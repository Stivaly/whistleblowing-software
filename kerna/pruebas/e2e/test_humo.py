"""Prueba de humo: la página de inicio de Veridy carga."""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.pr("PR-39"), pytest.mark.rnf("disponibilidad-veridy")]


def test_inicio_carga(pagina, url_veridy):
    respuesta = pagina.goto(url_veridy + "/", wait_until="domcontentloaded")
    assert respuesta is not None and respuesta.status == 200
    pagina.wait_for_selector("app-root", state="attached")
    # la aplicación Angular termina de dibujar algo dentro de app-root
    pagina.wait_for_function("document.querySelector('app-root') && document.querySelector('app-root').innerText.trim().length > 0")
    assert pagina.title().strip() != ""
