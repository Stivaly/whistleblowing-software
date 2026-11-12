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
    cl = [{"PartitionKey": "a", "nombre": "Alfa SpA", "rubro": "X", "plan_denuncias_mes": 30, "plan_tipo": "basico", "estado": "activo"},
          {"PartitionKey": "b", "nombre": "Beta SA", "rubro": "Y", "plan_denuncias_mes": 100, "plan_tipo": "pro", "estado": "activo"},
          {"PartitionKey": "c", "nombre": "Baja", "plan_denuncias_mes": 10, "estado": "baja"}]
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
    # Básico: 1.483.200 pesos al año = 37,08 UF (UF a 40.000); 30 días = 30/365 del año.
    assert a["plan_tipo"] == "Básico" and a["tarifa_uf_anual"] == 37.08
    assert a["ingreso"] == round(37.08 * 30 / 365, 2) == 3.05
    # IA medida: 30 días x (1 M de entrada nano a 0,10 + 1 M de salida mini a 10) = 303 USD; muy sobre la cuota del plan (36.000 pesos al año).
    assert n["totales"]["costo_ia_bruto"] > a["costo_ia"]
    assert a["costo_ia"] == round(36000 / 40000 * 30 / 365, 4)  # tope de cuota prorrateado
    assert b["dias_sin_uso"] == 20 and b["riesgo"] == "bad"
    assert n["totales"]["en_riesgo"] == ["Beta SA"]
    assert n["adopcion"]["utiles_pct"] == 100 and len(n["proyeccion"]["anios"]) == 5 and len(n["serie_total"]) == 30


def test_resultado_con_todos_los_costos():
    """Un solo cliente Pro sin uso de IA, 365 días en el año 1: cada partida se verifica a mano (cap. 25)."""
    cl = [{"PartitionKey": "p", "nombre": "P", "plan_tipo": "pro", "plan_denuncias_mes": 300, "estado": "activo", "origen_veridy": True}]
    n = negocio.construir(cl, [], hoy=HOY, dias=365)
    t, c = n["totales"], n["clientes"][0]
    assert c["tarifa_uf_anual"] == round(2719200 / 40000, 2) == 67.98 and t["ingreso"] == 67.98
    # costo de servir Pro 494.400 pesos = 12,36 UF (sin IA usada: infraestructura y soporte 410.400 pesos = 10,26 UF)
    assert t["costo_servir"] == 10.26 and t["margen_bruto"] == round(67.98 - 10.26, 2)
    assert t["participacion_veridy"] == round(0.30 * (67.98 - 10.26), 2) == 17.32
    assert t["costos_fijos"] == round(4315381 / 40000, 2) == 107.88
    assert t["depreciacion"] == round(2865844.5 / 40000, 2) and t["interes"] == round(2212371.78 / 40000, 2)
    assert t["margen_operativo"] == round(67.98 - 10.26 - 17.316 - 107.88, 2) and t["margen_operativo"] < 0
    assert t["impuesto"] == 0 and t["utilidad"] == t["resultado_antes_impuesto"] < t["margen_operativo"]


def test_proyeccion_es_la_del_capitulo():
    n = negocio.construir(_datos()[0], _datos()[1], hoy=HOY)
    p = n["proyeccion"]
    assert [a["ventas"] for a in p["anios"]][0] == round(25523400 / 40000, 2)
    assert p["tasa_descuento_pct"] == 25.0 and p["tir_pct"] == 66.5 and p["indice_rentabilidad"] == 2.59 and p["recuperacion_anio"] == 3
    assert p["van"] == round(27932860 / 40000, 2)


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
