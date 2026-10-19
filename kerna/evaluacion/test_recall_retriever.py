"""Pruebas de la medición de recall@5, sin red (Voyage y Qdrant falsos).

  ../pipeline_bcn/.venv-test/bin/python -m pytest -q
"""
import json

import pytest

import recall_retriever as r
from recall_retriever import embed_sync  # recall_retriever agrega pipeline_bcn/ al path

CORPUS = {"207436-karin-art-2", "207436-karin-art-154-bis", "207436-karin-art-211-a",
          "207436-karin-art-211-b", "207436-karin-art-211-c", "1008668-art-1", "1008668-art-4",
          "141599-2026-12-01-art-2", "141599-2026-12-01-art-17", "141599-2026-12-01-art-18",
          "141599-2026-12-01-art-19", "1200096-art-6"}


def arts(texto):
    return sorted(a.split("-art-", 1)[1] for a in r.normalizar_candidatos(texto, CORPUS)[0])


@pytest.mark.parametrize("texto, esperado", [
    ("CT 2 (acoso laboral: hoy basta un acto); CT 211-A a 211-C; CT 162, 177", ["2", "211-a", "211-b", "211-c"]),
    ("CT 2 (acoso sexual), CT 211-A (prevención)", ["2", "211-a"]),
    ("CT 2 inc. 2 b); Ley 18.834 art. 84 l) y m), 159", ["2"]),
    ("CT 211-C (plazos de investigación); Reglamento Ley 21.643 art. 17", ["211-c"]),
    ("CT 5, 154 bis (reserva de información del trabajador); Ley 19.628", ["154-bis"]),
    ("Ley 19.628 art. 17-19 (datos de morosidad); Ley 20.009", ["17", "18", "19"]),
    ("Ley 19.628 art. 2 g), 9, 10, 11 (seguridad); Ley 21.719 (notificación)", ["2"]),
    ("Ley 20.393 art. 3, 4 (modelo de prevención), 1 (cohecho); CP 250", ["1", "4"]),
    ("CT 97 N°4 (facturas falsas); CP 468 (estafa); Ley 20.393 art. 1 (delitos base, incl. Ley 21.595)", ["1"]),
    ("Ley 21.595 / Ley 20.393 (apropiación indebida de cotizaciones); CT 58", []),
    ("Ley 21.719 (derechos ARCO, plazos de conservación)", []),
])
def test_normalizar_candidatos(texto, esperado):
    assert arts(texto) == esperado


def test_citas_fuera_del_corpus():
    dentro, fuera = r.normalizar_candidatos("CT 2; CT 485-489 (tutela)", CORPUS)
    assert dentro == {"207436-karin-art-2"}
    assert fuera == [f"207436-karin-art-{n}" for n in range(485, 490)]


def test_articulo_de_quita_la_parte():
    assert r.articulo_de("141599-2026-12-01-art-2-p2") == "141599-2026-12-01-art-2"
    assert r.articulo_de("1008668-art-17-quater") == "1008668-art-17-quater"


def test_texto_consulta_quita_marca_de_resumen():
    caso = {"resumen_parafraseado": "[Resumen parafraseado] Jefe acosa a trabajadora."}
    assert r.texto_consulta(caso, "resumen_parafraseado") == "Jefe acosa a trabajadora."


def _top(*ids):
    norma = {"207436": 207436, "1008668": 1008668, "141599": 141599, "1200096": 1200096}
    return [{"fragmento_id": f, "id_norma": norma[f.split("-")[0]], "score": 0.9 - 0.1 * i}
            for i, f in enumerate(ids)]


def test_evaluar_por_ley_y_global():
    casos = [
        {"id": "A", "ley_principal": "21.643", "articulos_candidatos": "CT 211-B"},
        {"id": "B", "ley_principal": "21.643", "articulos_candidatos": "Ley 21.643"},
        {"id": "C", "ley_principal": "20.393", "articulos_candidatos": "Ley 20.393 art. 1"},
        {"id": "D", "ley_principal": "19.628-21.719", "articulos_candidatos": "Ley 19.628 art. 2"},
        {"id": "N", "ley_principal": "ninguna", "articulos_candidatos": "CT 177"},
    ]
    tops = [
        _top("1008668-art-4", "207436-karin-art-211-b"),          # ley y artículo
        _top("1200096-art-6"),                                     # ley (Ley 21.643 propia); sin artículos
        _top("207436-karin-art-2", "141599-2026-12-01-art-17"),    # falla
        _top("141599-2026-12-01-art-2-p2"),                        # artículo vía parte
        [{"fragmento_id": "207436-karin-art-2", "id_norma": 207436, "score": 0.42}],
    ]
    res = r.evaluar(casos, tops, CORPUS)
    g = res["por_ley"]["global"]
    assert (g["casos"], g["recall_ley"], g["casos_articulo"], g["recall_articulo"]) == (4, 0.75, 3, 2 / 3)
    assert res["por_ley"]["21.643"]["recall_ley"] == 1.0
    assert res["por_ley"]["21.643"]["casos_articulo"] == 1
    assert res["por_ley"]["20.393"]["recall_articulo"] == 0.0
    n = res["ninguna"]
    assert n["casos"] == 1 and n["top1"] == [0.42]
    u40 = next(u for u in n["umbrales"] if u["umbral"] == 0.40)
    u45 = next(u for u in n["umbrales"] if u["umbral"] == 0.45)
    assert (u40["falsos_positivos"], u45["falsos_positivos"]) == (1.0, 0.0)
    assert u45["positivos_que_pasan"] == 1.0
    assert r.UMBRALES[0] == 0.15 and r.UMBRALES[-1] == 0.55


