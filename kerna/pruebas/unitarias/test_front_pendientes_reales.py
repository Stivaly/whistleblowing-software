"""Lo pendiente del Resumen sale del estado real del conector (fila `conector`); la telemetría acumulada solo es el respaldo y se dice."""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"

from fastapi.testclient import TestClient  # noqa: E402

from app import consultas, principal, proveedores, reintentos, vistas  # noqa: E402
from test_front_reintentos import H, TablaFalsa  # noqa: E402

AHORA = datetime(2026, 11, 13, 6, 20, tzinfo=timezone.utc)
TELE = {"total": 299, "reintentables": 206, "proximo_auto": None, "ultimo_reintento": None,
        "motivos": [{"motivo": "cadena_agotada", "texto": "Los modelos de IA no estaban disponibles", "casos": 201, "se_reintenta": True},
                    {"motivo": "tiempo_agotado", "texto": "El análisis tardó más de lo permitido", "casos": 98, "se_reintenta": True}]}


def fila(seg=10, **kw):
    return {"actualizado_en": (AHORA - timedelta(seconds=seg)).strftime("%Y-%m-%dT%H:%M:%SZ"), "casos": 117, "archivados": 62, "completado": 116,
            "en_revision_manual": 3, "error": 1, "nuevo": 0, "pendiente": 0, **kw}


def test_con_fila_reciente_manda_el_estado_del_conector():
    r = reintentos.con_estado_real(TELE, fila(), AHORA)
    assert r["fuente"] == "conector" and r["reintentables"] == 4 and r["total"] == 4
    assert [(m["texto"], m["casos"]) for m in r["motivos"]] == [("En revisión manual", 3), ("Con error al procesar", 1)]
    assert sum(m["casos"] for m in r["motivos"]) == r["total"]                 # el desglose siempre cuadra con el total
    assert r["con_sugerencia"] == 113 and "206" not in str(r) and "201" not in str(r)
    assert "Estado actual de los casos en Veridy" in reintentos.ayuda_pendientes(r, 7, AHORA)


def test_sin_pendientes_reales_no_hereda_las_cifras_de_la_telemetria():
    r = reintentos.con_estado_real(TELE, fila(en_revision_manual=0, error=0), AHORA)
    assert r["fuente"] == "conector" and r["reintentables"] == 0 and r["motivos"] == []


@pytest.mark.parametrize("c", [None, fila(seg=900), {"casos": 5}])
def test_fila_ausente_o_vieja_usa_la_telemetria_y_lo_dice(c):
    r = reintentos.con_estado_real(TELE, c, AHORA)
    assert r["fuente"] == "telemetria" and r["reintentables"] == 206 and len(r["motivos"]) == 2
    a = reintentos.ayuda_pendientes(r, 7, AHORA)
    assert "Estimado con la telemetría" in a and "no está disponible" in a
    if c and "actualizado_en" in c:
        assert "hace 15 min" in a


def test_sin_telemetria_pero_con_conector_igual_hay_datos_reales():
    assert reintentos.con_estado_real(None, fila(), AHORA)["reintentables"] == 4
    assert reintentos.con_estado_real(None, None, AHORA) is None


def _V():
    base = {"total": 425, "e_sug": "bad", "sug_pct": 29, "proveedores": [], "eg": {"e": "warn"}, "modos": [
        {"k": "oficial", "n": 111}, {"k": "respaldo", "n": 15}, {"k": "manual", "n": 299}], "kpis": [], "valoraciones": [], "n_val": 0, "etapas": [],
        "rapidez": {"hay": False}, "graficos": {"heat": [], "casos": {"labels": []}}, "aciertos": []}
    return base


def test_frase_distingue_periodo_de_ahora_y_no_contradice_el_bloque(monkeypatch):
    monkeypatch.setattr(vistas, "_kb", lambda *a, **k: {})
    V = _V(); V["kpis"] = [{"k": k} for k in ("calidad", "tiempo", "costo_k")]
    for fuente, n, esperado in (("conector", 4, "Ahora, <em"), ("telemetria", 206, "Según la telemetría")):
        P = vistas.presentacion_resumen(V, {"r": {"reintentables": n, "fuente": fuente}}, 7)
        t = str(P["frase"])
        assert "En 7 días, <em" in t and "29 %" in t and esperado in t and f">{n}<" in t
        assert "425 denuncias en 7 días por modo" in P["diag"] and "Pasó a revisión manual" in P["diag"]
    P = vistas.presentacion_resumen(V, {"r": {"reintentables": 0, "fuente": "conector"}}, 7)
    assert "Ahora no hay casos esperando reintento" in str(P["frase"]) and "esperan reintento" not in str(P["frase"])


@pytest.fixture
def cliente(monkeypatch):
    t = TablaFalsa()
    monkeypatch.setattr(reintentos, "_tabla", lambda: t)
    monkeypatch.setattr(consultas, "filas", lambda x, d: [{"motivo": "cadena_agotada", "casos": 201, "evento": "conector_reintento", "eventos": 1, "ultimo": "2026-11-12T09:00:00Z"}])
    monkeypatch.setattr(proveedores, "_get", lambda u: (_ for _ in ()).throw(TimeoutError()))
    consultas._cache.clear(); proveedores._cache.update(t=0.0, datos=None)
    from app import cache
    cache.vaciar()
    return TestClient(principal.app, follow_redirects=False), t


def test_el_panel_usa_el_estado_real_y_marca_la_estimacion(cliente, monkeypatch):
    c, t = cliente
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    monkeypatch.setattr(reintentos, "estado_conector", lambda tabla=None: fila() | {"actualizado_en": ahora})
    p = c.get("/panel", headers=H).text
    assert "Ahora · en espera" in p and "En revisión manual" in p and "Con error al procesar" in p and "201" not in p.split('id="rei"')[1].split("</section>")[0]
    assert 'data-n="4"' in p and "Estado actual de los casos en Veridy" in p
    from app import cache
    cache.vaciar()
    monkeypatch.setattr(reintentos, "estado_conector", lambda tabla=None: None)
    p = c.get("/panel", headers=H).text
    assert "Estimado · en espera" in p and "Los modelos de IA no estaban disponibles" in p and "Estimado con la telemetría" in p
