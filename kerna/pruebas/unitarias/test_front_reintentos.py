"""Pruebas del reintento manual del panel: resumen, solicitud atómica, CSRF, sesión y doble clic."""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"

from azure.core.exceptions import ResourceExistsError, ResourceModifiedError, ResourceNotFoundError  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import consultas, principal, proveedores, reintentos, seguridad  # noqa: E402


class TablaFalsa:
    """Imita la tabla: create falla si existe; update con etag falla si cambió."""
    def __init__(self):
        self.fila, self.version = None, 0

    def get_entity(self, pk, rk):
        if self.fila is None:
            raise ResourceNotFoundError("no")
        e = dict(self.fila); e = type("E", (dict,), {})(e); e.metadata = {"etag": str(self.version)}
        return e

    def create_entity(self, ent):
        if self.fila is not None:
            raise ResourceExistsError("existe")
        self.fila, self.version = dict(ent), 1

    def update_entity(self, ent, mode="merge", etag=None, match_condition=None):
        if etag != str(self.version):
            raise ResourceModifiedError("cambió")
        self.fila, self.version = dict(ent), self.version + 1


def test_solicitar_es_atomica_y_el_doble_clic_no_dispara_dos_veces():
    t = TablaFalsa()
    assert reintentos.solicitar(t) == "solicitado"
    assert reintentos.solicitar(t) == "ya_solicitado"
    assert reintentos.estado_solicitud(t)["estado"] == "solicitado"
    t.fila["estado"] = "atendido"                        # el conector la atendió
    assert reintentos.solicitar(t) == "solicitado"       # se puede pedir otra vez


def test_solicitar_pierde_la_carrera_si_otro_cambio_la_fila():
    t = TablaFalsa(); reintentos.solicitar(t); t.fila["estado"] = "atendido"
    original = t.update_entity
    def carrera(*a, **k):
        t.version += 1                                   # otro proceso escribió entre la lectura y el reemplazo
        return original(*a, **k)
    t.update_entity = carrera
    assert reintentos.solicitar(t) == "ya_solicitado"


def test_resumen_en_lenguaje_simple_y_sin_identificadores():
    def ej(texto, dias):
        if "conector_reintento" in texto:
            return [{"evento": "conector_reintento", "eventos": 3, "ultimo": "2026-11-12T09:00:00Z"}, {"evento": "conector_reproceso", "eventos": 1, "ultimo": "2026-11-12T10:00:00Z"}]
        return [{"motivo": "cadena_agotada", "casos": 5}, {"motivo": "validacion_fallida", "casos": 2}]
    r = reintentos.resumen(ejecutar=ej, ahora=datetime(2026, 11, 12, 12, tzinfo=timezone.utc))
    assert r["reintentables"] == 4 and r["total"] == 7
    assert r["motivos"][0]["texto"] == "Los modelos de IA no estaban disponibles" and r["motivos"][1]["se_reintenta"] is False
    assert r["proximo_auto"].startswith("2026-11-13T09:00")
    assert not any("ref" in k for m in r["motivos"] for k in m)


@pytest.fixture
def cliente(monkeypatch):
    t = TablaFalsa()
    monkeypatch.setattr(reintentos, "_tabla", lambda: t)
    monkeypatch.setattr(consultas, "filas", lambda x, d: [{"motivo": "cadena_agotada", "casos": 2, "evento": "conector_reintento", "eventos": 1, "ultimo": "2026-11-12T09:00:00Z"}])
    monkeypatch.setattr(proveedores, "_get", lambda u: (_ for _ in ()).throw(TimeoutError()))
    consultas._cache.clear(); proveedores._cache.update(t=0.0, datos=None)
    c = TestClient(principal.app, follow_redirects=False)
    c.tabla = t
    return c


H = {"X-Clave": "clave-de-prueba"}


def token():
    return seguridad.token_csrf({})


def test_post_exige_sesion_csrf_y_mismo_origen(cliente):
    assert cliente.post("/panel/reintentar", data={"csrf": token()}).status_code == 401
    assert cliente.post("/panel/reintentar", headers=H, data={"csrf": "malo"}).status_code == 403
    assert cliente.post("/panel/reintentar", headers=H, data={}).status_code == 403
    assert cliente.post("/panel/reintentar", headers={**H, "Origin": "https://otro.example"}, data={"csrf": token()}).status_code == 403
    assert cliente.post("/panel/reintentar", headers={**H, "Sec-Fetch-Site": "cross-site"}, data={"csrf": token()}).status_code == 403
    assert cliente.tabla.fila is None                     # nada se escribió


def test_flujo_confirmar_pedir_y_doble_clic(cliente):
    assert cliente.get("/panel/reintentar").status_code == 303   # sin sesión: al acceso
    c = cliente.get("/panel/reintentar", headers=H)
    assert c.status_code == 200 and "Sí, reintentar" in c.text and token() in c.text
    r = cliente.post("/panel/reintentar", headers=H, data={"csrf": token()})
    assert r.status_code == 303 and r.headers["location"] == "/panel?reintento=solicitado"
    r2 = cliente.post("/panel/reintentar", headers=H, data={"csrf": token()})
    assert r2.headers["location"] == "/panel?reintento=ya_solicitado"
    p = cliente.get("/panel?reintento=ya_solicitado", headers=H)
    assert "Pedido en curso" in p.text and "Ya estaba pedido" in p.text and "Reintentar ahora" not in p.text


def test_panel_muestra_bloque_y_no_se_rompe_si_la_tabla_falla(cliente, monkeypatch):
    p = cliente.get("/panel", headers=H)
    assert "Casos esperando reintento" in p.text and "Reintentar ahora" in p.text and "Los modelos de IA no estaban disponibles" in p.text
    monkeypatch.setattr(reintentos, "_tabla", lambda: (_ for _ in ()).throw(RuntimeError("sin acceso")))
    p = cliente.get("/panel", headers=H)
    assert p.status_code == 200 and "Casos esperando reintento" not in p.text
    assert cliente.post("/panel/reintentar", headers=H, data={"csrf": token()}).headers["location"] == "/panel?reintento=error"
