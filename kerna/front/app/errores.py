"""Pantallas de error del front: toda falla responde con una página de Kerna (o JSON en /api y con Accept: application/json).

Nunca se muestra el detalle de la excepción, de pydantic ni una traza; en el log queda solo el tipo de la excepción y la ruta.
"""
from __future__ import annotations

import logging
import re

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("kerna.front.errores")

# código: (ilustración de estado, título, una línea). Los títulos se explican solos.
CATALOGO = {
    400: ("cadena-agotada", "No entendimos lo que enviaste", "Revisa los datos e inténtalo de nuevo."),
    401: ("revision-citas", "Necesitas entrar para ver esto", "Entra con la clave de acceso y vuelve a intentarlo."),
    403: ("revision-citas", "No pudimos confirmar tu solicitud", "Vuelve atrás, recarga la página e inténtalo otra vez."),
    404: ("sin-info", "No encontramos esta página", "La dirección no existe o cambió de lugar."),
    405: ("sin-info", "Esta acción no está disponible aquí", "Vuelve atrás y usa los botones de la página."),
    422: ("cadena-agotada", "Hay un dato que no es válido", "Corrígelo y vuelve a intentarlo."),
    429: ("revision-tiempo", "Demasiados intentos seguidos", "Espera un momento antes de volver a intentarlo."),
    500: ("cadena-agotada", "Algo falló de nuestro lado", "No se perdió nada. Inténtalo de nuevo en un momento."),
    502: ("sin-conexion", "Kerna no responde ahora", "Un servicio del que depende no contestó. Reintenta en un momento."),
    503: ("nucleo-no-disponible", "Kerna no responde ahora", "El servicio está ocupado o en pausa. Reintenta en un momento."),
    504: ("revision-tiempo", "Kerna no responde ahora", "Tardó demasiado en contestar. Reintenta en un momento."),
}
REINTENTABLES = {500, 502, 503, 504}
DEPENDENCIA_CAIDA = {502, 503, 504}


def _normal(codigo: int) -> int:
    if codigo in CATALOGO:
        return codigo
    return 500 if codigo >= 500 else 400 if codigo >= 400 else 500


def _espera(s: float | None) -> str:
    if not s or s <= 0:
        return ""
    s = int(s) + 1
    if s < 60:
        return f"Vuelve a intentarlo en {s} segundos."
    m = -(-s // 60)
    return f"Vuelve a intentarlo en {m} minuto{'s' if m != 1 else ''}."


def _campos(exc: RequestValidationError) -> str:
    """Nombres de los campos inválidos (sin valores ni mensajes de pydantic)."""
    nombres = []
    for e in exc.errors():
        loc = [str(p) for p in e.get("loc", ()) if p not in ("body", "query", "path", "header", "cookie")]
        n = re.sub(r"[^\w.-]", "", loc[0] if loc else "")[:30]
        if n and n not in nombres:
            nombres.append(n)
    return ", ".join(f"«{n}»" for n in nombres[:3])


def _destino_reintento(request, en_panel: bool) -> str:
    """Dirección a la que vuelve «Reintentar»: la misma página si se pidió con GET; si no, el inicio. Solo rutas locales simples."""
    base = "/panel" if en_panel else "/"
    ruta, q = request.url.path, request.url.query
    if ruta == "/acceso":
        return ruta
    if request.method != "GET" or not re.fullmatch(r"/[\w\-./]*", ruta) or ruta.startswith("//"):
        return base
    return ruta + ("?" + q if q and re.fullmatch(r"[\w=&.\-]{1,80}", q) else "")


def _json(request) -> bool:
    return request.url.path.startswith("/api/") or "application/json" in request.headers.get("accept", "")


def registrar(app, plantillas, hay_sesion, cabeceras: dict):
    """Instala los manejadores. `hay_sesion(request)` dice si hay sesión de panel (decide el marco de la pantalla)."""

    def pantalla(request, codigo: int, linea: str = "", espera_s: float | None = None, headers: dict | None = None):
        codigo = _normal(codigo)
        ico, titulo, texto = CATALOGO[codigo]
        texto = " ".join(x for x in (linea or texto, _espera(espera_s) if codigo == 429 else "") if x)
        h = {**cabeceras, "Cache-Control": "no-store", **(headers or {})}
        ruta = request.url.path
        if ruta.startswith("/estaticos/"):
            return PlainTextResponse("No encontrado" if codigo == 404 else titulo, status_code=codigo, headers=h)
        if _json(request):
            return JSONResponse({"error": titulo, "mensaje": texto}, status_code=codigo, headers=h)
        en_panel = ruta.startswith("/panel") and bool(hay_sesion(request))
        ctx = {"codigo": codigo, "ico": ico, "titulo": titulo, "texto": texto, "en_panel": en_panel, "seccion": "",
               "sin_sesion": codigo in (401, 403) and not hay_sesion(request), "reintentar": codigo in REINTENTABLES or codigo == 429,
               "dependencia": codigo in DEPENDENCIA_CAIDA, "reintento": _destino_reintento(request, en_panel)}
        return plantillas.TemplateResponse(request, "error.html", ctx, status_code=codigo, headers=h)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request, exc):
        h = {k: v for k, v in (exc.headers or {}).items() if k.lower() in ("allow", "retry-after")}
        espera = None
        if exc.status_code == 429 and h.get("Retry-After", "").isdigit():
            espera = float(h["Retry-After"])
        return pantalla(request, exc.status_code, espera_s=espera, headers=h)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request, exc):
        c = _campos(exc)
        return pantalla(request, 422, f"Revisa {c} y vuelve a intentarlo." if c else "")

    @app.exception_handler(Exception)
    async def _sin_controlar(request, exc):
        log.error("excepcion_no_controlada tipo=%s ruta=%s metodo=%s", type(exc).__name__, request.url.path, request.method)
        codigo = 504 if isinstance(exc, TimeoutError) else 503 if isinstance(exc, ConnectionError) else 500
        return pantalla(request, codigo)

    return pantalla