def test_evaluar_rechaza_ley_desconocida():
    with pytest.raises(ValueError):
        r.evaluar([{"id": "X", "ley_principal": "18.834", "articulos_candidatos": ""}], [[]], CORPUS)


def test_embeber_usa_cache_y_lotes(tmp_path, monkeypatch):
    llamadas = []

    def falso(textos):
        llamadas.append(list(textos))
        return [[float(len(t))] * embed_sync.DIMS for t in textos]

    monkeypatch.setattr(embed_sync, "embed_consultas", falso)
    cache = tmp_path / "cache.json"
    v = r.embeber(["uno", "dos", "uno"], cache)
    assert llamadas == [["uno", "dos"]]           # una sola petición, sin duplicados
    assert v[0] == v[2] and v[0][0] == 3.0
    r.embeber(["dos", "tres"], cache)
    assert llamadas[-1] == ["tres"]                # lo ya embebido sale del cache
    assert len(json.loads(cache.read_text())) == 3


def test_buscar_y_corpus_con_filtro_vigente(monkeypatch):
    peticiones = []

    def qdrant(path, body=None, method="PUT"):
        peticiones.append((path, body, method))
        if path.endswith("/scroll"):
            pagina = body.get("offset") or 0
            puntos = [{"payload": {"fragmento_id": f}} for f in
                      (["141599-2026-12-01-art-2-p1", "141599-2026-12-01-art-2-p2"] if pagina == 0
                       else ["1008668-art-1"])]
            return {"result": {"points": puntos, "next_page_offset": None if pagina else 1}}
        return {"result": [[{"score": 0.8, "payload": {"fragmento_id": "1008668-art-1", "id_norma": 1008668}}]
                           for _ in body["searches"]]}

    monkeypatch.setattr(embed_sync, "qdrant", qdrant)
    assert r.articulos_vigentes() == {"141599-2026-12-01-art-2", "1008668-art-1"}
    tops = r.buscar([[0.0]] * 3, lote=2)
    assert len(tops) == 3 and tops[0][0] == {"fragmento_id": "1008668-art-1", "id_norma": 1008668, "score": 0.8}
    busquedas = [b for p, b, m in peticiones if p.endswith("/search/batch")]
    assert [len(b["searches"]) for b in busquedas] == [2, 1]
    for p, b, m in peticiones:
        assert m == "POST" and p.startswith("/collections/normativa_cl/")
        filtro = b["filter"] if "filter" in b else b["searches"][0]["filter"]
        assert filtro == {"must": [{"key": "vigente", "match": {"value": True}}]}
    assert all(s["limit"] == 5 for b in busquedas for s in b["searches"])


def test_registrar_agrega_una_linea_sin_textos(tmp_path):
    casos = [{"id": "A", "ley_principal": "21.643", "articulos_candidatos": "CT 2",
              "texto_original": "relato privado"},
             {"id": "N", "ley_principal": "ninguna", "articulos_candidatos": ""}]
    res = r.evaluar(casos, [_top("207436-karin-art-2"), _top("1008668-art-1")], CORPUS)
    reg = tmp_path / "registro" / "recall.jsonl"
    for _ in range(2):
        r.registrar(res, campo="texto_original", dataset=b"{}", articulos_corpus=12, casos=2,
                    duracion_s=1.23, registro=reg)
    lineas = [json.loads(l) for l in reg.read_text().splitlines()]
    assert len(lineas) == 2                                   # agrega, no sobrescribe
    e = lineas[0]
    assert e["parametros"]["modelo"] == "voyage-4-large" and e["parametros"]["top_k"] == 5
    assert e["parametros"]["filtro"] == "vigente=true"
    assert e["por_ley"]["global"]["recall_articulo"] == 1.0
    assert e["dataset"]["sha256"] == "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    assert e["fecha"] and e["commit"]
    assert "relato privado" not in reg.read_text()
