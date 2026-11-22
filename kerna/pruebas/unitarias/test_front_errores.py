"""Errores del front: toda falla responde con una pantalla de Kerna (HTML) o JSON, con cabeceras de seguridad y sin trazas."""
import logging
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"

from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import principal, seguridad  # noqa: E402

from sesion_prueba import H  # noqa: E402  (cookie de la sesión de Dirección)
SECRETO = "secreto-que-no-debe-salir"


def _falla_inesperada():
    raise RuntimeError(SECRETO)


def _http(codigo):
    def f():
        raise HTTPException(codigo, detail=SECRETO, headers={"Retry-After": "130"} if codigo == 429 else None)
    return f


def _validar(n: int):
    return n


for _c in (400, 401, 403, 404, 429, 500, 502, 503, 504):
    principal.app.add_api_route(f"/_prueba/http/{_c}", _http(_c))
    principal.app.add_api_route(f"/api/_prueba/http/{_c}", _http(_c))
import re  # noqa: E402
from app import permisos  # noqa: E402
permisos.RUTAS.insert(0, (re.compile(r"^/api/_prueba/.*$"), "resumen"))   # las rutas de prueba de /api también pasan por los permisos
principal.app.add_api_route("/_prueba/boom", _falla_inesperada)
principal.app.add_api_route("/api/_prueba/boom", _falla_inesperada)
principal.app.add_api_route("/panel/demo/_prueba/boom", _falla_inesperada)
principal.app.add_api_route("/_prueba/tiempo", lambda: (_ for _ in ()).throw(TimeoutError(SECRETO)))
principal.app.add_api_route("/_prueba/conexion", lambda: (_ for _ in ()).throw(ConnectionError(SECRETO)))
principal.app.add_api_route("/_prueba/valida", _validar)


@pytest.fixture
def c():
    return TestClient(principal.app, base_url="https://t", follow_redirects=False, raise_server_exceptions=False)


def _limpio(r):
    t = r.text
    assert SECRETO not in t and "Traceback" not in t and "RuntimeError" not in t and 'File "' not in t and "pydantic" not in t.lower()


def _boton_reintentar(r):
    return " Reintentar</a>" in r.text


def _seguras(r):
    for k in principal.CABECERAS:
        assert k in r.headers, k
    assert r.headers["Cache-Control"] == "no-store"


def test_404_html_publico(c):
    r = c.get("/no-existe")
    assert r.status_code == 404 and "text/html" in r.headers["content-type"]
    assert "No encontramos esta página" in r.text and "Error 404" in r.text and 'href="/"' in r.text
    assert 'href="/panel"' not in r.text.split("</header>")[-1] and not _boton_reintentar(r)
    _seguras(r), _limpio(r)


def test_404_dentro_del_panel_con_sesion_y_sin_sesion(c):
    r = c.get("/panel/loquesea", headers=H)
    assert r.status_code == 404 and "Volver al panel" in r.text and 'aria-label="Menú lateral"' in r.text
    _seguras(r)
    r = c.get("/panel/loquesea")
    assert r.status_code == 404 and "Volver al panel" not in r.text and "Ir a la portada" in r.text


def test_panel_sin_sesion_sigue_redirigiendo(c):
    r = c.get("/panel")
    assert r.status_code == 303 and r.headers["location"] == "/acceso"
    r = c.get("/panel/demo")
    assert r.status_code == 303 and r.headers["location"] == "/acceso"


def test_estaticos_inexistentes_404_simple(c):
    r = c.get("/estaticos/inexistente.css")
    assert r.status_code == 404 and "text/plain" in r.headers["content-type"] and "<html" not in r.text
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert c.get("/estaticos/kerna.css").status_code == 200


def test_405_metodo_no_permitido(c):
    r = c.post("/salud")
    assert r.status_code == 405 and "No está disponible aquí".lower() in r.text.lower() and "allow" in r.headers
    _seguras(r), _limpio(r)
    r = c.post("/api/metricas", headers={**H})
    assert r.status_code == 405 and r.json()["error"]


def test_422_entrada_invalida_sin_detalle_de_pydantic(c):
    r = c.get("/_prueba/valida?n=abc")
    assert r.status_code == 422 and "Hay un dato que no es válido" in r.text and "«n»" in r.text
    assert "abc" not in r.text and "int_parsing" not in r.text
    _seguras(r), _limpio(r)
    r = c.get("/_prueba/valida")
    assert r.status_code == 422
    r = c.get("/api/metricas?dias=xx", headers=H)
    assert r.status_code == 422 and set(r.json()) == {"error", "mensaje"}


