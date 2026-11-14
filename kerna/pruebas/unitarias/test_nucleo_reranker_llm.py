"""Reranker LLM listwise y completado del generador: permutaciones, Borda, IDs inválidos, fallas y citas literales."""
import asyncio
from types import SimpleNamespace

from kerna_nucleo.config import Config
from kerna_nucleo.enrutador import CadenaAgotada, Resultado
from kerna_nucleo.orquestador import Orquestador
from kerna_nucleo.reranker_llm import RerankerLLM, perfil_articulo, usuario

DENUNCIA = "Mi jefe me grita todos los días delante del equipo. Me amenaza con despedirme si reclamo."
TEXTO = "Artículo 5.- Deber de investigar. El empleador deberá investigar la conducta de hostigamiento conforme a la ley."
CANDS = [{"fragmento_id": f"f{i}", "norma": "Ley X", "articulo": str(i), "texto": TEXTO,
          "enriquecimiento": f"Situación típica {i}", "rol": "sustantivo"} for i in range(1, 7)]


class Falso:
    def __init__(self, *resp):
        self.resp, self.usuarios = list(resp), []

    async def __call__(self, sistema, usuario_, esquema, validar, inicio):
        self.usuarios.append(usuario_)
        r = self.resp.pop(0)
        if isinstance(r, Exception):
            raise r
        return Resultado(validar({"ranking": r}), "oficial", "azure-openai", "m", 100, 20)


def correr(gen, **kw):
    return asyncio.run(RerankerLLM(gen, **kw).reordenar(DENUNCIA, CANDS, 0.0))


def test_borda_de_dos_permutaciones_y_resto_en_orden_de_entrada():
    # permutación 1 (orden f1..f6): A3 > A1; permutación 2 (invertida: A1=f6, A2=f5, A3=f4...): A1 = f6
    r = correr(Falso(["A3", "A1"], ["A1", "A3"]))
    ids = [f["fragmento_id"] for f in r.fragmentos]
    assert r.usado and r.permutaciones == 2
    assert ids == ["f3", "f6", "f1", "f4", "f2", "f5"]
    assert r.fragmentos[0]["rerank_llm"] and not r.fragmentos[-1]["rerank_llm"]


def test_ids_inventados_y_repetidos_se_descartan():
    r = correr(Falso(["A9", "A2", "A2", "zz"], ["A5"]))
    assert r.descartados_id == 2 and r.fragmentos[0]["fragmento_id"] == "f2"


def test_una_permutacion_fallida_usa_la_otra():
    r = correr(Falso(CadenaAgotada(), ["A1"]))
    assert r.usado and r.permutaciones == 1


def test_ambas_fallan_conserva_orden():
    r = correr(Falso(CadenaAgotada(), CadenaAgotada()))
    assert not r.usado and r.motivo == "reranker_fallido"
    assert [f["fragmento_id"] for f in r.fragmentos] == [f["fragmento_id"] for f in CANDS]


def test_voto_del_evaluador_desempata():
    r = correr(Falso(["A1"], ["A6"]), voto_evaluador=0.5)   # empatan f1 y f1... A6 en invertida = f1
    assert r.fragmentos[0]["fragmento_id"] == "f1"
    r2 = correr(Falso(["A2"], ["A5"]), voto_evaluador=3.0)
    assert r2.usado


def test_perfil_usa_enriquecimiento_o_inicio_del_texto():
    assert "Situaciones típicas: Situación típica 1" in perfil_articulo(CANDS[0])
    sin = dict(CANDS[0], enriquecimiento="")
    assert "Texto: Artículo 5" in perfil_articulo(sin)
    assert DENUNCIA.split(".")[0] in usuario(["H"], CANDS) or "H1" in usuario(["x"], CANDS)


def _orq(**kw):
    c = Config()
    for k, v in kw.items():
        setattr(c, k, v)
    return Orquestador(c, None, None, None, lambda: 0.0)


def _acept(f, conf=0.9):
    return {"fragmento": f, "cita": "El empleador deberá investigar", "confianza": conf, "explicacion": "x"}


def test_completar_sigue_el_orden_y_agrega_omitidos_con_cita_literal():
    frags = [dict(f, puntaje_evaluador=p, frase_ids_evaluador=[]) for f, p in zip(CANDS, [3, 2, 1, 0, 3, 2])]
    o = _orq(generador_completar=5, generador_min_puntaje=1)
    out = o._completar([_acept(frags[1])], frags)
    ids = [a["fragmento"]["fragmento_id"] for a in out]
    assert ids == ["f1", "f2", "f3", "f5"]  # f4 (puntaje 0) no se completa; f6 queda fuera de las 5 primeras posiciones
    assert out[1]["confianza"] == 0.9 and out[0]["confianza"] == 0.6
    from kerna_nucleo.validador import normalizar
    assert all(normalizar(a["cita"]) in normalizar(TEXTO) for a in out)


def test_completar_incluye_los_reordenados_por_el_reranker_y_respeta_el_maximo():
    frags = [dict(f, rerank_llm=True) for f in CANDS]
    out = _orq(generador_completar=5, max_articulos=5)._completar([], frags)
    assert [a["fragmento"]["fragmento_id"] for a in out] == ["f1", "f2", "f3", "f4", "f5"]


def test_cuatro_permutaciones_incluyen_rotada_e_invertida_y_criterios_en_el_sistema():
    sistemas = []

    class Gen(Falso):
        async def __call__(self, sistema, usuario_, esquema, validar, inicio):
            sistemas.append(sistema)
            return await super().__call__(sistema, usuario_, esquema, validar, inicio)

    g = Gen(["A1"], ["A1"], ["A1"], ["A1"])
    r = correr(g, permutaciones=4, criterios=True)
    assert r.permutaciones == 4 and len(g.usuarios) == 4
    assert "[A1] Ley X" in g.usuarios[0] and all("CRITERIOS POR LEY" in s for s in sistemas)
    assert g.usuarios[2] != g.usuarios[0] and g.usuarios[3] != g.usuarios[1]
    assert Config().rerank_llm_permutaciones == 2 and Config().rerank_llm_criterios is False
