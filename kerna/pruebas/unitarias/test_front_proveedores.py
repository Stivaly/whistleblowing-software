"""Pruebas de la disponibilidad por proveedor con respuestas guardadas de cada fuente (sin red)."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"

from fastapi.testclient import TestClient  # noqa: E402

from app import consultas, principal, proveedores as pv  # noqa: E402

DATOS = Path(__file__).resolve().parents[1] / "datos" / "estado_proveedores"


def guardado(nombre: str) -> str:
    return (DATOS / nombre).read_text(encoding="utf-8")


def falso(azure="azure_operativo.xml", google="google_operativo.json", voyage="voyage_operativo.json"):
    por_url = {pv.URL_AZURE: azure, pv.URL_GOOGLE: google, pv.URL_VOYAGE: voyage}

    def get(url):
        v = por_url[url]
        if v is None:
            raise TimeoutError("fuente caída")
        return guardado(v).encode()
    return get


def estados(**kw):
    return {p["id"]: p["estado"] for p in pv.estado_proveedores(falso(**kw))["proveedores"]}


def test_todo_operativo():
    r = pv.estado_proveedores(falso())
    assert {p["estado"] for p in r["proveedores"]} == {"operativo"} and r["general"]["estado"] == "operativo"


def test_azure_incidente_en_nuestra_region_deja_caido_o_degradado_y_refleja_general():
    r = pv.estado_proveedores(falso(azure="azure_incidente_nuestro.xml"))
    a = r["proveedores"][0]
    assert a["estado"] == "caido" and "Gemini" in a["mensaje"] and a["desde"].startswith("2026-11-12T14:00")
    assert r["general"]["estado"] == "caido" and "principal" in r["general"]["texto"]


def test_azure_incidente_de_otra_region_o_servicio_no_afecta():
    assert estados(azure="azure_incidente_otra_region.xml")["azure"] == "operativo"


def test_google_incidente_global_afecta_y_el_de_otra_region_no():
    assert estados(google="google_incidente_nuestro.json")["gemini"] == "degradado"
    assert estados(google="google_incidente_otra_region.json")["gemini"] == "operativo"


def test_voyage_caida_de_api_y_otro_componente():
    assert estados(voyage="voyage_incidente_nuestro.json")["voyage"] == "caido"
    assert estados(voyage="voyage_incidente_otro_componente.json")["voyage"] == "operativo"


def test_fuente_caida_o_basura_es_sin_informacion_y_no_rompe():
    r = estados(azure=None, google=None, voyage=None)
    assert set(r.values()) == {"sin_informacion"}
    por_basura = pv.estado_proveedores(lambda u: b"<html>no es el formato</html>")
    assert {p["estado"] for p in por_basura["proveedores"]} == {"sin_informacion"}


def test_regiones():
    assert pv._region_cuenta("Impacted region: West US", "West US")
    assert not pv._region_cuenta("Impacted region: West US 2", "West US")
    assert pv._region_cuenta("All regions affected", "West US")
    assert not pv._region_cuenta("Sweden Central only", "West US")


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(consultas, "filas", lambda t, d: [])
    pv._cache.update(t=0.0, datos=None)
    return TestClient(principal.app, follow_redirects=False)


def test_endpoint_y_panel_con_fuentes_caidas(cliente, monkeypatch):
    def caida(url):
        raise TimeoutError
    monkeypatch.setattr(pv, "_get", caida)
    h = {"X-Clave": "clave-de-prueba"}
    assert cliente.get("/api/proveedores").status_code == 401
    r = cliente.get("/api/proveedores", headers=h)
    assert r.status_code == 200 and r.json()["proveedores"][0]["estado"] == "sin_informacion"
    p = cliente.get("/panel", headers=h)
    assert p.status_code == 200 and "Sin información" in p.text


def test_panel_muestra_proveedor_caido(cliente, monkeypatch):
    monkeypatch.setattr(pv, "_get", lambda u: guardado({pv.URL_AZURE: "azure_incidente_nuestro.xml", pv.URL_GOOGLE: "google_operativo.json", pv.URL_VOYAGE: "voyage_operativo.json"}[u]).encode())
    p = cliente.get("/panel", headers={"X-Clave": "clave-de-prueba"})
    assert "Caído" in p.text and "Azure OpenAI" in p.text and "¿Está todo bien?" not in p.text