def test_400_y_401_403_con_enlace_al_acceso(c):
    r = c.get("/_prueba/http/400")
    assert r.status_code == 400 and "No entendimos" in r.text
    for cod in (401, 403):
        r = c.get(f"/_prueba/http/{cod}")
        assert r.status_code == cod and 'href="/acceso"' in r.text and "Entrar con tu cuenta" in r.text
        _seguras(r), _limpio(r)


def test_403_con_sesion_vuelve_al_panel(c):
    principal.app.add_api_route("/panel/demo/_prueba/403", _http(403))
    r = c.get("/panel/demo/_prueba/403", headers=H)
    assert r.status_code == 403 and "Volver al panel" in r.text and "Entrar con tu cuenta" not in r.text


def test_429_dice_cuanto_esperar(c):
    r = c.get("/_prueba/http/429")
    assert r.status_code == 429 and "Demasiados intentos" in r.text and "3 minutos" in r.text and _boton_reintentar(r)
    assert r.headers["retry-after"] == "130"
    _limpio(r)


def test_429_real_de_acceso(c, monkeypatch):
    monkeypatch.setattr(seguridad, "_fallos", {})
    for _ in range(5):
        assert c.post("/acceso", data={"clave": "mala"}).status_code == 401
    r = c.post("/acceso", data={"clave": "mala"})
    assert r.status_code == 429 and "Demasiados intentos" in r.text and "minutos" in r.text and 'href="/acceso"' in r.text
    _seguras(r)


@pytest.mark.parametrize("codigo", [502, 503, 504])
def test_dependencia_caida_con_reintentar(c, codigo):
    r = c.get(f"/_prueba/http/{codigo}")
    assert r.status_code == codigo and "Kerna no responde ahora" in r.text and _boton_reintentar(r)
    _seguras(r), _limpio(r)


def test_500_no_filtra_traza_y_registra_solo_el_tipo(c, caplog):
    with caplog.at_level(logging.ERROR, logger="kerna.front.errores"):
        r = c.get("/_prueba/boom?dato=privado")
    assert r.status_code == 500 and "Algo falló de nuestro lado" in r.text and _boton_reintentar(r)
    _seguras(r), _limpio(r)
    log = " ".join(x.getMessage() for x in caplog.records)
    assert "RuntimeError" in log and SECRETO not in log and "privado" not in log
    assert all(x.exc_info is None for x in caplog.records)


def test_500_dentro_del_panel_usa_el_marco_del_panel(c):
    r = c.get("/panel/demo/_prueba/boom", headers=H)
    assert r.status_code == 500 and 'aria-label="Menú lateral"' in r.text and "Volver al panel" in r.text
    _limpio(r)


def test_timeout_y_conexion_se_traducen(c):
    assert c.get("/_prueba/tiempo").status_code == 504
    assert c.get("/_prueba/conexion").status_code == 503


def test_json_en_api_y_con_accept(c):
    r = c.get("/api/inexistente", headers=H)
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    assert set(r.json()) == {"error", "mensaje"}
    _seguras(r)
    r = c.get("/api/_prueba/boom", headers=H)
    assert r.status_code == 500 and set(r.json()) == {"error", "mensaje"}
    _seguras(r), _limpio(r)
    r = c.get("/api/_prueba/http/503")
    assert r.status_code == 503 and r.json()["error"] == "Kerna no responde ahora"
    r = c.get("/no-existe", headers={"Accept": "application/json"})
    assert r.status_code == 404 and r.json()["error"] == "No encontramos esta página"
    r = c.get("/_prueba/boom", headers={"Accept": "application/json"})
    assert r.status_code == 500 and set(r.json()) == {"error", "mensaje"}
    _limpio(r)


def test_reintentar_solo_a_rutas_locales(c):
    r = c.get("/_prueba/http/503?dias=7")
    assert 'href="/_prueba/http/503?dias=7"' in r.text
    r = c.post("/_prueba/http/503")  # 405 con POST: no hay reintento, y de haberlo vuelve al inicio
    assert r.status_code == 405 and 'href="//' not in r.text
    r = c.get("//evil.example.com/x")
    assert 'href="//evil' not in r.text


def test_redirecciones_y_json_existentes_siguen_igual(c):
    assert c.get("/panel/reintentar").status_code == 303
    r = c.get("/api/metricas")
    assert r.status_code == 401 and "detalle" in r.json()
    r = c.post("/panel/reintentar", headers={"Accept": "application/json"}, data={})
    assert r.status_code == 401 and r.json() == {"estado": "sesion"}
