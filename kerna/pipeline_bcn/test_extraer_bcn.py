"""Pruebas del extractor BCN. XML sintético con la estructura real verificada
(anidamiento EstructurasFuncionales, doble articulado, transitorios, derogados).

  pip install -r requirements-dev.txt && python3 -m pytest -q

Las pruebas de upsert usan un MongoDB real y desechable (fixture `db` de conftest.py,
MONGODB_TEST_URI, por defecto mongodb://127.0.0.1:27018/kerna_test). Con Docker:
  docker run -d --name kerna-mongo44-test -p 127.0.0.1:27018:27017 mongo:4.4
(4.4 porque MongoDB 5+ exige CPU con AVX; las operaciones usadas son las mismas en Atlas 8.)
"""

import pytest

import extraer_bcn as e

NS = 'xmlns="http://www.leychile.cl/esquemas"'


def ef(tipo, texto="", nombre="", titulo="", hijos="", derogado="no derogado",
       transitorio="no transitorio", id_parte="1"):
    sub = f"<EstructurasFuncionales>{hijos}</EstructurasFuncionales>" if hijos else ""
    return (f'<EstructuraFuncional transitorio="{transitorio}" tipoParte="{tipo}" '
            f'fechaVersion="2024-01-01" derogado="{derogado}" idParte="{id_parte}">'
            f"<Texto>{texto}</Texto><Metadatos><NombreParte>{nombre}</NombreParte>"
            f"<TituloParte>{titulo}</TituloParte></Metadatos>{sub}</EstructuraFuncional>")


def norma(cuerpo, derogada="no derogado", tipo="Ley", numero="99999"):
    return (f'<?xml version="1.0" encoding="UTF-8"?><Norma {NS} normaId="555" '
            f'fechaVersion="2024-02-02" derogado="{derogada}">'
            f'<Identificador fechaPublicacion="2024-01-15"><TiposNumeros><TipoNumero>'
            f"<Tipo>{tipo}</Tipo><Numero>{numero}</Numero></TipoNumero></TiposNumeros>"
            f"<Organismos><Organismo>MINISTERIO X</Organismo></Organismos></Identificador>"
            f"<Metadatos><TituloNorma>LEY DE PRUEBA</TituloNorma><Materias>"
            f"<Materia>Prueba</Materia></Materias></Metadatos>"
            f"<EstructurasFuncionales>{cuerpo}</EstructurasFuncionales></Norma>").encode()


CFG = {"nombre": "Ley de prueba", "idNorma": 555, "categoria": ["test"]}


def test_jerarquia_anidada_y_texto_por_incisos():
    xml = norma(ef("Título", "TÍTULO I", titulo="TÍTULO I Generalidades", hijos=
                   ef("Párrafo", titulo="§ 1 Normas", hijos=
                      ef("Artículo", "Artículo 1.- Primer inciso\npartido en\nlíneas.\n\n"
                                     "     Segundo inciso.", nombre="1"))))
    doc, frags = e.parsear(xml, CFG)
    assert doc["id_norma"] == 555 and doc["titulo"] == "LEY DE PRUEBA" and doc["_id"] == "555"
    [f] = frags
    assert f["_id"] == "555-art-1"
    assert f["jerarquia"] == ["TÍTULO I Generalidades", "§ 1 Normas", "Artículo 1"]
    assert f["texto"] == "Artículo 1.- Primer inciso partido en líneas.\n\nSegundo inciso."
    assert f["tipo_numero"] == "Ley 99999" and f["vigente"] is True
    assert f["texto_embedding"].startswith("Ley 99999 — Ley de prueba. TÍTULO I")


