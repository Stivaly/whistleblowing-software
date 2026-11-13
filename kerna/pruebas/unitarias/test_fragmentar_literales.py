"""Partición de artículos-lista por literal y construcción de las colecciones del experimento de enriquecimiento."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline_bcn"))
from fragmentar_literales import partir_literales  # noqa: E402
from indexar_enriquecido import construir  # noqa: E402

LISTA = "Artículo 84.- Prohibiciones:\n\n" + "\n\n".join(f"{c}) " + ("Texto del literal. " * 15) for c in "abcdefgh")


def test_parte_lista_larga_y_conserva_introduccion():
    intro, lits = partir_literales(LISTA)
    assert intro.startswith("Artículo 84") and [e for e, _ in lits] == list("abcdefgh")
    assert lits[2][1].startswith("c) Texto")


def test_no_parte_textos_cortos_ni_con_pocos_literales():
    assert partir_literales("Artículo 1.- x\n\na) uno\n\nb) dos")[1] == []
    assert partir_literales(("a) " + "x " * 600 + "\n\nb) y"))[1] == []


def test_ignora_incisos_numerados_dentro_de_un_literal():
    t = LISTA.replace("c) Texto", "c) 1) Primero\n2) Segundo. Texto")
    assert [e for e, _ in partir_literales(t)[1]] == list("abcdefgh")


def frag(i, texto, **kw):
    return {"fragmento_id": i, "norma": "N", "tipo_numero": "Ley 1", "articulo": "84", "jerarquia": ["Artículo 84"],
            "texto": texto, "vigente": True, **kw}


def test_construir_modos():
    fr = [frag("x-art-84", LISTA), frag("x-art-2", "Artículo 2.- Algo corto.")]
    enr = {"x-art-84": {"rol": "sustantivo", "hechos": ["hecho general"], "literales": {"c": ["hecho del c"]}},
           "x-art-2": {"rol": "definicion", "hechos": ["h1", "h2", "h3"]}}
    p = construir(fr, enr, "p")
    assert len(p) == 9 and p[3]["frag_id"] == "x-art-84-p3" and p[3]["payload"]["literal"] == "c"
    assert "hecho del c" not in p[3]["texto_embedding"] and p[3]["payload"]["enriquecimiento"] == "hecho del c"
    assert p[0]["frag_id"] == "x-art-2" and p[0]["payload"]["rol"] == "definicion"
    assert "hecho del c" in construir(fr, enr, "pe")[3]["texto_embedding"]
    e = construir(fr, enr, "e")
    assert len(e) == 2 and "hecho general" in e[1]["texto_embedding"] and "literal" not in e[1]["payload"]
    solo = construir(fr, enr, "eonly")
    assert "Texto del literal" not in solo[3]["texto_embedding"] and "hecho del c" in solo[3]["texto_embedding"]
