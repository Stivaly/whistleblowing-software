import medir_base_b2 as m


def test_hit_normaliza_fragmento_a_articulo_y_corta_en_k():
    ids = ["1008668-art-1-p1", "1008668-art-3", "1008668-art-4"]
    assert m.hit(ids, {"1008668-art-1"}, 5) == 1.0
    assert m.hit(ids, {"1008668-art-4"}, 2) == 0.0
    assert m.hit(ids, {"1008668-art-4"}, 3) == 1.0


def test_cadena_antes_y_despues_del_revisor():
    sug = [{"id_articulo": "a", "confianza": 0.9, "dictamen": "veta"},
           {"id_articulo": "b", "confianza": 0.5, "dictamen": "confirma", "confianza_revisor": 0.4},
           {"id_articulo": "c", "confianza": 0.7, "dictamen": "condiciona", "confianza_revisor": 0.6}]
    assert m.top_antes(sug) == ["a", "c", "b"]
    assert m.top_despues(sug) == ["c", "b"]


def test_medir_cadena_cuenta_fallos_y_estados():
    casos = [{"id": "x", "ley": "20.393", "esperados": {"1008668-art-1"}},
             {"id": "y", "ley": "20.393", "esperados": {"1008668-art-3"}}]
    salida = [{"id": "x", "estado": "completada", "motivo_revision": None, "candidatos": ["1008668-art-1"],
               "evaluador": ["1008668-art-1"], "sugerencias": [{"id_articulo": "1008668-art-1", "confianza": 1}]},
              {"id": "y", "estado": "revision_manual", "motivo_revision": "validacion_fallida", "candidatos": [],
               "evaluador": [], "sugerencias": []}]
    r, meta = m.medir_cadena(casos, salida)
    assert r["global"]["cadena5"]["valor"] == 0.5 and r["global"]["cand70"]["valor"] == 0.5
    assert meta["estados"] == {"completada": 1, "revision_manual:validacion_fallida": 1}


def test_casos_set_acepta_particiones_complejas(tmp_path, monkeypatch):
    import json
    f = tmp_path / "complejas.json"
    f.write_text(json.dumps({"casos": [
        {"id": "CX-9001", "triage": "si", "ley_principal": "20.393", "particion": "afinar",
         "articulos_corregidos": ["1008668-art-1"], "texto_original": "x"},
        {"id": "CX-9002", "triage": "si", "ley_principal": "20.393", "particion": "medir_complejas",
         "articulos_corregidos": ["1008668-art-3"], "texto_original": "y"},
        {"id": "CX-9003", "triage": "control", "ley_principal": "ninguna", "particion": "medir_complejas",
         "articulos_corregidos": [], "texto_original": "z"}]}))
    monkeypatch.setitem(m.EXTRA, "afinar", f)
    monkeypatch.setitem(m.EXTRA, "medir_complejas", f)
    corpus = {"1008668-art-1", "1008668-art-3"}
    assert [c["id"] for c in m.casos_set("afinar", corpus)] == ["CX-9001"]
    assert [c["id"] for c in m.casos_set("medir_complejas", corpus)] == ["CX-9002"]
    assert {"afinar", "medir_complejas"} <= set(m.SETS_VALIDOS) and "afinar" not in m.SETS
