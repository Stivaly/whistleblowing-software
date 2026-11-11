"""Pruebas de las funciones puras del análisis de recall por artículo (sin red ni Qdrant)."""
import math

import numpy as np
import pytest

import analisis_recall_articulo as a


def test_azar_es_la_probabilidad_de_acertar_con_5_artículos_distintos():
    assert a.azar(144, 1) == pytest.approx(5 / 144)
    assert a.azar(10, 6) == 1.0
    assert a.azar(144, 2) == pytest.approx(1 - math.comb(142, 5) / math.comb(144, 5))


def test_clasificar_top_vecino_misma_ley_y_otra_ley():
    cands = {"207436-karin-art-211-b", "1008668-art-1"}
    leyes = {207436, 1200096}
    c = a.clasificar_top
    assert c("207436-karin-art-211-b", cands, None, leyes) == "candidato"
    assert c("207436-karin-art-211-b-bis", cands, None, leyes) == "vecino"      # mismo número base
    assert c("207436-karin-art-211-d", cands, None, leyes) == "vecino"          # mismo número base 211
    assert c("207436-karin-art-154", cands, None, leyes) == "misma_ley"
    assert c("141599-2026-12-01-art-45", cands, None, leyes) == "otra_ley"
    assert c("1008668-art-2", cands, None, {1008668}) == "vecino"                # contiguo al candidato 1


def test_por_largo_agrupa_por_cubos():
    detalle = [{"metricas": {"recall5": 0.0}, "top": ["x-art-1", "x-art-2-p1"], "candidatos": ["x-art-1", "x-art-3"]},
               {"metricas": {"recall5": 0.0}, "top": ["x-art-9"], "candidatos": ["x-art-1"]}]
    r = a.por_largo(detalle, {"x-art-1": 1000, "x-art-3": 4000})
    assert r["<1500"] == {"pares": 2, "en_top5": 0.5} and r[">=3000"] == {"pares": 1, "en_top5": 0.0}


def test_rrf_fusiona_rangos():
    s1 = np.array([[3.0, 2.0, 1.0]])
    s2 = np.array([[1.0, 3.0, 2.0]])
    f = a.rrf(s1, s2)
    assert int(np.argmax(f[0])) == 1 and f.shape == (1, 3)


def test_bm25_ordena_por_coincidencia_lexica_sin_acentos_ni_plurales_cortos():
    docs = ["El acoso sexual en el trabajo", "Modelo de prevención de delitos", "Datos personales sensibles"]
    bm = a.BM25(docs)
    p = bm.puntajes("Me acosaron sexualmente; sufro acoso en mi trabajo")
    assert int(np.argmax(p)) == 0
    assert a.tokens("Atención: ÁRBOLES y la del") == ["atenci", "arbole"]


def test_oraculo_de_ley_restringe_al_cuerpo_correcto():
    caso = {"id": "A", "ley_principal": "20.393", "articulos_candidatos": "Ley 20.393 art. 4"}
    top = [{"fragmento_id": "207436-karin-art-2", "id_norma": 207436, "score": 0.9},
           {"fragmento_id": "1008668-art-4", "id_norma": 1008668, "score": 0.8}]
    arts = {"207436-karin-art-2", "1008668-art-4"}
    assert a.oraculo_de_ley([caso], [top], arts)["recall5"] == 1.0


def test_costo_revectorizar_respeta_tokens_y_peticiones_por_minuto():
    textos = ["x" * 3000] * 20            # 20 × 900 tokens con 3,33 caracteres por token
    c = a.costo_revectorizar(textos, 3.33)
    assert c["tokens"] == 18018 and c["peticiones"] >= 3
    assert c["minutos"] == pytest.approx(c["tokens"] * 60 / 10000 / 60, rel=0.5)
