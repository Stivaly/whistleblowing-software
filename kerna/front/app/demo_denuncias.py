"""Demo del panel, sección «Denuncias»: una denuncia pasa por el núcleo real de Kerna y se compara con la respuesta esperada.

`principal.py` la carga si existe: `registrar(app, permitido, plantillas)` agrega las rutas y `contexto()` entrega lo que usa
`_demo_denuncias.html` (variable `den`).

Cómo llega al núcleo: el front es un cliente más (OAuth client credentials, como el conector de Veridy) con una cuenta propia de demo,
`DEMO_CLIENT_ID` y `DEMO_CLIENT_SECRET` (referencias de Key Vault, ver infra/terraform/front.tf), contra `KERNA_NUCLEO_URL`.
El relato va por POST /v1/casos con una referencia opaca nueva y se consulta GET /v1/casos/{ref}/sugerencia; el núcleo lo anonimiza antes
de analizarlo. Si falta alguna de las tres variables o el núcleo no responde, la pantalla muestra la respuesta esperada guardada, con un
aviso claro.

El texto de la denuncia solo vive en memoria durante el envío: no se guarda, no se registra y las respuestas del núcleo no se almacenan.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from fastapi import Form, Request
from fastapi.responses import JSONResponse

from . import seguridad
from .demo_denuncias_casos import CASOS, POR_ID

MAX_CARACTERES = 6000
MIN_CARACTERES = 40
ID_EMPRESA = "demo-panel"          # id_empresa que viaja con cada caso (el núcleo lo guarda en su registro de solicitudes)
PLAZO_SEGUIMIENTO_S = 600          # el núcleo corta a los 420 s (KERNA_PLAZO_GLOBAL_S); este es el margen de memoria de referencias
TOPE_10_MIN, TOPE_DIA = 8, 60      # el núcleo gasta modelos de pago: se limita el uso de la demo
TIMEOUT_TOKEN_S, TIMEOUT_ENVIO_S, TIMEOUT_CONSULTA_S = 30, 70, 30

LEYES = (
    {"tipo": "karin", "norma": "Ley 21.643 (Karin)", "numero": "21.643", "nombre": "Ley Karin",
     "tema": "Acoso y violencia en el trabajo, con sus cambios al Código del Trabajo y a los estatutos administrativos"},
    {"tipo": "datos", "norma": "Ley 19.628 y Ley 21.719 (datos personales)", "numero": "19.628 y 21.719", "nombre": "Datos personales",
     "tema": "Protección y tratamiento de datos personales"},
    {"tipo": "penal", "norma": "Ley 20.393 (responsabilidad penal de personas jurídicas)", "numero": "20.393", "nombre": "Responsabilidad penal",
     "tema": "Responsabilidad penal de las personas jurídicas"},
)
NOMBRE_LEY = {"karin": "Ley Karin (21.643)", "datos": "Datos personales (19.628 y 21.719)", "penal": "Responsabilidad penal (20.393)"}

# Prefijo del id de fragmento -> ley del corpus. 1209272 son los transitorios de la Ley 21.719.
_PREFIJOS = (("1200096-", "karin"), ("207436-karin", "karin"), ("191865-karin", "karin"), ("236392-karin", "karin"), ("30256-karin", "karin"),
             ("251693-karin", "karin"), ("141599-", "datos"), ("1209272-", "datos"), ("1008668-", "penal"))
_SUFIJO_PARTE = re.compile(r"-p\d+$")

_cerrojo = threading.Lock()
_token: dict = {"valor": "", "vence": 0.0}
_refs: dict[str, dict] = {}        # ref -> {"caso": id del caso de la lista si el texto no se tocó, "t": cuándo}. Nunca guarda el texto.
_envios: list[float] = []


class NucleoNoDisponible(Exception):
    """`motivo`: no_configurado | no_responde | credenciales."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


# ---- ley de un artículo ---------------------------------------------------------------------------------------------------

