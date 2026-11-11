"""Agente evaluador: guardias (ids inventados, citas literales, JSON inválido, ninguno aplica) y orden final."""
import asyncio

import pytest

from kerna_nucleo.enrutador import CadenaAgotada, PlazoAgotado, Resultado
from kerna_nucleo.evaluador import Evaluador, contiene

DENUNCIA = "Mi jefe me grita todos los días delante del equipo y me amenaza con despedirme si reclamo."
CANDS = [
    {"fragmento_id": f"a{i}", "norma": "Ley X", "articulo": str(i),
     "texto": f"Artículo {i}. El empleador deberá investigar la conducta de hostigamiento y proteger al trabajador."}
    for i in range(5)
]


def item(i, aplica=True, conf=0.8, hecho="me grita todos los días", frase="investigar la conducta de hostigamiento"):
    return {"id": f"a{i}", "aplica": aplica, "confianza": conf,
            "hecho_citado": hecho if aplica else "", "frase_articulo": frase if aplica else ""}


class Falso:
    def __init__(self, *respuestas):
        self.respuestas, self.llamadas = list(respuestas), 0

    async def __call__(self, sistema, usuario, esquema, validar, inicio):
        self.llamadas += 1
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return Resultado(validar(r), "oficial", "gemini", "m", 100, 20)


def correr(gen, cands=CANDS, **kw):
    return asyncio.run(Evaluador(gen, **kw).evaluar(DENUNCIA, cands, 0.0))


def ids(r):
    return [f["fragmento_id"] for f in r.fragmentos]


def test_ordena_por_confianza_con_desempate_por_orden_del_retriever():
    r = correr(Falso({"resultados": [item(0, False), item(1, conf=0.6), item(2, conf=0.9), item(3, conf=0.6),
                                     item(4, False)]}))
    assert r.usado and r.aplican == 3
    assert ids(r) == ["a2", "a1", "a3", "a0", "a4"]            # aplican primero, el resto en orden del retriever
    assert r.tokens_entrada == 100 and r.llamadas == 1


def test_sin_completar_solo_entrega_los_que_aplican():
    r = correr(Falso({"resultados": [item(2, conf=0.9)] + [item(i, False) for i in (0, 1, 3, 4)]}), completar=False)
    assert ids(r) == ["a2"]


def test_id_inventado_se_descarta():
    r = correr(Falso({"resultados": [dict(item(1), id="zzz"), item(2, conf=0.7)] + [item(i, False) for i in (0, 1, 3, 4)]}))
    assert r.descartados_id == 1 and "zzz" not in ids(r) and ids(r)[0] == "a2"


def test_hecho_citado_que_no_esta_en_la_denuncia_se_descarta():
    r = correr(Falso({"resultados": [item(1, hecho="me pegó en el estacionamiento"), item(2, conf=0.7)]
                      + [item(i, False) for i in (0, 3, 4)]}))
    assert r.descartados_cita == 1 and r.evaluaciones.get("a1") is None and ids(r)[0] == "a2"


def test_frase_del_articulo_que_no_esta_en_el_texto_se_descarta():
    r = correr(Falso({"resultados": [item(1, frase="sancionará con presidio mayor"), item(2, conf=0.7)]
                      + [item(i, False) for i in (0, 3, 4)]}))
    assert r.descartados_cita == 1 and ids(r)[0] == "a2"


def test_cita_literal_tolera_mayusculas_espacios_y_comillas():
    assert contiene(DENUNCIA, "«ME  grita todos\nlos días»")
    assert not contiene(DENUNCIA, "corto")      # citas triviales no cuentan


def test_ninguno_aplica_conserva_el_orden_del_retriever():
    r = correr(Falso({"resultados": [item(i, False) for i in range(5)]}))
    assert r.usado and r.aplican == 0 and r.motivo == "ninguno_aplica" and ids(r) == ["a0", "a1", "a2", "a3", "a4"]


