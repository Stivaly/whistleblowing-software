import asyncio

import pytest

from nucleo_apoyo import (FLASH, GEMMA, LITE, SILENCIO, FakeGemini, FakeLocal, FakeQdrant, FakeVoyage, armar, caida,
                          falla, procesar_caso)

pytestmark = [pytest.mark.rf("RF26")]


def correr(e, **kw):
    return asyncio.run(procesar_caso(e, **kw))


@pytest.mark.pr("PR-02")
@pytest.mark.pr("PR-18")
@pytest.mark.rf("RF27")
def test_camino_normal_oficial_sin_contingencia():
    e = armar()
    g, _ = correr(e)
    assert g["estado"] == "completada" and g["modo"] == "oficial" and g["recuperacion"] == "nube"
    assert g["contingencia"] is False and g["version_corpus"] == 7
    assert 1 <= len(g["articulos"]) <= 5
    a = g["articulos"][0]
    assert a["enlace_fuente"].startswith("https://www.bcn.cl") and a["norma"] == "Ley N.° 21.643"
    assert a["articulo"] == "Artículo 1"
    assert [x["confianza"] for x in g["articulos"]] == sorted((x["confianza"] for x in g["articulos"]), reverse=True)
    assert e.gemini.generacion(FLASH) and not e.gemini.generacion(LITE)


@pytest.mark.pr("PR-02")
@pytest.mark.pr("PR-18")
@pytest.mark.rf("RF27")
def test_cc1_falla_oficial_pasa_a_respaldo():
    e = armar(gemini=FakeGemini({FLASH: falla(503)}))
    g, ref = correr(e)
    assert g["estado"] == "completada" and g["modo"] == "respaldo" and g["contingencia"] is True
    assert g["recuperacion"] == "nube"
    sol = next(iter(e.almacen.solicitudes.values()))
    assert sol["modelo"] == LITE and sol["proveedor"] == "gemini" and sol["embedding"] == "voyage-4-large"
    assert sol["coleccion"] == "normativa_cl" and sol["version_indice"] == "7"


@pytest.mark.pr("PR-02")
def test_cc2_fallan_oficial_y_respaldo_pasa_a_local():
    e = armar(gemini=FakeGemini({FLASH: falla(500), LITE: falla(429)}))
    g, _ = correr(e)
    assert g["estado"] == "completada" and g["modo"] == "local" and g["contingencia"] is True
    assert next(iter(e.almacen.solicitudes.values()))["modelo"] == GEMMA


@pytest.mark.pr("PR-02")
@pytest.mark.pr("PR-18")
@pytest.mark.rf("RF27")
@pytest.mark.parametrize("voyage,qdrant", [(FakeVoyage(caida("voyage")), FakeQdrant()),
                                           (FakeVoyage(), FakeQdrant(caida("qdrant")))])
def test_cc3_nube_no_responde_recupera_en_local(voyage, qdrant):
    e = armar(voyage=voyage, qdrant=qdrant)
    g, _ = correr(e)
    assert g["estado"] == "completada" and g["recuperacion"] == "local" and g["modo"] == "oficial"
    assert g["contingencia"] is True and g["version_corpus"] == 5
    sol = next(iter(e.almacen.solicitudes.values()))
    assert sol["embedding"] == "bge-m3-local" and sol["coleccion"] == "normativa_local"
    assert e.local.llamadas


@pytest.mark.pr("PR-02")
def test_cc4_falla_toda_la_cadena_revision_manual():
    e = armar(gemini=FakeGemini({FLASH: falla(503), LITE: falla(503), GEMMA: falla(503)}))
    g, _ = correr(e)
    assert g["estado"] == "revision_manual" and g["motivo_revision"] == "cadena_agotada"
    assert g["modo"] == "manual" and g["articulos"] == [] and g["contingencia"] is True


@pytest.mark.pr("PR-02")
def test_cc4_nube_y_local_caidos_revision_manual():
    e = armar(voyage=FakeVoyage(caida()), local=FakeLocal(caida("local")))
    g, _ = correr(e)
    assert g["estado"] == "revision_manual" and g["motivo_revision"] == "cadena_agotada"


@pytest.mark.pr("PR-02")
@pytest.mark.pr("PR-04")
def test_cc4_se_agotan_240_s_tiempo_agotado():
    e = armar(gemini=FakeGemini({FLASH: SILENCIO, LITE: SILENCIO, GEMMA: SILENCIO}))
    g, _ = correr(e)
    assert g["estado"] == "revision_manual" and g["motivo_revision"] == "tiempo_agotado"
    assert e.reloj() - 1_700_000_000.0 >= 240 - 31


@pytest.mark.pr("PR-02")
def test_sin_normativa_bajo_umbral():
    bajos = [dict(f, puntaje=0.05) for f in __import__("nucleo_apoyo").FRAGMENTOS]
    e = armar(qdrant=FakeQdrant(fragmentos=bajos))
    g, _ = correr(e)
    assert g["estado"] == "revision_manual" and g["motivo_revision"] == "sin_normativa_aplicable"
    assert not e.gemini.generacion()


@pytest.mark.pr("PR-02")
def test_validacion_fallida_si_ninguna_cita_sirve():
    def inventa(modelo, sistema, usuario, esquema):
        from nucleo_apoyo import FakeGemini, json_ok
        if "materia" in esquema["properties"]:
            return FakeGemini.responder(modelo, sistema, usuario, esquema)
        return json_ok({"articulos": [{"fragmento_id": "ley_inventada", "explicacion": "x", "cita": "texto cualquiera largo",
                                       "confianza": 0.9}]})
    e = armar(gemini=FakeGemini({FLASH: inventa}))
    g, _ = correr(e)
    assert g["estado"] == "revision_manual" and g["motivo_revision"] == "validacion_fallida"
    assert next(iter(e.almacen.solicitudes.values()))["citas_rechazadas"] == 1


@pytest.mark.pr("PR-02")
@pytest.mark.pr("PR-18")
@pytest.mark.rf("RF27")
def test_modo_registrado_por_etapa_en_telemetria():
    from kerna_comun import telemetria
    visto = []
    telemetria.quitar_emisores()
    telemetria.registrar_emisor(lambda clase, nombre, valor, at: visto.append((clase, nombre, dict(at))))
    try:
        e = armar(gemini=FakeGemini({FLASH: falla(503)}))
        correr(e)
    finally:
        telemetria.quitar_emisores()
    etapas = {n: a for c, n, a in visto if c == "etapa"}
    assert etapas["generacion"]["modo"] == "respaldo" and etapas["generacion"]["modelo"] == LITE
    assert etapas["generacion"]["proveedor"] == "gemini" and etapas["generacion"]["tokens_entrada"] == 100
    assert etapas["recuperacion"]["embedding"] == "voyage-4-large" and etapas["recuperacion"]["coleccion"] == "normativa_cl"
    assert etapas["recuperacion"]["version_corpus"] == 7
    assert {"anonimizacion", "clasificacion", "recuperacion", "generacion", "validacion"} <= set(etapas)
