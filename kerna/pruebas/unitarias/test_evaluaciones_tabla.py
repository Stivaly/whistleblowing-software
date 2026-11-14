"""Escritura (kerna/evaluacion/tabla_evaluaciones.py) y lectura (front/app/evaluaciones.py) de la tabla `evaluaciones`, con tabla simulada."""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "evaluacion"))
sys.path.insert(0, str(RAIZ / "front"))

import tabla_evaluaciones as t  # noqa: E402
from app import evaluaciones  # noqa: E402


class TablaFalsa:
    def __init__(self):
        self.filas = {}

    def upsert_entity(self, e, mode="merge"):
        self.filas[(e["PartitionKey"], e["RowKey"])] = e

    def list_entities(self):
        return list(self.filas.values())


RECALL = {"fecha": "2026-11-11T10:00:00+00:00", "commit": "abc+cambios",
          "parametros": {"campo_consulta": "texto_original", "modelo": "m", "meta": 0.8, "particion": "desarrollo", "coleccion": "normativa_cl"}, "dataset": {"casos": 113},
          "corpus_articulos_vigentes": 144, "por_ley": {"global": {"casos": 91, "recall_ley": 0.9}, "20.393": {"casos": 24, "recall_ley": 0.8}},
          "metricas_articulo": {"global": {"recall5": 0.4, "ndcg10": 0.3, "casos_articulo": 61, "recall5_ic95": [0.3, 0.5]},
                                "20.393": {"recall5": 0.0, "casos_articulo": 10, "recall5_ic95": [0.0, 0.0]}}}


def test_filas_recall_y_idempotencia():
    tabla = TablaFalsa()
    assert t.subir(t.filas_recall(RECALL), tabla) == 3
    assert t.subir(t.filas_recall(RECALL), tabla) == 3 and len(tabla.filas) == 3
    f = next(x for x in tabla.filas.values() if x["metrica"] == "recall5" and x["ambito"] == "global")
    assert f["valor"] == 0.4 and f["commit"] == "abc+cambios" and json.loads(f["parametros"])["meta"] == 0.8


def test_subir_no_lanza_si_falla(capsys):
    class Rota:
        def upsert_entity(self, *a, **k):
            raise RuntimeError("403")
    assert t.subir(t.filas_recall(RECALL), Rota()) == 0
    assert "no se escribió" in capsys.readouterr().err


def test_sin_cuenta_no_escribe(monkeypatch):
    monkeypatch.delenv("KERNA_TABLAS_URL", raising=False)
    monkeypatch.setattr(t, "url_cuenta", lambda: None)
    assert t.subir(t.filas_recall(RECALL)) == 0


def test_backfill_del_registro(tmp_path):
    (tmp_path / "recall_retriever.jsonl").write_text(json.dumps(RECALL) + "\n")
    (tmp_path / "anonimizador_2026-11-11.json").write_text(json.dumps(
        {"n_casos": 5, "casos_con_etiqueta": {"RUT": 2}, "casos_con_deteccion_del_tipo": {"RUT": 1},
         "apariciones_independientes": {"RUT": {"total": 4, "ocultas": 3}}}))
    (tmp_path / "pruebas-x.json").write_text(json.dumps(
        {"commit": "abc", "fecha_utc": "2026-11-11T20:00:00Z", "ok": True, "capas": {"unitarias": {"total": 3, "pasadas": 3, "fallidas": 0, "omitidas": 0}}}))
    tabla = TablaFalsa()
    assert t.backfill(tmp_path, tabla) == 3 + 2 + 1
    assert {k[0] for k in tabla.filas} == {"recall_retriever", "anonimizador", "pruebas"}


def test_lector_reconstruye_el_modelo_del_informe(tmp_path):
    tabla = TablaFalsa()
    (tmp_path / "recall_retriever.jsonl").write_text(json.dumps(RECALL) + "\n")
    (tmp_path / "pruebas-x.json").write_text(json.dumps(
        {"commit": "abc", "fecha_utc": "2026-11-11T20:00:00Z", "capas": {"unitarias": {"total": 3, "pasadas": 3, "fallidas": 0, "omitidas": 0}}}))
    t.backfill(tmp_path, tabla)
    ev = evaluaciones.cargar(tabla)
    assert ev["recall"]["por_ley"][0]["ley"] == "Global" and ev["recall"]["por_ley"][0]["recall5"] == 0.4
    assert ev["recall"]["por_ley"][0]["ic95_inf"] == 0.3 and ev["corpus_articulos"] == 144
    assert ev["pruebas"]["capas"]["unitarias"]["pasadas"] == 3 and len(ev["serie"]) == 1


def test_lector_tabla_vacia_devuelve_none():
    assert evaluaciones.cargar(TablaFalsa()) is None


def test_lector_usa_la_marca_vigente_y_solo_desarrollo(tmp_path):
    tabla = TablaFalsa()
    otra = {**RECALL, "fecha": "2026-11-12T10:00:00+00:00",
            "parametros": {**RECALL["parametros"], "particion": "prueba"},
            "metricas_articulo": {"global": {"recall5": 0.9, "casos_articulo": 10, "recall5_ic95": [0.8, 1.0]}}}
    nueva = {**RECALL, "fecha": "2026-11-14T10:00:00+00:00", "parametros": {**RECALL["parametros"], "coleccion": "normativa_cl_x_e"},
             "metricas_articulo": {"global": {"recall5": 0.7, "casos_articulo": 42, "recall5_ic95": [0.6, 0.8]}}}
    for r in (RECALL, otra, nueva):
        t.subir(t.filas_recall(r), tabla)
    assert evaluaciones.cargar(tabla)["recall"]["por_ley"][0]["recall5"] == 0.4  # sin marca: normativa_cl, solo desarrollo
    tabla.upsert_entity({"PartitionKey": "vigente", "RowKey": "desarrollo", "corrida": nueva["fecha"]})
    r = evaluaciones.cargar(tabla)["recall"]
    assert r["set"] == "desarrollo" and r["por_ley"][0]["recall5"] == 0.7