def test_json_invalido_se_reintenta_una_vez():
    g = Falso(ValueError("json"), {"resultados": [item(3, conf=0.9)] + [item(i, False) for i in (0, 1, 2, 4)]})
    r = correr(g)
    assert g.llamadas == 2 and ids(r)[0] == "a3"


def test_json_invalido_dos_veces_conserva_el_orden_del_retriever():
    g = Falso(ValueError("json"), CadenaAgotada())
    r = correr(g)
    assert g.llamadas == 2 and not r.usado and r.motivo == "evaluador_fallido" and ids(r) == ["a0", "a1", "a2", "a3", "a4"]


def test_forma_invalida_se_trata_como_json_invalido():
    g = Falso({"otra": 1}, {"resultados": "x"})
    r = correr(g)
    assert not r.usado


def test_plazo_agotado_se_propaga():
    with pytest.raises(PlazoAgotado):
        correr(Falso(PlazoAgotado()))


def test_lotes_dividen_los_candidatos_y_salida_limitada():
    g = Falso({"resultados": [item(0, conf=0.5), item(1, conf=0.9)]},
              {"resultados": [item(2, conf=0.7), item(3, False)]},
              {"resultados": [item(4, False)]})
    r = correr(g, lote=2, salida=3)
    assert g.llamadas == 3 and ids(r) == ["a1", "a2", "a0"]


def test_un_solo_candidato_no_llama_al_modelo():
    g = Falso()
    r = correr(g, CANDS[:1])
    assert g.llamadas == 0 and not r.usado


# ---- integración en el flujo del núcleo (KERNA_EVALUADOR)
import json  # noqa: E402
import re  # noqa: E402

from kerna_nucleo.config import Config  # noqa: E402
from nucleo_apoyo import FakeGemini, armar, json_ok, procesar_caso  # noqa: E402


def _responder_evaluador(modelo, sistema, usuario, esquema):
    if "resultados" in ((esquema or {}).get("properties") or {}):
        ids = re.findall(r'<fragmento id="([^"]+)"', usuario)
        return json_ok({"resultados": [
            {"id": i, "aplica": i == "cdt_art2", "confianza": 0.9,
             "hecho_citado": "presiona de forma reiterada" if i == "cdt_art2" else "",
             "frase_articulo": "trato compatible con la dignidad" if i == "cdt_art2" else ""} for i in ids]})
    return FakeGemini.responder(modelo, sistema, usuario, esquema)


def _config(**kw):
    import hashlib
    from nucleo_apoyo import SECRETO
    return Config(clientes={"conector": {"secreto_sha256": hashlib.sha256(SECRETO.encode()).hexdigest(),
                                         "cliente": "conector"}}, jwt_secreto="x" * 40, umbral_similitud=0.3,
                  top_k=2, **kw)


def _orden_en_generador(e):
    u = e.gemini.generacion()[-1][2]
    return re.findall(r'fragmento_id="([^"]+)"', u)


def test_flujo_con_evaluador_apagado_no_lo_llama():
    e = armar(gemini=FakeGemini({m: _responder_evaluador for m in ("gemini-3.8-flash", "gemini-3.5-flash-lite")}),
              config=_config())
    asyncio.run(procesar_caso(e))
    assert not [x for x in e.gemini.llamadas if "resultados" in ((x[3] or {}).get("properties") or {})]
    assert _orden_en_generador(e) == ["ley21643_art1", "cdt_art2"]


def test_flujo_con_evaluador_encendido_reordena_para_el_agente_final():
    e = armar(gemini=FakeGemini({m: _responder_evaluador for m in ("gemini-3.8-flash", "gemini-3.5-flash-lite")}),
              config=_config(evaluador=True, evaluador_candidatos=2))
    asyncio.run(procesar_caso(e))
    assert _orden_en_generador(e)[0] == "cdt_art2"


def test_cita_con_elipsis_exige_cada_tramo_literal():
    assert contiene(DENUNCIA, "me grita todos los días [...] me amenaza con despedirme")
    assert contiene(DENUNCIA, "Mi jefe me grita... y me amenaza con despedirme")
    assert not contiene(DENUNCIA, "me grita todos los días [...] me golpea en el pasillo")
