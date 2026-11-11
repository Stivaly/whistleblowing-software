"""Fixtures de Playwright (API síncrona) para las pruebas de Veridy de punta a punta.

Variables: VERIDY_URL (obligatoria), VERIDY_USUARIO y VERIDY_PASSWORD (para pruebas con sesión),
KERNA_ARTEFACTOS (carpeta donde dejar trazas, capturas y video; solo se conservan si la prueba falla).
"""
import os
import pathlib

import pytest

from playwright.sync_api import sync_playwright  # noqa: E402

ARTEFACTOS = pathlib.Path(os.environ.get("KERNA_ARTEFACTOS", "reportes/artefactos-e2e"))


def pytest_collection_modifyitems(items):
    for item in items:
        if "/e2e/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session")
def url_veridy():
    url = os.environ.get("VERIDY_URL", "").rstrip("/")
    if not url:
        pytest.skip("falta VERIDY_URL")
    return url


@pytest.fixture(scope="session")
def credenciales():
    usuario, clave = os.environ.get("VERIDY_USUARIO"), os.environ.get("VERIDY_PASSWORD")
    if not usuario or not clave:
        pytest.skip("faltan VERIDY_USUARIO y VERIDY_PASSWORD")
    return usuario, clave


@pytest.fixture(scope="session")
def navegador():
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True, args=["--no-sandbox"])
        yield nav
        nav.close()


@pytest.fixture
def pagina(navegador, request):
    nombre = request.node.nodeid.replace("/", "_").replace("::", "__")
    carpeta = ARTEFACTOS / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    ctx = navegador.new_context(record_video_dir=str(carpeta), bypass_csp=True, ignore_https_errors=False,
                                viewport={"width": 1280, "height": 800}, locale="es-CL")
    ctx.tracing.start(screenshots=True, snapshots=True)
    pag = ctx.new_page()
    pag.set_default_timeout(60_000)   # la instancia de pruebas es pequeña: 30 s no siempre alcanzan
    yield pag
    falla = getattr(request.node, "_kerna_fallo", False)
    if falla:
        pag.screenshot(path=str(carpeta / "captura.png"), full_page=True)
        ctx.tracing.stop(path=str(carpeta / "trace.zip"))
    else:
        ctx.tracing.stop()
    video = pag.video
    ctx.close()
    if not falla and video:
        # sin falla no se conserva el video (se mueve a una subcarpeta ignorada por el reporte)
        try:
            descartados = ARTEFACTOS / "_sin_falla"
            descartados.mkdir(parents=True, exist_ok=True)
            os.replace(video.path(), descartados / pathlib.Path(video.path()).name)
        except Exception:
            pass


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    resultado = yield
    informe = resultado.get_result()
    if informe.when == "call" and informe.failed:
        item._kerna_fallo = True
