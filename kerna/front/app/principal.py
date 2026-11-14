"""Front web de Kerna AI: portada pública y panel de métricas agregadas (protegido)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from fastapi.templating import Jinja2Templates

from datetime import datetime, timedelta, timezone

from fastapi.responses import Response

import json
import re
import time

from . import ajustes as aj, orbital, cache, consultas, evaluaciones, exportar, formato, glosario, graficos, informe as inf_mod, negocio, proveedores, reintentos, seguridad, vistas

BASE = Path(__file__).parent
app = FastAPI(title="Kerna AI", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=6)
app.mount("/estaticos", StaticFiles(directory=BASE / "estaticos"), name="estaticos")
plantillas = Jinja2Templates(directory=BASE / "plantillas")
plantillas.env.globals.update(graficos.FUNCIONES)
plantillas.env.globals.update(formato.FUNCIONES)
plantillas.env.globals.update(orbital.FUNCIONES)
plantillas.env.filters["zip"] = lambda a, b: zip(a, b)
_GLOS = glosario.glosario()
plantillas.env.globals.update(
    glos=_GLOS, glosario_json=json.dumps(_GLOS, ensure_ascii=False).replace("</", "<\\/"), ICONO=vistas.ICONO, motivo_ico=vistas.motivo_ico, ESTADO_TXT=vistas.ESTADO_TXT,
    ver=int(max((p.stat().st_mtime for p in (BASE / "estaticos").glob("*.*")), default=0)))

def _sprites() -> str:
    """Íconos de la identidad y de Lucide dentro de cada página (<use href="#id">): los sprites externos no los resuelven todos los navegadores."""
    partes = []
    for n in ("identidad.svg", "iconos.svg"):
        t = (BASE / "estaticos" / n).read_text(encoding="utf-8")
        partes.append(re.sub(r"</?svg[^>]*>", "", t))
    return '<svg id="sprites" width="0" height="0" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">' + "".join(partes) + "</svg>"


plantillas.env.globals["sprites"] = _sprites()

CABECERAS = {
    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; form-action 'self'",
}


@app.middleware("http")
async def cabeceras_seguras(request: Request, call_next):
    r = await call_next(request)
    for k, v in CABECERAS.items():
        r.headers.setdefault(k, v)
    ruta = request.url.path
    if ruta.startswith(("/panel", "/api", "/acceso")):
        r.headers["Cache-Control"] = "no-store"
    elif ruta.startswith("/estaticos/"):  # con ?v=<versión> el nombre cambia al cambiar el contenido: inmutable un año
        # los sprites se referencian sin ?v=: se revalidan (304 con ETag) para que un cambio llegue de inmediato
        r.headers["Cache-Control"] = ("public, max-age=31536000, immutable" if "v=" in request.url.query
                                      else "no-cache" if ruta.endswith(".svg") else "public, max-age=604800")
    return r


@app.get("/", response_class=HTMLResponse)
def portada(request: Request):
    return plantillas.TemplateResponse(request, "portada.html")


@app.get("/salud")
def salud():
    return {"estado": "ok"}


def _permitido(request: Request) -> bool:
    return seguridad.autorizado(request.headers, request.cookies)


@app.get("/acceso", response_class=HTMLResponse)
def acceso(request: Request):
    return plantillas.TemplateResponse(request, "acceso.html", {"error": False})


@app.post("/acceso")
def entrar(request: Request, clave: str = Form("")):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    if not seguridad.limitar(ip):
        return plantillas.TemplateResponse(request, "acceso.html", {"error": True}, status_code=429)
    if not seguridad.clave_valida(clave):
        seguridad.fallo(ip)
        return plantillas.TemplateResponse(request, "acceso.html", {"error": True}, status_code=401)
    r = RedirectResponse("/panel", status_code=303)
    r.set_cookie(seguridad.COOKIE, seguridad.emitir_cookie(), max_age=seguridad.VIDA_S, httponly=True, secure=True,
                 samesite="strict", path="/")
    return r


_extra_cache: dict = {}


def _extra_directo(nombre: str, dias: int) -> list[dict]:
    try:
        return consultas.filas(reintentos._kql(nombre + ".kql").replace("ago(7d)", f"ago({int(dias)}d)"), dias)
    except Exception:
        return []


def _extra(nombre: str, dias: int, ttl: float = consultas.TTL_S) -> list[dict]:
    """Consulta auxiliar del Resumen (costo, etapas, horarios) con caché compartida; si falla, no hay datos (nunca rompe el panel)."""
    return cache.obtener(("extra", nombre, dias), lambda: _extra_directo(nombre, dias), ttl)


def _vista_resumen(m: dict, dias: int, prov, rei) -> dict:
    def ev():
        try:
            return cache.obtener(("ev",), evaluaciones.cargar, 120)
        except Exception:
            return None
    r = cache.paralelo({"ev": ev, **{k: (lambda k=k: _extra(k, dias)) for k in ("front_tokens_por_modelo", "latencia_por_etapa", "front_horarios")}})
    g = lambda k: [] if isinstance(r[k], Exception) else r[k]  # noqa: E731
    return vistas.resumen(m, None if isinstance(r["ev"], Exception) else r["ev"], prov, rei, vistas.costo_modelos(g("front_tokens_por_modelo")),
                          vistas.etapas_lista(g("latencia_por_etapa")), vistas.heat(g("front_horarios")), dias, conector=reintentos.con_estado_real(None, _conector()))


def _metricas(dias: int) -> dict:
    return cache.obtener(("metricas", dias), lambda: consultas.metricas(dias), consultas.TTL_S)


def _prov():
    return cache.obtener(("prov",), proveedores.estado_proveedores, 60)


@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request, dias: int = 7):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    dias = dias if dias in consultas.RANGOS else 7
    r = cache.paralelo({"m": lambda: _metricas(dias), "prov": _prov, "rei": _reintentos_ctx})
    m, error = (None, type(r["m"]).__name__) if isinstance(r["m"], Exception) else (r["m"], None)  # sin identidad, sin rol o Log Analytics caído: no se filtra el detalle
    prov = None if isinstance(r["prov"], Exception) else r["prov"]  # la página de estado nunca debe romper el panel
    rei = None if isinstance(r["rei"], Exception) else r["rei"]
    V = _vista_resumen(m, dias, prov, rei) if m else None
    P = vistas.presentacion_resumen(V, rei, dias) if V else None
    return plantillas.TemplateResponse(request, "panel.html", {"m": m, "V": V, "P": P, "error": error, "prov": prov, "rei": rei, "vb": reintentos.vista_boton(rei["s"] if rei else None), "vivo": _dato_en_vivo(dias), "csrf": seguridad.token_csrf(request.cookies),
                                                               "aviso": request.query_params.get("reintento"), "dias": dias})


def _conector():
    try:
        return cache.obtener(("rei_c",), reintentos.estado_conector, 5)
    except Exception:  # sin la fila o sin tabla: «En vivo» usa la telemetría
        return None


def _reintentos_ctx():
    """Pendientes: el último estado real del conector, con su hora; la telemetría solo si el conector nunca escribió su fila. Sin ninguno de los dos, el bloque se oculta."""
    def uno(clave, fn, ttl):
        try:
            return cache.obtener(clave, fn, ttl)
        except Exception:
            return None
    r, s, c = uno(("rei",), reintentos.resumen, 60), uno(("rei_s",), reintentos.estado_solicitud, 5), _conector()
    real = reintentos.con_estado_real(r, c)
    if real is None or s is None:
        return None
    return {"r": real, "s": s, "ayuda": reintentos.ayuda_pendientes(real)}


def _dato_en_vivo(dias: int = 7) -> dict:
    """Hora del último dato recibido: la fila `conector` (segundos de latencia) o, si no existe, la última consulta a la telemetría."""
    c = _conector()
    if c and c.get("actualizado_en"):
        return {"dato": c["actualizado_en"], "fuente": "conector"}
    t = cache.marca(("metricas", dias))
    return {"dato": datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None, "fuente": "telemetria"}


@app.get("/panel/reintentar/estado")
def reintentar_estado(request: Request, dias: int = 7):
    """Estado en vivo del botón de reintento y de «En vivo» (la página lo pide cada pocos segundos, sin recargar)."""
    if not _permitido(request):
        return JSONResponse({"estado": "sesion"}, status_code=401)
    try:
        s = cache.obtener(("rei_s",), reintentos.estado_solicitud, 3)
    except Exception:
        return JSONResponse({"estado": "error"}, status_code=502)
    vm = reintentos.vista_boton(s)
    return JSONResponse({"estado": s.get("estado", "ninguna"), **vm, "html": str(plantillas.get_template("_reintento_accion.html").module.accion(vm)), **_dato_en_vivo(dias)},
                        headers={"Cache-Control": "no-store"})


@app.get("/panel/reintentar", response_class=HTMLResponse)
def reintentar_confirmar(request: Request):
    """Paso de confirmación (sin JavaScript): explica qué pasará y pide el segundo clic."""
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    return plantillas.TemplateResponse(request, "reintentar.html", {"ctx": _reintentos_ctx(), "csrf": seguridad.token_csrf(request.cookies)})


def _quiere_json(request: Request) -> bool:
    """El modal del Resumen envía el POST con fetch y pide JSON; un envío normal de formulario recibe una redirección con aviso."""
    return "application/json" in request.headers.get("accept", "")


def _respuesta_post(request: Request, destino: str, clave: str, estado: str, codigo_json: int = 200):
    """Nunca una página JSON en blanco: con fetch devuelve el resultado; sin JavaScript, 303 a la vista con el aviso."""
    if _quiere_json(request):
        return JSONResponse({"estado": estado}, status_code=codigo_json)
    return RedirectResponse(f"{destino}?{clave}={estado}", status_code=303)


@app.post("/panel/reintentar")
def reintentar(request: Request, csrf: str = Form("")):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303) if not _quiere_json(request) else JSONResponse({"estado": "sesion"}, status_code=401)
    if not _origen_ok(request):
        return _respuesta_post(request, "/panel", "reintento", "origen", 403)
    if not seguridad.csrf_valido(request.cookies, csrf):
        return _respuesta_post(request, "/panel", "reintento", "token", 403)
    try:
        r = reintentos.solicitar()
        cache.invalidar(("rei_s",))
    except Exception:
        r = "error"
    return _respuesta_post(request, "/panel", "reintento", r)


@app.get("/api/proveedores")
def api_proveedores(request: Request):
    if not _permitido(request):
        return JSONResponse({"detalle": "no autorizado"}, status_code=401)
    return proveedores.estado_proveedores()


@app.get("/api/metricas")
def api_metricas(request: Request, dias: int = 7):
    if not _permitido(request):
        return JSONResponse({"detalle": "no autorizado"}, status_code=401)
    try:
        m = _metricas(dias if dias in consultas.RANGOS else 7)
    except Exception as e:
        return JSONResponse({"detalle": "consulta fallida", "tipo": type(e).__name__}, status_code=502)
    try:
        prov = _prov()
    except Exception:
        prov = None
    # La vista (estados, textos y series ya calculados) lleva lo que el Resumen necesita para refrescarse sin recargar.
    return {**m, "vista": _vista_resumen(m, m["dias"], prov, None)}


def _informe(dias, desde, hasta):
    dias, desde, hasta = _norm_informe(dias, desde, hasta)

    def calcular():
        ini, fin = inf_mod.periodo(dias, desde, hasta)
        try:
            n = negocio.cargar(dias=(fin - ini).days or 30)
        except Exception:
            n = None  # la sección de rentabilidad declara que no hay datos
        inf = inf_mod.construir(ini, fin, negocio=n, conector=reintentos.con_estado_real(None, _conector()))
        if inf.get("fallos", 0) > 3:  # casi todo falló (p. ej. identidad aún sin token): un segundo intento antes de guardar el resultado
            time.sleep(2)
            inf = inf_mod.construir(ini, fin, negocio=n, conector=reintentos.con_estado_real(None, _conector()))
        return inf
    return cache.obtener(("informe", dias, desde, hasta), calcular, 120)


def precalentar():
    """Al arrancar: deja listos Resumen, informe y Negocio para que la primera visita no espere a Log Analytics."""
    cache.precalentar([(("metricas", 7), lambda: consultas.metricas(7), 60), (("prov",), proveedores.estado_proveedores, 60),
                       (("informe", 30, None, None), lambda: _informe_directo(30), 120), (("rei",), reintentos.resumen, 60), (("ev",), evaluaciones.cargar, 120),
                       (("negocio", 30), lambda: negocio.cargar(dias=30), 120), (("ajustes",), aj.cargar, 15)]
                      + [(("extra", k, 7), (lambda k=k: _extra_directo(k, 7)), consultas.TTL_S) for k in ("front_tokens_por_modelo", "latencia_por_etapa", "front_horarios")])


def _informe_directo(dias):
    ini, fin = inf_mod.periodo(dias, None, None)
    try:
        n = negocio.cargar(dias=(fin - ini).days or 30)
    except Exception:
        n = None
    inf = inf_mod.construir(ini, fin, negocio=n, conector=reintentos.con_estado_real(None, _conector()))
    return inf


@app.on_event("startup")
def _arranque():
    precalentar()


def _norm_informe(dias, desde, hasta):
    return (None, desde, hasta or None) if desde else (dias if dias in inf_mod.RANGOS else 30, None, None)


def _ctx_informe(dias, desde, hasta):
    d, ds, hs = _norm_informe(dias, desde, hasta)
    ini, fin = inf_mod.periodo(d, ds, hs)
    return {"q": f"desde={desde}&hasta={hasta}" if desde else f"dias={d}", "dias": d if not desde else 0, "desde": desde, "hasta": hasta,
            "periodo_txt": f"{ini:%Y-%m-%d} a {(fin - timedelta(seconds=1)):%Y-%m-%d}"}


@app.get("/panel/informe", response_class=HTMLResponse)
def panel_informe(request: Request, dias: int = 30, desde: str = "", hasta: str = ""):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    d, ds, hs = _norm_informe(dias, desde, hasta)
    ctx = _ctx_informe(dias, desde, hasta)
    listo = cache.hay(("informe", d, ds, hs))
    if listo:  # con datos ya calculados la página sale completa; si no, sale el esqueleto y el cuerpo llega por /panel/informe/cuerpo
        inf = _informe(d, ds, hs)
        ctx.update(V2=vistas.informe_v2(inf))
    return plantillas.TemplateResponse(request, "informe.html", {**ctx, "inf": {"meta": {"periodo": ctx["periodo_txt"]}}, "listo": listo})


@app.get("/panel/informe/cuerpo", response_class=HTMLResponse)
def panel_informe_cuerpo(request: Request, dias: int = 30, desde: str = "", hasta: str = ""):
    if not _permitido(request):
        return JSONResponse({"detalle": "no autorizado"}, status_code=401)
    d, ds, hs = _norm_informe(dias, desde, hasta)
    inf = _informe(d, ds, hs)
    return plantillas.TemplateResponse(request, "informe_cuerpo.html", {**_ctx_informe(dias, desde, hasta), "V2": vistas.informe_v2(inf)})


@app.get("/panel/informe/datos", response_class=HTMLResponse)
def panel_informe_datos(request: Request, dias: int = 30, desde: str = "", hasta: str = ""):
    if not _permitido(request):
        return JSONResponse({"detalle": "no autorizado"}, status_code=401)
    d, ds, hs = _norm_informe(dias, desde, hasta)
    return plantillas.TemplateResponse(request, "informe_datos.html", {**_ctx_informe(dias, desde, hasta), "secciones": vistas.informe(_informe(d, ds, hs))})


_FORMATOS = {"xlsx": (exportar.a_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
             "csv": (exportar.a_csv, "text/csv; charset=utf-8"), "pdf": (exportar.a_pdf, "application/pdf")}


@app.get("/panel/informe/descargar.{ext}")
def descargar_informe(ext: str, request: Request, dias: int = 30, desde: str = "", hasta: str = ""):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    if ext not in _FORMATOS:
        return JSONResponse({"detalle": "formato no disponible"}, status_code=404)
    inf = _informe(dias, desde or None, hasta or None)
    f, tipo = _FORMATOS[ext]
    nombre = "informe-kerna-%s.%s" % (inf["meta"]["periodo"].replace(" a ", "_"), ext)
    return Response(f(inf), media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@app.get("/api/negocio")
def api_negocio(request: Request, dias: int = 30):
    if not _permitido(request):
        return JSONResponse({"detalle": "no autorizado"}, status_code=401)
    try:
        d = negocio.cargar(dias=30 if dias not in (7, 30, 90) else dias)
    except Exception as e:
        return JSONResponse({"detalle": "consulta fallida", "tipo": type(e).__name__}, status_code=502)
    return d if d is not None else JSONResponse({"detalle": "sin datos de clientes"}, status_code=404)


@app.get("/panel/negocio", response_class=HTMLResponse)
def panel_negocio(request: Request, dias: int = 30):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    try:
        n, error = cache.obtener(("negocio", 30 if dias not in (7, 30, 90) else dias), lambda: negocio.cargar(dias=30 if dias not in (7, 30, 90) else dias), 120), None
    except Exception as e:
        n, error = None, type(e).__name__
    dias = 30 if dias not in (7, 30, 90) else dias
    V = vistas.negocio(n) if n else None
    P = vistas.presentacion_negocio(V, n) if V else None
    return plantillas.TemplateResponse(request, "negocio.html", {"n": n, "V": V, "P": P, "error": error, "dias": dias})


def _origen_ok(request: Request) -> bool:
    """Mismo origen. Se compara solo el host: detrás de App Service la app recibe http aunque el navegador use https."""
    from urllib.parse import urlparse
    origen = request.headers.get("origin")
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip().lower()
    if origen and origen != "null" and urlparse(origen).netloc.lower() != host:
        return False
    return request.headers.get("sec-fetch-site", "same-origin") in ("same-origin", "none")


@app.get("/panel/ajustes", response_class=HTMLResponse)
def panel_ajustes(request: Request):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    try:
        est, error = cache.obtener(("ajustes",), aj.cargar, 15, vida_max=86400), None
    except Exception as e:
        est, error = {"valores": aj.RECOMENDADO, "guardado_en": None}, type(e).__name__
    return plantillas.TemplateResponse(request, "ajustes.html", {
        "grupos": aj.GRUPOS, "datos": {"valores": est["valores"], "recomendado": aj.RECOMENDADO, "grupos": aj.GRUPOS, "modelos": aj.MODELOS},
        "guardado_en": est["guardado_en"], "error": error, "csrf": seguridad.token_csrf(request.cookies), "aviso": request.query_params.get("guardado"),
        "modelos": aj.MODELOS, "valores": est["valores"], "rec": aj.RECOMENDADO})


@app.post("/panel/ajustes")
def guardar_ajustes(request: Request, csrf: str = Form(""), valores: str = Form("")):
    """Con fetch (Accept: application/json) responde {estado, guardado_en}; un envío normal recibe una redirección con aviso."""
    js = _quiere_json(request)
    if not _permitido(request):
        return JSONResponse({"estado": "sesion"}, status_code=401) if js else RedirectResponse("/acceso", status_code=303)

    def fin(estado, codigo=200, **extra):
        return JSONResponse({"estado": estado, **extra}, status_code=codigo) if js else RedirectResponse(f"/panel/ajustes?guardado={estado}", status_code=303)
    if not _origen_ok(request):
        return fin("origen", 403)
    if not seguridad.csrf_valido(request.cookies, csrf):
        return fin("token", 403)
    try:
        v = json.loads(valores)
        aj.validar(v)
    except (ValueError, TypeError, AttributeError):
        return fin("invalido", 400)
    try:
        g = aj.guardar(v)
        cache.poner(("ajustes",), g)  # lo recién guardado queda como dato fresco: sin leer la tabla ni servir el valor anterior
        return fin("ok", guardado_en=g["guardado_en"])
    except Exception:
        return fin("error", 502)
