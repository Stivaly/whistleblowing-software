"""Front web de Kerna AI: portada pública y panel de métricas agregadas (protegido)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from fastapi.templating import Jinja2Templates

from datetime import datetime, timedelta

from fastapi.responses import Response

import json
import time

from . import ajustes as aj, cache, consultas, evaluaciones, exportar, formato, glosario, graficos, informe as inf_mod, negocio, proveedores, reintentos, seguridad, vistas

BASE = Path(__file__).parent
app = FastAPI(title="Kerna AI", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=6)
app.mount("/estaticos", StaticFiles(directory=BASE / "estaticos"), name="estaticos")
plantillas = Jinja2Templates(directory=BASE / "plantillas")
plantillas.env.globals.update(graficos.FUNCIONES)
plantillas.env.globals.update(formato.FUNCIONES)
plantillas.env.filters["zip"] = lambda a, b: zip(a, b)
_GLOS = glosario.glosario()
plantillas.env.globals.update(
    glos=_GLOS, glosario_json=json.dumps(_GLOS, ensure_ascii=False).replace("</", "<\\/"), ICONO=vistas.ICONO, ESTADO_TXT=vistas.ESTADO_TXT,
    ver=int(max((p.stat().st_mtime for p in (BASE / "estaticos").glob("*.*")), default=0)))

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
        r.headers["Cache-Control"] = "public, max-age=31536000, immutable" if "v=" in request.url.query else "public, max-age=604800"
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


def _extra(nombre: str, dias: int, ttl: float = consultas.TTL_S) -> list[dict]:
    """Consulta auxiliar del Resumen (costo, etapas, horarios) con caché compartida; si falla, no hay datos (nunca rompe el panel)."""
    def calcular():
        try:
            return consultas.filas(reintentos._kql(nombre + ".kql").replace("ago(7d)", f"ago({int(dias)}d)"), dias)
        except Exception:
            return []
    return cache.obtener(("extra", nombre, dias), calcular, ttl)


def _vista_resumen(m: dict, dias: int, prov, rei) -> dict:
    def ev():
        try:
            return evaluaciones.cargar()
        except Exception:
            return None
    r = cache.paralelo({"ev": ev, **{k: (lambda k=k: _extra(k, dias)) for k in ("front_tokens_por_modelo", "latencia_por_etapa", "front_horarios")}})
    g = lambda k: [] if isinstance(r[k], Exception) else r[k]  # noqa: E731
    return vistas.resumen(m, None if isinstance(r["ev"], Exception) else r["ev"], prov, rei, vistas.costo_modelos(g("front_tokens_por_modelo")),
                          vistas.etapas_lista(g("latencia_por_etapa")), vistas.heat(g("front_horarios")), dias)


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
    return plantillas.TemplateResponse(request, "panel.html", {"m": m, "V": V, "error": error, "prov": prov, "rei": rei, "csrf": seguridad.token_csrf(request.cookies),
                                                               "aviso": request.query_params.get("reintento"), "dias": dias})


def _reintentos_ctx():
    try:
        return {"r": cache.obtener(("rei",), reintentos.resumen, 60), "s": reintentos.estado_solicitud()}
    except Exception:  # sin telemetría o sin tabla: el bloque se oculta, el panel sigue
        return None


@app.get("/panel/reintentar", response_class=HTMLResponse)
def reintentar_confirmar(request: Request):
    """Paso de confirmación (sin JavaScript): explica qué pasará y pide el segundo clic."""
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    return plantillas.TemplateResponse(request, "reintentar.html", {"ctx": _reintentos_ctx(), "csrf": seguridad.token_csrf(request.cookies)})


@app.post("/panel/reintentar")
def reintentar(request: Request, csrf: str = Form("")):
    if not _permitido(request):
        return JSONResponse({"detalle": "no autorizado"}, status_code=401)
    origen = request.headers.get("origin")
    if (origen and origen.rstrip("/") != str(request.base_url).rstrip("/")) or request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        return JSONResponse({"detalle": "origen no permitido"}, status_code=403)
    if not seguridad.csrf_valido(request.cookies, csrf):
        return JSONResponse({"detalle": "token inválido"}, status_code=403)
    try:
        r = reintentos.solicitar()
    except Exception:
        r = "error"
    return RedirectResponse(f"/panel?reintento={r}", status_code=303)


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
        inf = inf_mod.construir(ini, fin, negocio=n)
        if inf.get("fallos", 0) > 3:  # casi todo falló (p. ej. identidad aún sin token): un segundo intento antes de guardar el resultado
            time.sleep(2)
            inf = inf_mod.construir(ini, fin, negocio=n)
        return inf
    return cache.obtener(("informe", dias, desde, hasta), calcular, 120)


def precalentar():
    """Al arrancar: deja listos Resumen, informe y Negocio para que la primera visita no espere a Log Analytics."""
    cache.precalentar([(("metricas", 7), lambda: consultas.metricas(7), 60), (("prov",), proveedores.estado_proveedores, 60),
                       (("informe", 30, None, None), lambda: _informe_directo(30), 120)])


def _informe_directo(dias):
    ini, fin = inf_mod.periodo(dias, None, None)
    try:
        n = negocio.cargar(dias=(fin - ini).days or 30)
    except Exception:
        n = None
    inf = inf_mod.construir(ini, fin, negocio=n)
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
    return plantillas.TemplateResponse(request, "negocio.html", {"n": n, "V": V, "error": error, "dias": dias})


def _origen_ok(request: Request) -> bool:
    origen = request.headers.get("origin")
    return not ((origen and origen.rstrip("/") != str(request.base_url).rstrip("/")) or request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"))


@app.get("/panel/ajustes", response_class=HTMLResponse)
def panel_ajustes(request: Request):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    try:
        est, error = aj.cargar(), None
    except Exception as e:
        est, error = {"valores": aj.RECOMENDADO, "guardado_en": None}, type(e).__name__
    return plantillas.TemplateResponse(request, "ajustes.html", {
        "grupos": aj.GRUPOS, "datos": {"valores": est["valores"], "recomendado": aj.RECOMENDADO, "grupos": aj.GRUPOS, "modelos": aj.MODELOS},
        "guardado_en": est["guardado_en"], "error": error, "csrf": seguridad.token_csrf(request.cookies), "aviso": request.query_params.get("guardado"),
        "modelos": aj.MODELOS, "valores": est["valores"], "rec": aj.RECOMENDADO})


@app.post("/panel/ajustes")
def guardar_ajustes(request: Request, csrf: str = Form(""), valores: str = Form("")):
    if not _permitido(request):
        return JSONResponse({"detalle": "no autorizado"}, status_code=401)
    if not _origen_ok(request):
        return JSONResponse({"detalle": "origen no permitido"}, status_code=403)
    if not seguridad.csrf_valido(request.cookies, csrf):
        return JSONResponse({"detalle": "token inválido"}, status_code=403)
    try:
        v = json.loads(valores)
        aj.validar(v)
    except (ValueError, TypeError, AttributeError):
        return RedirectResponse("/panel/ajustes?guardado=invalido", status_code=303)
    try:
        aj.guardar(v)
        r = "ok"
    except Exception:
        r = "error"
    return RedirectResponse(f"/panel/ajustes?guardado={r}", status_code=303)
