"""Front web de Kerna AI: portada pública y panel de métricas agregadas (protegido)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from datetime import datetime

from fastapi.responses import Response

from . import consultas, exportar, graficos, informe as inf_mod, negocio, seguridad

BASE = Path(__file__).parent
app = FastAPI(title="Kerna AI", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/estaticos", StaticFiles(directory=BASE / "estaticos"), name="estaticos")
plantillas = Jinja2Templates(directory=BASE / "plantillas")
plantillas.env.globals.update(graficos.FUNCIONES)
plantillas.env.filters["zip"] = lambda a, b: zip(a, b)

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


@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request, dias: int = 7):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    try:
        m, error = consultas.metricas(dias), None
    except Exception as e:  # sin identidad, sin rol o Log Analytics caído: no se filtra el detalle
        m, error = None, type(e).__name__
    return plantillas.TemplateResponse(request, "panel.html", {"m": m, "error": error, "dias": dias if dias in consultas.RANGOS else 7})


@app.get("/api/metricas")
def api_metricas(request: Request, dias: int = 7):
    if not _permitido(request):
        return JSONResponse({"detalle": "no autorizado"}, status_code=401)
    try:
        return consultas.metricas(dias)
    except Exception as e:
        return JSONResponse({"detalle": "consulta fallida", "tipo": type(e).__name__}, status_code=502)


def _informe(dias, desde, hasta):
    ini, fin = inf_mod.periodo(dias, desde, hasta)
    return inf_mod.construir(ini, fin)


@app.get("/panel/informe", response_class=HTMLResponse)
def panel_informe(request: Request, dias: int = 30, desde: str = "", hasta: str = ""):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    inf = _informe(dias, desde or None, hasta or None)
    q = f"desde={desde}&hasta={hasta}" if desde else f"dias={dias if dias in inf_mod.RANGOS else 30}"
    return plantillas.TemplateResponse(request, "informe.html", {"inf": inf, "dias": dias if not desde else 0, "q": q, "desde": desde, "hasta": hasta, "fmt": exportar._fmt})


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
def api_negocio(request: Request, dias: int = 30, crec: float = 15.0):
    if not _permitido(request):
        return JSONResponse({"detalle": "no autorizado"}, status_code=401)
    try:
        d = negocio.cargar(crec=min(max(crec, 0), 30), dias=30 if dias not in (7, 30, 90) else dias)
    except Exception as e:
        return JSONResponse({"detalle": "consulta fallida", "tipo": type(e).__name__}, status_code=502)
    return d if d is not None else JSONResponse({"detalle": "sin datos de clientes"}, status_code=404)


@app.get("/panel/negocio", response_class=HTMLResponse)
def panel_negocio(request: Request, dias: int = 30, crec: float = 15.0):
    if not _permitido(request):
        return RedirectResponse("/acceso", status_code=303)
    try:
        n, error = negocio.cargar(crec=min(max(crec, 0), 30), dias=30 if dias not in (7, 30, 90) else dias), None
    except Exception as e:
        n, error = None, type(e).__name__
    return plantillas.TemplateResponse(request, "negocio.html", {"n": n, "error": error, "dias": dias, "crec": crec})
