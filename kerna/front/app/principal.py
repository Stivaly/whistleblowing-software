"""Front web de Kerna AI: portada pública y panel de métricas agregadas (protegido)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from datetime import datetime

from fastapi.responses import Response

import json
import time

from . import consultas, evaluaciones, exportar, formato, glosario, graficos, informe as inf_mod, negocio, proveedores, reintentos, seguridad, vistas

BASE = Path(__file__).parent
app = FastAPI(title="Kerna AI", docs_url=None, redoc_url=None, openapi_url=None)
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
    if request.url.path.startswith(("/panel", "/api", "/acceso")):
        r.headers["Cache-Control"] = "no-store"
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
    """Consulta auxiliar del Resumen (costo, etapas, horarios) con caché corta; si falla, no hay datos (nunca rompe el panel)."""
    hit = _extra_cache.get((nombre, dias))
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    try:
        filas = consultas.filas(reintentos._kql(nombre + ".kql").replace("ago(7d)", f"ago({int(dias)}d)"), dias)
    except Exception:
        filas = []
    _extra_cache[(nombre, dias)] = (time.time(), filas)
    return filas


def _vista_resumen(m: dict, dias: int, prov, rei) -> dict:
    try:
        ev = evaluaciones.cargar()
    except Exception:
        ev = None
    return vistas.resumen(m, ev, prov, rei, vistas.costo_modelos(_extra("front_tokens_por_modelo", dias)),
                          vistas.etapas_lista(_extra("latencia_por_etapa", dias)), vistas.heat(_extra("front_horarios", dias)), dias)


@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request, dias: int = 7):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    dias = dias if dias in consultas.RANGOS else 7
    try:
        m, error = consultas.metricas(dias), None
    except Exception as e:  # sin identidad, sin rol o Log Analytics caído: no se filtra el detalle
        m, error = None, type(e).__name__
    try:
        prov = proveedores.estado_proveedores()
    except Exception:  # la página de estado nunca debe romper el panel
        prov = None
    rei = _reintentos_ctx()
    V = _vista_resumen(m, dias, prov, rei) if m else None
    return plantillas.TemplateResponse(request, "panel.html", {"m": m, "V": V, "error": error, "prov": prov, "rei": rei, "csrf": seguridad.token_csrf(request.cookies),
                                                               "aviso": request.query_params.get("reintento"), "dias": dias})


def _reintentos_ctx():
    try:
        return {"r": reintentos.resumen(), "s": reintentos.estado_solicitud()}
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
        m = consultas.metricas(dias)
    except Exception as e:
        return JSONResponse({"detalle": "consulta fallida", "tipo": type(e).__name__}, status_code=502)
    try:
        prov = proveedores.estado_proveedores()
    except Exception:
        prov = None
    # La vista (estados, textos y series ya calculados) lleva lo que el Resumen necesita para refrescarse sin recargar.
    return {**m, "vista": _vista_resumen(m, m["dias"], prov, None)}


def _informe(dias, desde, hasta):
    ini, fin = inf_mod.periodo(dias, desde, hasta)
    try:
        n = negocio.cargar(dias=(fin - ini).days or 30)
    except Exception:
        n = None  # la sección de rentabilidad declara que no hay datos
    return inf_mod.construir(ini, fin, negocio=n)


@app.get("/panel/informe", response_class=HTMLResponse)
def panel_informe(request: Request, dias: int = 30, desde: str = "", hasta: str = ""):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    inf = _informe(dias, desde or None, hasta or None)
    q = f"desde={desde}&hasta={hasta}" if desde else f"dias={dias if dias in inf_mod.RANGOS else 30}"
    return plantillas.TemplateResponse(request, "informe.html", {"inf": inf, "secciones": vistas.informe(inf), "dias": dias if not desde else 0, "q": q, "desde": desde, "hasta": hasta, "fmt": exportar._fmt})


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
        n, error = negocio.cargar(dias=30 if dias not in (7, 30, 90) else dias), None
    except Exception as e:
        n, error = None, type(e).__name__
    dias = 30 if dias not in (7, 30, 90) else dias
    V = vistas.negocio(n) if n else None
    return plantillas.TemplateResponse(request, "negocio.html", {"n": n, "V": V, "error": error, "dias": dias})
