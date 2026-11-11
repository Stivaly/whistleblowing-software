"""Pruebas de las métricas y de la regla de decisión, sin red."""
import math

import pytest

import comparar_embeddings as c
import recall_retriever as r


def cand(id_, tipo, recall, ic, ndcg=0.5, p95=None, costo=None, por_caso=None):
    return {"id": id_, "etiqueta": id_, "tipo": tipo, "recall5": recall, "ic95": ic, "ndcg10": ndcg,
            "p95_ms": p95, "costo_usd": costo, "por_caso": por_caso or {}}


@pytest.mark.pr("PR-01")
def test_metricas_caso_ndcg_mrr_precision():
    top = [{"fragmento_id": f} for f in ["x-art-9", "x-art-1-p1", "x-art-1-p2", "x-art-2", "x-art-8"]]
    m = r.metricas_caso(top, {"x-art-1", "x-art-2"})
    assert m["recall5"] == 1.0 and m["hit5"] == 1.0
    assert m["mrr"] == 0.5
    assert m["p5"] == pytest.approx(2 / 5)                 # x-art-1 cuenta una vez
    assert m["cobertura5"] == 1.0
    dcg = 1 / math.log2(3) + 1 / math.log2(5)
    assert m["ndcg10"] == pytest.approx(dcg / (1 + 1 / math.log2(3)))
    fallo = r.metricas_caso([{"fragmento_id": "x-art-7"}], {"x-art-1"})
    assert fallo["recall5"] == 0.0 and fallo["mrr"] == 0.0 and fallo["ndcg10"] == 0.0


@pytest.mark.pr("PR-01")
def test_recall_fuera_del_top5_no_cuenta_pero_si_ndcg_y_mrr():
    top = [{"fragmento_id": f"x-art-{i}"} for i in range(6)] + [{"fragmento_id": "x-art-1"}]
    m = r.metricas_caso(top, {"x-art-6"} | {"x-art-1000"}) 
    assert m["recall5"] == 0.0
    top = [{"fragmento_id": f"y-art-{i}"} for i in range(7)]
    m = r.metricas_caso(top, {"y-art-6"})
    assert m["recall5"] == 0.0 and m["mrr"] == pytest.approx(1 / 7) and m["ndcg10"] > 0


@pytest.mark.pr("PR-01")
def test_bootstrap_es_determinista_y_contiene_la_media():
    v = [1.0] * 30 + [0.0] * 30
    lo, hi = r.bootstrap_ic(v)
    assert (lo, hi) == r.bootstrap_ic(v) and lo < 0.5 < hi
    assert r.bootstrap_ic([1.0] * 10) == (1.0, 1.0)
    assert r.bootstrap_ic([]) is None


@pytest.mark.pr("PR-01")
def test_bootstrap_pareado():
    a, b = [1.0] * 40 + [0.0] * 20, [1.0] * 20 + [0.0] * 40
    res = r.bootstrap_pareado(a, b)
    assert res["diferencia"] == pytest.approx(1 / 3) and res["ic95"][0] > 0
    assert r.bootstrap_pareado(a, a)["ic95"] == [0.0, 0.0]


@pytest.mark.pr("PR-01")
def test_percentil_95():
    assert r.percentil(list(range(1, 101)), 95) == 95
    assert r.percentil([None], 95) is None


@pytest.mark.pr("PR-10")
def test_regla_diferencia_grande_sin_solapamiento_gana_recall():
    a = cand("a", "nube", 0.70, [0.60, 0.80], ndcg=0.3)
    b = cand("b", "nube", 0.50, [0.40, 0.58], ndcg=0.9)
    assert c.mejor(a, b) == (a, "recall@5")


@pytest.mark.pr("PR-10")
def test_regla_empate_por_diferencia_pequena_desempata_ndcg_luego_p95_luego_costo():
    a = cand("a", "nube", 0.60, [0.50, 0.70], ndcg=0.40)
    b = cand("b", "nube", 0.58, [0.48, 0.68], ndcg=0.45)
    assert c.mejor(a, b)[0] is b
    b["ndcg10"] = 0.40
    a["p95_ms"], b["p95_ms"] = 300, 200
    assert c.mejor(a, b)[0] is b
    b["p95_ms"] = 300
    a["costo_usd"], b["costo_usd"] = 1.0, 2.0
    ganador, criterio = c.mejor(a, b)
    assert ganador is a and "costo" in criterio


@pytest.mark.pr("PR-10")
def test_regla_intervalos_superpuestos_aunque_la_diferencia_sea_grande():
    a = cand("a", "nube", 0.70, [0.50, 0.85], ndcg=0.2)
    b = cand("b", "nube", 0.60, [0.45, 0.72], ndcg=0.6)
    assert c.mejor(a, b)[0] is b


