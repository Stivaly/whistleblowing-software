import asyncio

import pytest

from kerna_nucleo.enrutador import CadenaAgotada, Enrutador, Nivel, PlazoAgotado
from kerna_nucleo.proveedores import ErrorProveedor
from nucleo_apoyo import FLASH, GEMMA, LITE, SILENCIO, FakeGemini, Reloj, falla, plazo_simulado

NIVELES = [Nivel("oficial", "gemini", FLASH), Nivel("respaldo", "gemini", LITE), Nivel("local", "gemini", GEMMA)]


def montar(comp, niveles=NIVELES):
    reloj, plazos = Reloj(), []
    g = FakeGemini(comp)
    return Enrutador(niveles, g, reloj=reloj, dormir=reloj.dormir, plazo_llamada=plazo_simulado(reloj, plazos)), g, reloj, plazos


def gen(r, inicio):
    return asyncio.run(r.generar("s", "u", None, lambda d: d, inicio))


@pytest.mark.pr("PR-04")
@pytest.mark.parametrize("codigo", [500, 503, 429])
def test_reintentos_con_esperas_1_2_4_ante_5xx_y_429_sostenido(codigo):
    r, g, reloj, _ = montar({FLASH: falla(codigo), LITE: falla(codigo), GEMMA: falla(codigo)})
    with pytest.raises(CadenaAgotada):
        gen(r, reloj())
    assert reloj.esperas == [1, 2, 4] * 3
    assert len([x for x in g.llamadas if x[0] == FLASH]) == 4


@pytest.mark.pr("PR-04")
def test_error_no_reintentable_pasa_directo_al_siguiente_nivel():
    r, g, reloj, _ = montar({FLASH: falla(400)})
    res = gen(r, reloj())
    assert res.modo == "respaldo" and reloj.esperas == []


@pytest.mark.pr("PR-04")
def test_recupera_en_el_segundo_intento_tras_esperar_1_s():
    n = {"i": 0}

    def a_medias(m, s, u, e):
        n["i"] += 1
        if n["i"] == 1:
            raise ErrorProveedor("gemini", 503, True)
        return FakeGemini.responder(m, s, u, {"properties": {"materia": 1}})
    r, _, reloj, _ = montar({FLASH: a_medias})
    res = gen(r, reloj())
    assert res.modo == "oficial" and reloj.esperas == [1] and res.intentos == 2


@pytest.mark.pr("PR-04")
def test_silencio_se_corta_a_30_s_por_llamada():
    r, g, reloj, plazos = montar({FLASH: SILENCIO, LITE: SILENCIO, GEMMA: SILENCIO})
    with pytest.raises((CadenaAgotada, PlazoAgotado)):
        gen(r, reloj())
    assert plazos[0] == 30 and max(plazos) == 30
    assert reloj.esperas[:3] == [1, 2, 4]


@pytest.mark.pr("PR-04")
def test_plazo_global_240_s_corta_la_cadena():
    r, g, reloj, plazos = montar({FLASH: SILENCIO, LITE: SILENCIO, GEMMA: SILENCIO})
    inicio = reloj()
    with pytest.raises(PlazoAgotado):
        gen(r, inicio)
    assert reloj() - inicio <= 240 + 1e-6
    assert all(p <= 30 for p in plazos)


@pytest.mark.pr("PR-04")
def test_salida_no_json_cuenta_como_falla_del_nivel():
    from kerna_nucleo.proveedores.gemini import RespuestaLLM
    r, g, reloj, _ = montar({FLASH: lambda *a: RespuestaLLM("no es json", 1, 1)})
    res = gen(r, reloj())
    assert res.modo == "respaldo"


@pytest.mark.pr("PR-02")
def test_cortocircuito_excluye_10_min_y_readmite_tras_salud():
    r, g, reloj, _ = montar({FLASH: falla(503)})
    gen(r, reloj())  # 4 fallas seguidas: nivel excluido
    n0 = len(g.llamadas) and len([x for x in g.llamadas if x[0] == FLASH])
    assert r.excluido(NIVELES[0])
    gen(r, reloj())
    assert len([x for x in g.llamadas if x[0] == FLASH]) == n0  # no se vuelve a llamar
    reloj.avanzar(601)
    g.sano[FLASH] = False  # la comprobación de salud falla: sigue excluido otros 10 min
    gen(r, reloj())
    assert len([x for x in g.llamadas if x[0] == FLASH]) == n0 and r.excluido(NIVELES[0])
    reloj.avanzar(601)
    g.sano[FLASH] = True
    g.comportamientos.pop(FLASH)
    res = gen(r, reloj())
    assert res.modo == "oficial" and not r.excluido(NIVELES[0])


@pytest.mark.pr("PR-02")
def test_tres_fallas_en_5_min_excluyen_pero_dos_no():
    r, g, reloj, _ = montar({FLASH: falla(400)})
    gen(r, reloj())
    gen(r, reloj())
    assert not r.excluido(NIVELES[0])
    gen(r, reloj())
    assert r.excluido(NIVELES[0])


@pytest.mark.pr("PR-02")
def test_fallas_espaciadas_mas_de_5_min_no_excluyen():
    r, g, reloj, _ = montar({FLASH: falla(400)})
    gen(r, reloj())
    gen(r, reloj())
    reloj.avanzar(301)
    gen(r, reloj())
    assert not r.excluido(NIVELES[0])
