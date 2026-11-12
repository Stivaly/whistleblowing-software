"""Render de cada vista del front (diseño de la maqueta v4) con datos falsos, y reglas de la capa de vistas."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"

from fastapi.testclient import TestClient  # noqa: E402

from app import consultas, evaluaciones, formato, negocio, principal, proveedores, vistas  # noqa: E402

H = {"X-Clave": "clave-de-prueba"}
M = {"dias": 7, "total_casos": 20, "casos_por_dia": [{"dia": "2026-11-10", "casos": 8, "con_sugerencia": 6}, {"dia": "2026-11-11", "casos": 12, "con_sugerencia": 11}],
     "modos": {"oficial": 15, "respaldo": 3, "local": 0, "manual": 2}, "leyes": [{"norma": "Ley 21643", "articulos": 5}],
     "valoraciones": {"util": 3, "no_util": 1, "ninguno_aplica": 0},
     "latencia": {"p50_ms": 27141, "p95_ms": 41000, "por_dia": [{"dia": "2026-11-10", "p50_ms": 27141, "p95_ms": 41000}]}, "tokens": {"entrada": 1000, "salida": 100, "total": 1100}}
EV = {"recall": {"fecha": "2026-11-12T10:00:00", "fuente": "tabla evaluaciones", "configuracion": "prueba", "dataset_casos": 10, "meta": 0.8, "por_ley": [{"ley": "Global", "recall5": 0.475, "casos": 10, "casos_articulo": 10, "recall_ley": 0.9, "ic95_inf": 0.2, "ic95_sup": 0.7}, {"ley": "Ley 21643", "recall5": 0.9, "casos": 10, "casos_articulo": 10, "recall_ley": 0.9, "ic95_inf": 0.5, "ic95_sup": 1.0}]}}


def test_formatos():
    assert formato.segundos(27141) == "27" and formato.segundos(4523) == "4,5"
    assert formato.miles(1234567) == "1.234.567" and formato.dec(1234.5, 2) == "1.234,50" and formato.uf(12.3456) == "12,35"


def test_resumen_estados_y_formato():
    v = vistas.resumen(M, EV, None, None, vistas.costo_modelos([{"modelo": "gpt-5-nano", "solicitudes": 20, "tokens_entrada_total": 1000, "tokens_salida_total": 100}]),
                       [], None, 7)
    k = {x["k"]: x for x in v["kpis"]}
    assert k["calidad"]["e"] == "bad" and k["calidad"]["v"] == "47,5"      # 0,475 frente a la meta 0,80
    assert k["tiempo"]["e"] == "bad" and k["tiempo"]["v"] == "41"          # segundos, no milisegundos
    assert v["eg"]["e"] == "bad" and v["sug_pct"] == 85
    assert v["mapas"]["t"]["k.tiempo.v"] == "41" and v["mapas"]["s"]["k.calidad"] == "bad"


def test_resumen_sin_datos_es_na():
    m = {**M, "total_casos": 0, "casos_por_dia": [], "modos": {"oficial": 0, "respaldo": 0, "local": 0, "manual": 0}, "latencia": {"p50_ms": 0, "p95_ms": 0, "por_dia": []}}
    v = vistas.resumen(m, None, None, None, None, [], None, 7)
    assert {x["k"]: x["e"] for x in v["kpis"]} == {"casos": "na", "calidad": "na", "tiempo": "na", "costo_k": "na"} and v["eg"]["e"] == "na"


@pytest.fixture
def cliente(monkeypatch):
    def falso(texto, dias):
        if "by modelo" in texto:
            return [{"modelo": "gpt-5-nano", "solicitudes": 9, "tokens_entrada_total": 9000, "tokens_salida_total": 900, "tokens_entrada_prom": 1000}]
        if '"etapa"' in texto:
            return [{"etapa": "generacion", "solicitudes": 9, "p50_ms": 18000, "p95_ms": 20000, "max_ms": 21000}]
        if "dayofweek" in texto:
            return [{"dow": 2, "hora": 10, "casos": 4}]
        if "articulo_sugerido" in texto:
            return [{"norma": "Ley 21643", "articulos": 5}]
        if "valoracion" in texto:
            return [{"valoracion": "util", "total": 4}]
        if "percentile" in texto:
            return [{"dia": "2026-11-10T00:00:00Z", "solicitudes": 3, "p50_ms": 27141, "p95_ms": 41000}]
        if "tokens_entrada_total" in texto:
            return [{"modo": "oficial", "tokens_entrada_total": 1000, "tokens_salida_total": 500}]
        if "recuperacion" in texto:
            return [{"modo": "oficial", "solicitudes": 6}, {"modo": "manual", "solicitudes": 2}]
        return [{"dia": "2026-11-10T00:00:00Z", "casos": 9, "con_sugerencia": 7}]
    monkeypatch.setattr(consultas, "filas", falso)
    monkeypatch.setattr(proveedores, "_get", lambda url: b"[]" if "google" in url else (b"<rss><channel></channel></rss>" if "azure" in url else b'{"components":[{"id":"1","name":"API","status":"operational"}],"incidents":[]}'))
    monkeypatch.setattr(evaluaciones, "cargar", lambda *a, **k: EV)
    consultas._cache.clear(); principal._extra_cache.clear(); proveedores._cache.update(t=0.0, datos=None)
    return TestClient(principal.app, follow_redirects=False)


def test_render_resumen_sin_cifras_crudas(cliente):
    t = cliente.get("/panel", headers=H).text
    assert 'class="kt s-bad"' in t and "gg-n" in t and 'id="ch-casos"' in t and "En vivo" in t and 'id="pv-azure"' in t
    assert "27141" not in t and "41000" not in t and "ms</" not in t     # nada de milisegundos
    assert "/estaticos/tailwind.css" in t and "cdn." not in t and "googleapis" not in t


def test_api_metricas_lleva_vista(cliente):
    j = cliente.get("/api/metricas?dias=7", headers=H).json()
    assert j["total_casos"] == 9 and j["vista"]["mapas"]["t"]["k.tiempo.v"] == "41" and "graficos" in j["vista"]


def test_render_portada_acceso_informe(cliente):
    assert "Entrar al panel" in cliente.get("/").text
    r = cliente.post("/acceso", data={"clave": "mala"})
    assert r.status_code == 401 and "Clave incorrecta" in r.text
    t = cliente.get("/panel/informe?dias=7", headers=H).text
    assert "Informe de gestión" in t and "descargar.pdf" in t and 'id="inf-cuerpo"' in t and 'class="card doc' not in t


def test_render_negocio(cliente, monkeypatch):
    cli = [{"PartitionKey": "a", "nombre": "Cliente A", "plan_tipo": "basico", "plan_denuncias_mes": 150, "estado": "activo"}]
    uso = [{"PartitionKey": "a", "RowKey": "2026-11-10", "denuncias": 5, "con_sugerencia": 4, "valoradas": 1, "utiles": 1, "nano_in": 1000, "nano_out": 100}]
    monkeypatch.setattr(negocio, "_tabla", lambda n: type("T", (), {"list_entities": lambda s: iter(cli if n == "clientes" else uso)})())
    negocio._cache.update(t=0.0, v=None)
    t = cliente.get("/panel/negocio?dias=30", headers=H).text
    assert "Cliente A" in t and " UF" in t and "Proyección a 5 años" in t and 'id="ch-proy"' in t
