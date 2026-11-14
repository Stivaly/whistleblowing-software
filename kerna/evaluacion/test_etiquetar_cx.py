import json

import pytest

import etiquetar_cx as e

CORPUS = {"207436-karin-art-2", "207436-karin-art-211-a", "1008668-art-1", "191865-karin-art-62"}


def test_parsear_deriva_leyes_secundarias_de_los_articulos():
    f = e.parsear("CX-1|si|media|21.643||CT:2,CT:211-a,18575:62|texto")
    assert f["arts"] == ["207436-karin-art-2", "207436-karin-art-211-a", "191865-karin-art-62"]
    assert f["sec"] == "18.575-18.834-18.883"
    e.validar(f, CORPUS)


def test_validar_rechaza_articulos_fuera_del_corpus_y_triage_incoherente():
    with pytest.raises(AssertionError):
        e.validar(e.parsear("CX-1|si|media|21.643||CT:999|t"), CORPUS)
    with pytest.raises(AssertionError):
        e.validar(e.parsear("CX-1|no|media|21.643||CT:2|t"), CORPUS)       # 'no' no lleva artículos
    with pytest.raises(AssertionError):
        e.validar(e.parsear("CX-1|si|media|20.393||CT:2|t"), CORPUS)       # ley principal = ley del primer artículo


def test_construir_caso_usa_formato_de_prueba3():
    c = {"id": "CX-0007", "texto_original": "relato", "particion": "afinar"}
    caso = e.construir_caso(c, e.parsear("CX-0007|si|baja|20.393||PJ:1|t"))
    assert caso["ley_principal"] == "20.393" and caso["articulos_corregidos"] == ["1008668-art-1"]
    assert caso["particion"] == "afinar" and caso["es_caso_frontera"] == "sí" and caso["triage"] == "si"
    json.dumps(caso)
