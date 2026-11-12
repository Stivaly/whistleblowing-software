"""Pruebas del front web de Kerna AI (kerna/front) con Log Analytics simulado."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"

from fastapi.testclient import TestClient  # noqa: E402

from app import consultas, principal, seguridad  # noqa: E402


def falso(texto, dias):
    if "articulo_sugerido" in texto:
        return [{"norma": "Ley 21643", "articulos": 5}, {"norma": "Ley 19628", "articulos": 2}]
    if "front_valoraciones" in texto or "clasificacion_auditor" in texto:
        return [{"valoracion": "util", "total": 4}, {"valoracion": "no_util", "total": 1}, {"valoracion": "ninguno_aplica", "total": 2}]
    if "percentile" in texto:
        return [{"dia": "2026-11-10T00:00:00Z", "solicitudes": 3, "p50_ms": 4000.4, "p95_ms": 9000.2}]
    if "tokens_entrada_total" in texto:
        return [{"modo": "oficial", "tokens_entrada_total": 1000, "tokens_salida_total": 500}]
    if "recuperacion" in texto:
        return [{"modo": "oficial", "recuperacion": "nube", "solicitudes": 6}, {"modo": "respaldo", "recuperacion": "nube", "solicitudes": 1},
                {"modo": "manual", "recuperacion": "nube", "solicitudes": 2}]
    return [{"dia": "2026-11-10T00:00:00Z", "casos": 9, "con_sugerencia": 7}]


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(consultas, "filas", falso)
    consultas._cache.clear()
    return TestClient(principal.app, follow_redirects=False)


def test_kql_reemplaza_rango():
    assert "ago(30d)" in consultas.kql("casos", 30) and "ago(7d)" not in consultas.kql("casos", 30)


def test_metricas_agregadas():
    m = consultas.metricas(7, ejecutar=falso)
    assert m["total_casos"] == 9 and m["modos"] == {"oficial": 6, "respaldo": 1, "local": 0, "manual": 2}
    assert m["leyes"][0] == {"norma": "Ley 21643", "articulos": 5}
    assert m["valoraciones"] == {"util": 4, "no_util": 1, "ninguno_aplica": 2}
    assert m["latencia"]["p50_ms"] == 4000 and m["tokens"]["total"] == 1500


def test_no_expone_identificadores():
    texto = str(consultas.metricas(7, ejecutar=falso))
    assert "id_solicitud" not in texto and "ref_opaca" not in texto


def test_portada_publica(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "21.643" in r.text and "20.393" in r.text and "no un dictamen" in r.text
    assert "prefers-reduced-motion" in cliente.get("/estaticos/kerna.css").text


def test_panel_exige_autenticacion(cliente):
    assert cliente.get("/panel").status_code == 303
    assert cliente.get("/api/metricas").status_code == 401
    assert cliente.get("/api/metricas", headers={"X-Clave": "mala"}).status_code == 401


def test_api_con_clave(cliente):
    r = cliente.get("/api/metricas?dias=30", headers={"X-Clave": "clave-de-prueba"})
    assert r.status_code == 200 and r.json()["dias"] == 30


def test_acceso_cookie_y_panel(cliente):
    assert cliente.post("/acceso", data={"clave": "mala"}).status_code == 401
    r = cliente.post("/acceso", data={"clave": "clave-de-prueba"})
    assert r.status_code == 303 and "httponly" in r.headers["set-cookie"].lower()
    p = cliente.get("/panel", cookies={seguridad.COOKIE: seguridad.emitir_cookie()})
    assert p.status_code == 200 and "Ley 21643" in p.text and "casos procesados" in p.text


def test_panel_con_error_de_consulta(monkeypatch):
    def roto(d, ejecutar=None):
        raise RuntimeError("x")
    monkeypatch.setattr(consultas, "metricas", roto)
    c = TestClient(principal.app, follow_redirects=False)
    p = c.get("/panel", cookies={seguridad.COOKIE: seguridad.emitir_cookie()})
    assert p.status_code == 200 and "Sin conexión con Log Analytics" in p.text


def test_referencia_keyvault_sin_resolver_no_sirve(monkeypatch):
    monkeypatch.setenv("FRONT_CLAVE", "@Microsoft.KeyVault(SecretUri=x)")
    assert not seguridad.clave_valida("@Microsoft.KeyVault(SecretUri=x)")


def test_modo_entra(monkeypatch):
    monkeypatch.setenv("FRONT_AUTH", "entra")
    assert not seguridad.autorizado({}, {}) and seguridad.autorizado({"x-ms-client-principal-id": "abc"}, {})
