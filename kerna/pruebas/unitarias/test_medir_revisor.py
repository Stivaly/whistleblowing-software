"""medir_revisor.py con datos sintéticos (sin red, sin modelos, sin el dataset)."""
import json

import medir_revisor as m


def s(i, conf=0.9, dictamen=None, **kw):
    return {"id_articulo": i, "confianza": conf, "dictamen": dictamen, **kw}


CASOS = [
    {"id": "c1", "esperados": ["a", "b"], "sugerencias": [s("a", .9, "confirma"), s("x", .8, "veta"), s("b", .7, "condiciona", confianza_revisor=.4)]},
    {"id": "c2", "esperados": ["c"], "sugerencias": [s("y", .9, "veta"), s("c", .5, "veta")]},          # veto incorrecto
    {"id": "c3", "esperados": ["d"], "sugerencias": [s("d", .6), s("z", .5)]},                           # sin revisión
    {"id": "k1", "control": True, "esperados": [], "sugerencias": [s("q", .9, "veta"), s("r", .8, "veta")]},
    {"id": "k2", "control": True, "esperados": [], "sugerencias": [s("q", .9, "condiciona")]},
    {"id": "k3", "control": True, "esperados": [], "sugerencias": []},
]


def test_top_antes_y_despues_ordenan_y_excluyen_vetadas():
    sug = CASOS[0]["sugerencias"]
    assert m.top_antes(sug, 2) == ["a", "x"]
    assert m.top_despues(sug, 5) == ["a", "b"]
    assert m.top_despues([s("a", .9, "veta")], 5) == []
    assert m.top_despues([s("a", .9, confianza_revisor=.1), s("b", .5, "confirma", confianza_revisor=.4)], 5) == ["b", "a"]


def test_medicion_sintetica():
    r = m.medir(CASOS, k=5, n_bootstrap=200)
    assert (r["casos"], r["casos_con_esperados"], r["casos_control"]) == (6, 3, 3)
    rec = r["recall_por_articulo"]
    assert rec["antes"] == 1.0 and rec["despues"] == round((1.0 + 0.0 + 1.0) / 3, 4)
    assert rec["antes_global"] == 1.0 and rec["despues_global"] == round(3 / 4, 4)
    assert rec["no_rompe_recall"] is False and rec["diferencia"]["media"] == round(-1 / 3, 4)
    assert r["precision"]["antes"] == round((2 / 3 + 1 / 2 + 1 / 2) / 3, 4)
    v = r["vetos"]
    assert (v["total"], v["correctos"], v["incorrectos"], v["en_controles"]) == (5, 2, 1, 2)
    assert v["precision_del_veto"] == round(2 / 3, 4)
    assert v["controles_con_sugerencias"] == 2 and v["controles_con_todo_vetado"] == 1 and v["tasa_control_limpio"] == 0.5
    rv = r["revision"]
    assert rv["sugerencias"] == 10 and rv["condicionadas"] == 2
    assert rv["esperadas_por_dictamen"]["veta"] == {"esperadas": 1, "total": 5, "proporcion": 0.2}
    assert rv["esperadas_por_dictamen"]["sin_revision"]["total"] == 2


def test_revisor_que_no_veta_no_rompe_el_recall():
    casos = [{"id": f"c{i}", "esperados": ["a"], "sugerencias": [s("a", .9, "confirma"), s("b", .5, "condiciona")]}
             for i in range(10)]
    r = m.medir(casos, 5, 200)
    assert r["recall_por_articulo"]["no_rompe_recall"] is True and r["recall_por_articulo"]["diferencia"]["media"] == 0.0
    assert r["precision"]["antes"] == r["precision"]["despues"] == 0.5


def test_entrada_vacia_o_sin_controles_no_falla():
    r = m.medir([], 5, 10)
    assert r["recall_por_articulo"]["antes"] is None and r["vetos"]["tasa_control_limpio"] is None
    assert m.medir([{"esperados": ["a"], "sugerencias": []}], 5, 10)["recall_por_articulo"]["despues"] == 0.0


def test_bootstrap_es_reproducible():
    assert m.bootstrap_diferencia([0, -1, 0, 0, 1], 100) == m.bootstrap_diferencia([0, -1, 0, 0, 1], 100)


def test_cli_lee_json_y_jsonl_y_guarda_registro(tmp_path, capsys):
    j, l, out = tmp_path / "c.json", tmp_path / "c.jsonl", tmp_path / "reg" / "r.json"
    j.write_text(json.dumps(CASOS), encoding="utf-8")
    l.write_text("\n".join(json.dumps(c) for c in CASOS), encoding="utf-8")
    assert m.cargar_casos(j) == m.cargar_casos(l)
    assert m.main([str(j), "--bootstrap", "50", "--salida", str(out), "--etiqueta", "sintetico"]) == 0
    reg = json.loads(out.read_text(encoding="utf-8"))
    assert reg["parametros"]["semilla"] == m.SEMILLA and reg["parametros"]["etiqueta"] == "sintetico"
    assert reg["resultado"]["casos"] == 6 and "fecha" in reg and "commit" in reg
    assert "recall_por_articulo" in capsys.readouterr().out