def tipo_ley(id_articulo: str = "", norma: str = "") -> str | None:
    """karin | datos | penal según el id del fragmento (o, si no calza, el nombre de la norma); None si no es del corpus de la demo."""
    i = str(id_articulo or "")
    for pref, tipo in _PREFIJOS:
        if i.startswith(pref):
            return tipo
    n = str(norma or "")
    if re.search(r"21\.?643|karin", n, re.I):
        return "karin"
    if re.search(r"19\.?628|21\.?719|datos personales", n, re.I):
        return "datos"
    if re.search(r"20\.?393|penal de las personas", n, re.I):
        return "penal"
    return None


def _base(id_articulo: str) -> str:
    return _SUFIJO_PARTE.sub("", str(id_articulo or "").strip().lower())


def _igual(a: str, b: str) -> bool:
    return " ".join(str(a).split()) == " ".join(str(b).split())


# ---- cliente del núcleo ---------------------------------------------------------------------------------------------------

def _env(nombre: str) -> str:
    v = os.environ.get(nombre, "").strip()
    return "" if not v or v.startswith("@Microsoft.KeyVault") else v     # una referencia de Key Vault sin resolver = sin valor


def configurado() -> bool:
    return bool(_env("KERNA_NUCLEO_URL") and _env("DEMO_CLIENT_ID") and _env("DEMO_CLIENT_SECRET"))