def test_doble_articulado_transitorios_y_derogados():
    interna = ef("Artículo", "Artículo 1°.- Contenido.", nombre="1") + \
        ef("Artículo", "Artículo 2.- Derogado.", nombre="2", derogado="derogado")
    xml = norma(
        ef("Artículo", "Artículo Primero.- Apruébase la siguiente ley:", nombre="PRIMERO",
           hijos=ef("Doble Articulado", nombre="del Artículo PRIMERO", hijos=interna))
        + ef("Artículo", "ARTICULOS TRANSITORIOS", nombre="710", hijos=
             ef("Artículo", "Artículo 1.- Rige desde...", nombre="1", transitorio="transitorio")))
    _, frags = e.parsear(xml, CFG)
    por_id = {f["_id"]: f for f in frags}
    assert set(por_id) == {"555-art-primero", "555-art-1", "555-art-2", "555-art-t-1"}
    assert por_id["555-art-1"]["jerarquia"] == ["Artículo PRIMERO", "Artículo 1"]
    assert por_id["555-art-2"]["vigente"] is False
    assert por_id["555-art-t-1"]["jerarquia"] == ["ARTICULOS TRANSITORIOS", "Artículo 1 transitorio"]
    assert por_id["555-art-t-1"]["articulo"] == "1 transitorio"
    assert por_id["555-art-primero"]["tipo_contenido"] == "promulgatoria"
    assert por_id["555-art-primero"]["estado_embedding"] == "no_aplica"
    assert por_id["555-art-1"]["tipo_contenido"] == "sustantiva"


def test_ids_con_enie_y_colisiones():
    xml = norma(ef("Artículo", "Artículo 183-N.- a", nombre="183 N")
                + ef("Artículo", "Artículo 183-Ñ.- b", nombre="183 Ñ")
                + ef("Artículo", "Artículo 5.- c", nombre="5")
                + ef("Artículo", "Artículo 5.- d (repetido)", nombre="5"))
    _, frags = e.parsear(xml, CFG)
    ids = [f["_id"] for f in frags]
    assert ids[:2] == ["555-art-183-n", "555-art-183-nn"]
    assert len(set(ids)) == 4


def test_norma_derogada_y_codigo_sin_numero():
    xml = norma(ef("Artículo", "Artículo 1.- x", nombre="1"), derogada="derogado",
                tipo="Código", numero="PENAL")
    doc, [f] = e.parsear(xml, {"nombre": "Código Penal", "idNorma": 1984})
    assert doc["derogado"] and not f["vigente"]
    assert f["tipo_numero"] == "Código Penal"


def test_articulo_largo_se_parte():
    inciso = "Oración de relleno bastante larga. " * 100  # ~3500 chars
    xml = norma(ef("Artículo", f"Artículo 9.- {inciso}\n\n{inciso}\n\n{inciso * 2}", nombre="9"))
    _, frags = e.parsear(xml, CFG)
    assert len(frags) >= 3
    assert all(len(f["texto"]) <= e.MAX_CHARS_FRAGMENTO for f in frags)
    assert [f["_id"] for f in frags][:2] == ["555-art-9-p1", "555-art-9-p2"]
    assert frags[0]["parte"] == f"1/{len(frags)}"
    assert "(parte 1/" in frags[0]["texto_embedding"]


def test_upsert_versiona_y_no_borra(db):
    v1 = norma(ef("Artículo", "Artículo 1.- original", nombre="1")
               + ef("Artículo", "Artículo 2.- se irá", nombre="2"))
    r = e.upsert_mongo(db, *e.parsear(v1, CFG))
    assert r["nuevos"] == 2
    db.fragmentos.update_many({}, {"$set": {"estado_embedding": "ok"}})

    # Misma versión: sin cambios.
    assert e.upsert_mongo(db, *e.parsear(v1, CFG))["sin_cambios"]

    # Nueva versión: art. 1 cambia, art. 2 desaparece, art. 3 aparece.
    v2 = norma(ef("Artículo", "Artículo 1.- modificado", nombre="1")
               + ef("Artículo", "Artículo 3.- nuevo", nombre="3"))
    r = e.upsert_mongo(db, *e.parsear(v2, CFG))
    assert (r["nuevos"], r["cambiados"], r["retirados"]) == (1, 1, 1)

    a1 = db.fragmentos.find_one({"_id": "555-art-1"})
    a2 = db.fragmentos.find_one({"_id": "555-art-2"})
    assert a1["texto"] == "Artículo 1.- modificado" and a1["estado_embedding"] == "pendiente"
    assert a2 is not None and a2["vigente"] is False and a2["estado_embedding"] == "pendiente"
    assert db.fragmentos_historial.count_documents({"fragmento_id": "555-art-1"}) == 1
    assert db.normas_historial.count_documents({}) == 1
    assert a1["clave_corpus"] == "555"

    # Re-ejecutar v2 con --forzar no vuelve a retirar ni duplicar historial.
    r = e.upsert_mongo(db, *e.parsear(v2, CFG), forzar=True)
    assert (r["nuevos"], r["cambiados"], r["retirados"]) == (0, 0, 0)


