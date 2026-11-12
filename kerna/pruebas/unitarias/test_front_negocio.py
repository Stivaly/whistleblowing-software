"""Pruebas del módulo de negocio del front con tablas simuladas."""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"

from fastapi.testclient import TestClient  # noqa: E402

from app import negocio, principal  # noqa: E402

HOY = date(2026, 11, 12)


def _datos():
    cl = [{"PartitionKey": "a", "nombre": "Alfa SpA", "rubro": "X", "plan_denuncias_mes": 30, "tarifa_usd_denuncia": 0.5, "estado": "activo"},
          {"PartitionKey": "b", "nombre": "Beta SA", "rubro": "Y", "plan_denuncias_mes": 100, "tarifa_usd_denuncia": 1.0, "estado": "activo"},
          {"PartitionKey": "c", "nombre": "Baja", "plan_denuncias_mes": 10, "tarifa_usd_denuncia": 1.0, "estado": "baja"}]
    uso = [{"PartitionKey": "a", "RowKey": (HOY - timedelta(days=i)).isoformat(), "denuncias": 2, "con_sugerencia": 2, "valoradas": 1, "utiles": 1,
            "nano_in": 1_000_000, "nano_out": 0, "mini_in": 0, "mini_out": 1_000_000} for i in range(30)]
    uso.append({"PartitionKey": "b", "RowKey": (HOY - timedelta(days=20)).isoformat(), "denuncias": 5})
    return cl, uso


def test_costo_por_modelo():
    assert negocio.costo_ia({"nano_in": 1_000_000, "mini_out": 1_000_000}) == 10.10


def test_construir():
    cl, uso = _datos()
    n = negocio.construir(cl, uso, hoy=HOY)
    a, b = n["clientes"]
    assert [x["nombre"] for x in n["clientes"]] == ["Alfa SpA", "Beta SA"]  # excluye el de baja
    assert a["tot"] == 60 and a["uso_plan"] == 200 and a["estado_uso"] == "bad" and a["riesgo"] == "ok"
    assert a["ingreso"] == 30.0 and a["costo_ia"] == round(30 * 10.10, 4)
    assert b["dias_sin_uso"] == 20 and b["riesgo"] == "bad"
    assert n["totales"]["en_riesgo"] == ["Beta SA"]
    assert n["adopcion"]["utiles_pct"] == 100 and len(n["proyeccion"]["meses"]) == 6 and len(n["serie_total"]) == 30


def test_sin_clientes():
    assert negocio.construir([], []) is None


def test_api_y_panel(monkeypatch):
    cl, uso = _datos()
    monkeypatch.setattr(negocio, "_cache", {"t": 0.0, "v": None})
    monkeypatch.setattr(negocio, "_tabla", lambda nombre: type("T", (), {"list_entities": lambda s: cl if nombre == "clientes" else uso})())
    c = TestClient(principal.app)
    assert c.get("/api/negocio").status_code == 401
    h = {"Authorization": "Bearer clave-de-prueba"}
    r = c.get("/api/negocio", headers=h)
    if r.status_code == 401:  # el esquema de cabecera lo define seguridad.py
        from app import seguridad
        h = {"Cookie": f"{seguridad.COOKIE}={seguridad.emitir_cookie()}"}
        r = c.get("/api/negocio", headers=h)
    assert r.status_code == 200 and r.json()["totales"]["clientes_activos"] == 2
    p = c.get("/panel/negocio", headers=h)
    assert p.status_code == 200 and "Alfa SpA" in p.text