def _pedir(metodo: str, ruta: str, *, cuerpo=None, formulario=None, token: str = "", timeout: float = 30) -> tuple[int, dict]:
    """(estado HTTP, JSON). Un fallo de red o un 5xx es NucleoNoDisponible('no_responde'); un 4xx se devuelve para que lo interprete quien llama."""
    datos, cab = None, {"Accept": "application/json"}
    if formulario is not None:
        datos, cab["Content-Type"] = urllib.parse.urlencode(formulario).encode(), "application/x-www-form-urlencoded"
    elif cuerpo is not None:
        datos, cab["Content-Type"] = json.dumps(cuerpo).encode(), "application/json"
    if token:
        cab["Authorization"] = "Bearer " + token
    req = urllib.request.Request(_env("KERNA_NUCLEO_URL").rstrip("/") + ruta, data=datos, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code >= 500:
            raise NucleoNoDisponible("no_responde") from None
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise NucleoNoDisponible("no_responde") from None


def _obtener_token(forzar: bool = False) -> str:
    with _cerrojo:
        if not forzar and _token["valor"] and time.time() < _token["vence"] - 60:
            return _token["valor"]
    est, d = _pedir("POST", "/oauth/token", timeout=TIMEOUT_TOKEN_S,
                    formulario={"grant_type": "client_credentials", "client_id": _env("DEMO_CLIENT_ID"), "client_secret": _env("DEMO_CLIENT_SECRET")})
    if est != 200 or not d.get("access_token"):
        raise NucleoNoDisponible("credenciales")
    with _cerrojo:
        _token.update(valor=d["access_token"], vence=time.time() + float(d.get("expires_in", 600)))
        return _token["valor"]


def _con_token(metodo: str, ruta: str, *, cuerpo=None, timeout: float = 30) -> tuple[int, dict]:
    if not configurado():
        raise NucleoNoDisponible("no_configurado")
    for vuelta in (0, 1):
        est, d = _pedir(metodo, ruta, cuerpo=cuerpo, token=_obtener_token(forzar=bool(vuelta)), timeout=timeout)
        if est != 401 or vuelta:
            return est, d
    return est, d  # pragma: no cover


def enviar_caso(ref: str, texto: str) -> None:
    est, _ = _con_token("POST", "/v1/casos", cuerpo={"ref_opaca": ref, "id_empresa": ID_EMPRESA, "texto": texto}, timeout=TIMEOUT_ENVIO_S)
    if est not in (200, 201, 202):
        raise NucleoNoDisponible("credenciales" if est in (401, 403) else "no_responde")


def consultar(ref: str) -> dict | None:
    """Respuesta de GET /v1/casos/{ref}/sugerencia; None si el núcleo no conoce la referencia."""
    est, d = _con_token("GET", f"/v1/casos/{ref}/sugerencia", timeout=TIMEOUT_CONSULTA_S)
    if est == 404:
        return None
    if est != 200:
        raise NucleoNoDisponible("no_responde")
    return d


# ---- respuesta esperada y comparación -----------------------------------------------------------------------------------------

def esperado(caso: dict | None) -> dict | None:
    if not caso:
        return None
    return {"tipo": caso["tipo"], "fuera": caso.get("fuera", ""), "titulo": caso["titulo"],
            "articulos": [{"id": i, "etiqueta": e, "ley": tipo_ley(i)} for i, e in caso["articulos"]]}


def _articulo_vista(a: dict, ids_esperados: set[str]) -> dict:
    ia = str(a.get("id_articulo") or "")
    veredicto = {"confirma": "mantiene", "condiciona": "condiciona", "veta": "veta"}.get(str(a.get("dictamen") or ""), "")
    return {"id": ia, "ley": tipo_ley(ia, a.get("norma", "")), "norma": str(a.get("norma") or ""), "articulo": str(a.get("articulo") or ""),
            "explicacion": str(a.get("explicacion") or ""), "cita": str(a.get("cita") or ""), "confianza": round(float(a.get("confianza") or 0), 2),
            "veredicto": veredicto, "coincide": _base(ia) in ids_esperados}


def vista_resultado(resp: dict, caso: dict | None) -> dict:
    """Respuesta del núcleo -> lo que muestra la pantalla. `caso` es el de la lista (solo si el texto enviado no se modificó) o None."""
    if resp.get("estado") == "pendiente":
        return {"estado": "procesando"}
    exp = esperado(caso)
    ids_exp = {_base(a["id"]) for a in exp["articulos"]} if exp else set()
    todos = [_articulo_vista(a, ids_exp) for a in resp.get("articulos") or []] if resp.get("estado") == "completada" else []
    vivos = [a for a in todos if a["veredicto"] != "veta"]
    out = {"estado": "listo" if vivos else "sin_sugerencia", "nucleo": True, "articulos": vivos, "vetados": len(todos) - len(vivos),
           "motivo": resp.get("motivo_revision") or ("" if vivos else "sin_normativa_aplicable"), "modo": resp.get("modo") or "",
           "esperado": exp, "comparacion": None, "detalle": ""}
    if exp:
        if exp["tipo"] == "fuera":
            out["comparacion"] = "difiere" if vivos else "coincide"
            out["detalle"] = "con_sugerencia" if vivos else ""
        elif any(a["coincide"] for a in vivos):
            out["comparacion"] = "coincide"
        else:
            out["comparacion"] = "difiere"
            out["detalle"] = ("sin_sugerencia" if not vivos else "misma_ley" if any(a["ley"] == exp["tipo"] for a in vivos) else "otra_ley")
    return out


def vista_sin_nucleo(motivo: str, caso: dict | None) -> dict:
    return {"estado": "sin_nucleo", "nucleo": False, "motivo": motivo, "esperado": esperado(caso), "articulos": [], "comparacion": None}


# ---- límites y referencias ------------------------------------------------------------------------------------------------------

def _limitar(ahora: float | None = None) -> bool:
    """True si se puede enviar otra denuncia (tope por 10 minutos y por día, de toda la demo)."""
    t = time.time() if ahora is None else ahora
    with _cerrojo:
        _envios[:] = [x for x in _envios if t - x < 86400]
        if len(_envios) >= TOPE_DIA or sum(1 for x in _envios if t - x < 600) >= TOPE_10_MIN:
            return False
        _envios.append(t)
        return True


def _recordar(ref: str, caso_id: str) -> None:
    ahora = time.time()
    with _cerrojo:
        for k in [k for k, v in _refs.items() if ahora - v["t"] > PLAZO_SEGUIMIENTO_S]:
            del _refs[k]
        _refs[ref] = {"caso": caso_id, "t": ahora}


# ---- rutas ---------------------------------------------------------------------------------------------------------------------

def _origen_ok(request: Request) -> bool:
    """Mismo origen. Se compara solo el host: detrás de App Service la app recibe http aunque el navegador use https."""
    origen = request.headers.get("origin")
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip().lower()
    if origen and origen != "null" and urllib.parse.urlparse(origen).netloc.lower() != host:
        return False
    return request.headers.get("sec-fetch-site", "same-origin") in ("same-origin", "none")


def registrar(app, permitido, plantillas=None) -> None:
    """Agrega POST /panel/demo/denuncia (envía) y GET /panel/demo/denuncia/{ref} (consulta). Ambas exigen la sesión del panel;
    la primera, además, mismo origen y token CSRF."""

    @app.post("/panel/demo/denuncia")
    def enviar(request: Request, csrf: str = Form(""), texto: str = Form(""), caso: str = Form("")):
        if not permitido(request):
            return JSONResponse({"estado": "sesion"}, status_code=401)
        if not _origen_ok(request):
            return JSONResponse({"estado": "origen"}, status_code=403)
        if not seguridad.csrf_valido(request.cookies, csrf):
            return JSONResponse({"estado": "token"}, status_code=403)
        texto = texto.replace("\r\n", "\n").strip()
        if len(texto) < MIN_CARACTERES:
            return JSONResponse({"estado": "corto"}, status_code=400)
        if len(texto) > MAX_CARACTERES:
            return JSONResponse({"estado": "largo"}, status_code=400)
        de_lista = POR_ID.get(caso)
        if de_lista is not None and not _igual(de_lista["texto"], texto):
            de_lista = None                                   # texto modificado: ya no es esa denuncia, no hay respuesta esperada
        if not _limitar():
            return JSONResponse({"estado": "limite"}, status_code=429)
        ref = str(uuid.uuid4())
        try:
            enviar_caso(ref, texto)
        except NucleoNoDisponible as e:
            return JSONResponse(vista_sin_nucleo(e.motivo, de_lista))
        _recordar(ref, de_lista["id"] if de_lista else "")
        return JSONResponse({"estado": "ok", "ref": ref})

    @app.get("/panel/demo/denuncia/{ref}")
    def consulta(request: Request, ref: str):
        if not permitido(request):
            return JSONResponse({"estado": "sesion"}, status_code=401)
        try:
            ref = str(uuid.UUID(ref))
        except ValueError:
            return JSONResponse({"estado": "desconocida"}, status_code=404)
        with _cerrojo:
            memoria = _refs.get(ref)
        if memoria is None:
            return JSONResponse({"estado": "desconocida"}, status_code=404)
        caso = POR_ID.get(memoria["caso"])
        try:
            resp = consultar(ref)
        except NucleoNoDisponible as e:
            return JSONResponse(vista_sin_nucleo(e.motivo, caso))
        if resp is None:
            return JSONResponse({"estado": "desconocida"}, status_code=404)
        return JSONResponse(vista_resultado(resp, caso))


# ---- contexto de la plantilla ------------------------------------------------------------------------------------------------------

def _json_seguro(d) -> str:
    """JSON para un <script type="application/json">: sin `<`, `>` ni `&` literales."""
    return json.dumps(d, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def contexto() -> dict:
    casos = [{"id": c["id"], "tipo": c["tipo"], "titulo": c["titulo"], "fuera": c.get("fuera", ""), "ley": NOMBRE_LEY.get(c["tipo"], "")} for c in CASOS]
    datos = {"max": MAX_CARACTERES, "min": MIN_CARACTERES, "leyes": NOMBRE_LEY,
             "casos": {c["id"]: {"texto": c["texto"], "tipo": c["tipo"], "titulo": c["titulo"], "fuera": c.get("fuera", ""),
                                 "esperado": esperado(c)["articulos"]} for c in CASOS}}
    return {"leyes": LEYES, "casos": casos, "max_car": MAX_CARACTERES, "configurado": configurado(), "json": _json_seguro(datos)}