def test_articulo_sin_cambios_conserva_embedding(db):
    v1 = norma(ef("Artículo", "Artículo 1.- igual", nombre="1")
               + ef("Artículo", "Artículo 2.- a", nombre="2"))
    e.upsert_mongo(db, *e.parsear(v1, CFG))
    db.fragmentos.update_many({}, {"$set": {"estado_embedding": "ok"}})
    v2 = norma(ef("Artículo", "Artículo 1.- igual", nombre="1")
               + ef("Artículo", "Artículo 2.- b", nombre="2"))
    e.upsert_mongo(db, *e.parsear(v2, CFG))
    assert db.fragmentos.find_one({"_id": "555-art-1"})["estado_embedding"] == "ok"
    assert db.fragmentos.find_one({"_id": "555-art-2"})["estado_embedding"] == "pendiente"


def test_clasifica_modificatorios_y_derogados():
    xml = norma(ef("Artículo", "Artículo 1.- Modifícase el Código del Trabajo: ...", nombre="1")
                + ef("Artículo", "Artículo segundo.- Suprímese el literal m) del artículo 33.", nombre="segundo")
                + ef("Artículo", "Artículo 3°.- Introdúcense las siguientes modificaciones...", nombre="3")
                + ef("Artículo", "Artículo 4.- Las empresas deberán modificar su reglamento.", nombre="4")
                + ef("Artículo", "ART. 5. Derogado.", nombre="5")
                + ef("Artículo", "Artículo 6.- Reemplázase ... (forzado sustantivo)", nombre="6"))
    _, frags = e.parsear(xml, {**CFG, "articulos_sustantivos": ["6"]})
    tipos = {f["articulo"]: f["tipo_contenido"] for f in frags}
    assert tipos == {"1": "modificatoria", "segundo": "modificatoria", "3": "modificatoria",
                     "4": "sustantiva", "5": "sustantiva", "6": "sustantiva"}
    assert [f["vigente"] for f in frags if f["articulo"] == "5"] == [False]


# --------------------------------------------------------------- fuente JSON
def jnodo(i, t_html, hijos=None):
    n = {"i": i, "t": t_html}
    if hijos:
        n["h"] = hijos
    return n


NOTA = ('<span class="n" id="n_1"><a href="navegar?idNorma=777&amp;idParte=1&amp;'
        'idVersion=2026-12-01">Ley 777<br>Art. 1<br>D.O. 1.1.2025</a></span>')


def norma_json(version_desde="2026-12-01"):
    import json as _json
    return _json.dumps({
        "metadatos": {"id_norma": "555", "titulo_norma": "LEY JSON", "derogado": False,
                      "tipos_numeros": [{"descripcion": "Ley", "numero": "99999"}],
                      "materias": ["Prueba"], "organismos": ["MIN"], "fecha_publicacion": "2000-01-01",
                      "vigencias": [{"desde": "2026-12-01", "hasta": "", "tipo_version": "7"},
                                    {"desde": "2023-05-09", "hasta": "2026-11-30", "tipo_version": "2"}]},
        "estructura": [{"n": "Encabezado", "i": 1},
                       {"n": "Título I De todo", "i": 2, "t": 1, "h": [
                           {"n": "Artículo 1", "i": 3, "t": 6}, {"n": "Artículo 2 bis", "i": 4, "t": 6}]},
                       {"n": "Disposiciones transitorias", "i": 5, "t": 7, "h": [
                           {"n": "Artículo 1 Transitorio", "i": 6, "t": 6}]}],
        "html": [jnodo(1, "<div>LEY JSON</div>"),
                 jnodo(2, "<div>Título I</div>", [
                     jnodo(3, f'<div><div class="p">&nbsp; Ar{NOTA}t&#xED;culo 1&#xB0;.- Primero.</div>'
                              '<div class="p">Segundo inciso.</div></div>'),
                     jnodo(4, '<div><div class="p">Art&#xED;culo 2 bis.- Sin nota.</div></div>')]),
                 jnodo(5, "<div>Disposiciones transitorias</div>", [
                     jnodo(6, '<div><div class="p">Art&#xED;culo 1.- Transitorio.</div></div>')])],
    }).encode()