@pytest.mark.pr("PR-10")
def test_local_es_el_mejor_abierto_aunque_gane_uno_de_nube():
    nube = cand("nube", "nube", 0.75, [0.70, 0.80])
    a1 = cand("qwen", "abierto", 0.60, [0.55, 0.65])
    a2 = cand("bge", "abierto", 0.50, [0.45, 0.55])
    d = c.decidir([a2, nube, a1])
    assert d["ganador"]["id"] == "nube" and d["local"]["id"] == "qwen" and not d["un_solo_indice"]
    d = c.decidir([nube, cand("qwen", "abierto", 0.90, [0.85, 0.95])])
    assert d["nube"]["id"] == "qwen" and d["local"]["id"] == "qwen" and d["un_solo_indice"]


@pytest.mark.pr("PR-10")
def test_informe_con_y_sin_candidatos_medidos():
    cands = [{"id": "m1", "etiqueta": "M1", "tipo": "nube", "coleccion": "col", "modelo": "m1", "modelo_consulta": "m1"},
             {"id": "m2", "etiqueta": "M2", "tipo": "abierto", "coleccion": "col2", "modelo": "m2", "modelo_consulta": "m2"}]

    def entrada(mod, col, aciertos, fecha):
        det = [{"id": f"c{i}", "metricas": {"recall5": a}} for i, a in enumerate(aciertos)]
        return {"fecha": fecha, "commit": "abc", "dataset": {"sha256": "d" * 64},
                "parametros": {"campo_consulta": "texto_original", "coleccion": col, "modelo": mod, "modelo_consulta": mod,
                               "mapeo": "concordancia"},
                "por_ley": {"global": {"recall_ley": 0.9, "casos_articulo": len(aciertos)},
                            "20.393": {"recall_ley": 0.9, "casos_articulo": len(aciertos)}},
                "metricas_articulo": {"global": {"recall5": sum(aciertos) / len(aciertos), "recall5_ic95": [0.2, 0.9],
                                                 "ndcg10": 0.5, "mrr": 0.4, "p5": 0.2, "hit5": 0.5, "casos_articulo": len(aciertos)},
                                      "20.393": {"recall5": 0.5, "ndcg10": 0.5}},
                "detalle": det}

    registro = [entrada("m1", "col", [1.0] * 6 + [0.0] * 4, "2026-11-11T00:00:00+00:00")]
    md = c.generar_informe(registro, cands, "texto_original")
    assert "M2: sin corrida registrada" in md and "**Nube**: M1" in md and "Ningún abierto" not in md
    registro.append(entrada("m2", "col2", [1.0] * 2 + [0.0] * 8, "2026-11-11T01:00:00+00:00"))
    md = c.generar_informe(registro, cands, "texto_original")
    assert "| m1 | m2 | 10 |" in md and "**Local**" in md and "Ningún candidato llega" in md
    assert "Sin candidatos medidos" in c.generar_informe([], cands, "texto_original")


def test_corridas_sin_mapeo_cuentan_como_directo_y_el_informe_muestra_antes_y_despues():
    cand = {"id": "m1", "etiqueta": "M1", "tipo": "nube", "coleccion": "col", "modelo": "m1", "modelo_consulta": "m1"}

    def entrada(mapeo, aciertos, fecha):
        par = {"campo_consulta": "texto_original", "coleccion": "col", "modelo": "m1", "modelo_consulta": "m1"}
        if mapeo:
            par["mapeo"] = mapeo
        n = len(aciertos)
        return {"fecha": fecha, "commit": "abc", "dataset": {"sha256": "d" * 64}, "parametros": par,
                "por_ley": {"global": {"recall_ley": 0.9, "casos_articulo": n}},
                "metricas_articulo": {"global": {"recall5": sum(aciertos) / n, "recall5_ic95": [0.1, 0.9], "ndcg10": 0.5,
                                                 "mrr": 0.4, "p5": 0.2, "hit5": 0.5, "casos_articulo": n,
                                                 "hit8": 0.6, "hit10": 0.7, "cobertura5": 0.3, "cobertura8": 0.4,
                                                 "cobertura10": 0.5}},
                "detalle": [{"id": f"c{i}", "metricas": {"recall5": a}} for i, a in enumerate(aciertos)]}

    antes = entrada(None, [1.0, 0.0, 0.0, 0.0], "2026-11-11T00:00:00+00:00")        # corrida vieja: sin parámetro
    despues = entrada("concordancia", [1.0, 1.0, 0.0, 0.0], "2026-11-12T00:00:00+00:00")
    assert c.ultima_corrida([antes, despues], cand, "texto_original", mapeo="directo") is antes
    assert c.ultima_corrida([antes, despues], cand, "texto_original") is despues
    md = c.generar_informe([antes, despues], [cand], "texto_original")
    assert "| M1 | 0.250 | 4 | 0.500 | 4 |" in md and "hit@8" in md