CFG_J = {"nombre": "Ley JSON", "idNorma": 555, "fuente": "json", "version": "2026-12-01",
         "clave": "555@2026-12-01"}


def test_json_limpia_notas_y_arma_jerarquia():
    doc, frags = e.parsear(norma_json(), CFG_J)
    por = {f["_id"]: f for f in frags}
    assert set(por) == {"555-2026-12-01-art-1", "555-2026-12-01-art-2-bis", "555-2026-12-01-art-t-1"}
    f1 = por["555-2026-12-01-art-1"]
    assert f1["texto"] == "Artículo 1°.- Primero.\n\nSegundo inciso."
    assert f1["jerarquia"] == ["Título I De todo", "Artículo 1"]
    assert f1["modificado_por"] == ["777"]
    assert por["555-2026-12-01-art-t-1"]["jerarquia"] == ["Disposiciones transitorias", "Artículo 1 transitorio"]
    assert doc["vigencia_desde"] == "2026-12-01" and doc["_id"] == "555@2026-12-01"


def test_json_solo_modificados_por():
    _, frags = e.parsear(norma_json(), {**CFG_J, "solo_modificados_por": 777, "version": None})
    assert [f["articulo"] for f in frags] == ["1"]


def test_vigencia_anticipada_historica_y_diferida():
    from datetime import date
    antes, despues = date(2026, 10, 2), date(2026, 12, 1)
    _, fr = e.parsear(norma_json(), {**CFG_J, "vigencia": "anticipada"}, hoy=antes)
    assert fr[0]["vigente"] and fr[0]["vigencia_anticipada"]
    _, fr = e.parsear(norma_json(), {**CFG_J, "vigencia": "anticipada"}, hoy=despues)
    assert fr[0]["vigente"] and not fr[0]["vigencia_anticipada"]
    _, fr = e.parsear(norma_json(), {**CFG_J, "vigencia": "bcn"}, hoy=antes)
    assert not fr[0]["vigente"]  # diferida sin anticipar
    _, fr = e.parsear(norma_json(), {**CFG_J, "version": "2023-05-09", "vigencia": "historica"}, hoy=antes)
    assert not fr[0]["vigente"]
    with pytest.raises(ValueError):
        e.parsear(norma_json(), {**CFG_J, "version": "2020-01-01"})


def test_cambio_de_fecha_actualiza_vigencia_sin_cambiar_fuente(db):
    from datetime import date
    cfg = {**CFG_J, "vigencia": "anticipada"}
    e.upsert_mongo(db, *e.parsear(norma_json(), cfg, hoy=date(2026, 10, 2)))
    db.fragmentos.update_many({}, {"$set": {"estado_embedding": "ok"}})
    # 1 de diciembre: misma fuente, pero vigencia_anticipada pasa a false.
    r = e.upsert_mongo(db, *e.parsear(norma_json(), cfg, hoy=date(2026, 12, 1)))
    assert not r["sin_cambios"] and r["cambiados"] == 3
    f = db.fragmentos.find_one({"_id": "555-2026-12-01-art-1"})
    assert f["vigencia_anticipada"] is False and f["estado_embedding"] == "pendiente"
    assert f["motivo_pendiente"] == "metadatos"
    assert db.normas_historial.count_documents({}) == 0  # la fuente no cambió
