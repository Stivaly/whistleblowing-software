"""Ajustes del panel en el núcleo: funciones puras, lector con tabla falsa y efecto en la cadena (sin red)."""
import asyncio
import hashlib
import json
import re
import uuid

import pytest

from kerna_nucleo import ajustes_vivos as av
from kerna_nucleo.ajustes_vivos import AjustesVivos, aplicar_config, aplicar_niveles
from kerna_nucleo.almacen import AlmacenMemoria
from kerna_nucleo.api import crear_app
from kerna_nucleo.config import Config
from kerna_nucleo.enrutador import Nivel
from kerna_nucleo.proveedores import Proveedores
from nucleo_apoyo import (FLASH, GEMMA, LITE, SECRETO, FakeGemini, FakeLocal, FakeQdrant, FakeVoyage, Reloj,
                          cabeceras, cliente_http, json_ok, plazo_simulado)

AZ, GM = "azure-openai", "gemini"
BASE = [Nivel("oficial", AZ, "gpt-5-nano"), Nivel("respaldo", GM, FLASH), Nivel("respaldo", GM, LITE), Nivel("local", GM, GEMMA)]
EF = {"evaluador": True, "candidatos": 70, "cadena": [{"v": "azure", "on": True}, {"v": "gemini", "on": True}], "guardado_en": "2026-11-17T10:00:00Z"}


def ef(**kw):
    return {**EF, **kw}


def modelos(ns):
    return [(n.modelo, n.modo) for n in ns]


# ---- funciones puras
def test_aplicar_config_copia_y_limita_candidatos():
    cfg = Config(evaluador=False, evaluador_candidatos=30)
    c = aplicar_config(cfg, ef(evaluador=True, candidatos=40), 70)
    assert c is not cfg and c.evaluador is True and c.evaluador_candidatos == 40
    assert cfg.evaluador is False and cfg.evaluador_candidatos == 30
    assert aplicar_config(cfg, ef(candidatos=70), 30).evaluador_candidatos == 30


def test_aplicar_niveles_orden_azure_gemini_y_etiquetas():
    n = aplicar_niveles(BASE, EF["cadena"])
    assert modelos(n) == [("gpt-5-nano", "oficial"), (FLASH, "respaldo"), (LITE, "respaldo"), (GEMMA, "local")]
    g = aplicar_niveles(BASE, [{"v": "gemini", "on": True}, {"v": "azure", "on": True}])
    assert modelos(g) == [(FLASH, "oficial"), (LITE, "respaldo"), (GEMMA, "local"), ("gpt-5-nano", "respaldo")]
    assert BASE[0].modo == "oficial" and BASE[1].modo == "respaldo"  # los base no se tocan


def test_aplicar_niveles_apagar_uno_y_lista_vacia():
    solo_g = aplicar_niveles(BASE, [{"v": "azure", "on": False}, {"v": "gemini", "on": True}])
    assert modelos(solo_g) == [(FLASH, "oficial"), (LITE, "respaldo"), (GEMMA, "local")]
    solo_a = aplicar_niveles(BASE, [{"v": "azure", "on": True}, {"v": "gemini", "on": False}])
    assert modelos(solo_a) == [("gpt-5-nano", "oficial")]
    assert modelos(aplicar_niveles(BASE, [{"v": "azure", "on": False}, {"v": "gemini", "on": False}])) == modelos(BASE)
    solo_gemini = [n for n in BASE if n.proveedor == GM]
    assert modelos(aplicar_niveles(solo_gemini, [{"v": "azure", "on": True}, {"v": "gemini", "on": False}])) == modelos(solo_gemini)


# ---- lector con tabla falsa
class TablaFalsa:
    def __init__(self, fila=None, error=None):
        self.fila, self.error, self.lecturas = fila, error, 0

    def get_entity(self, pk, rk):
        self.lecturas += 1
        assert (pk, rk) == ("kerna", "actual")
        if self.error:
            raise self.error
        if self.fila is None:
            from azure.core.exceptions import ResourceNotFoundError
            raise ResourceNotFoundError("no")
        return self.fila


def fila(**v):
    return {"valores": json.dumps({"evaluador": False, "candidatos": 20, **v}), "actualizado_en": "2026-11-17T11:00:00Z"}


def test_lector_ttl_y_valores():
    t, r = TablaFalsa(fila()), [0.0]
    a = AjustesVivos(t, ttl_s=20, reloj=lambda: r[0])
    v = asyncio.run(a.efectivos())
    assert v["evaluador"] is False and v["candidatos"] == 20 and v["guardado_en"] == "2026-11-17T11:00:00Z"
    assert v["cadena"][0] == {"v": "azure", "on": True}
    r[0] = 19
    asyncio.run(a.efectivos())
    assert t.lecturas == 1
    t.fila = fila(candidatos=40)
    r[0] = 21
    assert asyncio.run(a.efectivos())["candidatos"] == 40 and t.lecturas == 2


def test_lector_falla_conserva_el_ultimo_valor_bueno_y_no_lanza():
    t, r = TablaFalsa(fila()), [0.0]
    a = AjustesVivos(t, ttl_s=20, reloj=lambda: r[0])
    asyncio.run(a.efectivos())
    t.error, r[0] = RuntimeError("caído"), 100
    assert asyncio.run(a.efectivos())["candidatos"] == 20
    t.error = None
    r[0] = 200
    assert asyncio.run(a.efectivos())["candidatos"] == 20
    a2 = AjustesVivos(TablaFalsa(error=RuntimeError("x")))
    assert asyncio.run(a2.efectivos()) is None


def test_lector_fila_ausente_none_e_invalida_ignorada():
    assert asyncio.run(AjustesVivos(TablaFalsa(None)).efectivos()) is None
    assert asyncio.run(AjustesVivos(None).efectivos()) is None
    t, r = TablaFalsa(fila()), [0.0]
    a = AjustesVivos(t, ttl_s=20, reloj=lambda: r[0])
    asyncio.run(a.efectivos())
    for malo in ({"valores": "no es json", "actualizado_en": "x"}, fila(candidatos=75), {"actualizado_en": "x"}):
        t.fila, r[0] = malo, r[0] + 30
        assert asyncio.run(a.efectivos())["candidatos"] == 20
    inicial = AjustesVivos(TablaFalsa(fila(candidatos=75)))
    assert asyncio.run(inicial.efectivos()) is None


def test_desde_config_sin_url_es_none(monkeypatch):
    monkeypatch.delenv("AJUSTES_TABLA_URL", raising=False)
    assert AjustesVivos.desde_config(Config()) is None


# ---- integración sin red: Orquestador + AlmacenMemoria + proveedores falsos
class AjustesFalsos:
    def __init__(self, ef_=None):
        self.ef, self.llamadas = ef_, 0

    async def efectivos(self):
        self.llamadas += 1
        return self.ef


def _responder_evaluador(modelo, sistema, usuario, esquema):
    if "resultados" in ((esquema or {}).get("properties") or {}):
        ids = re.findall(r'<fragmento id="([^"]+)"', usuario)
        return json_ok({"resultados": [{"id": i, "aplica": i == "cdt_art2", "confianza": 0.9,
                                        "hecho_citado": "presiona de forma reiterada" if i == "cdt_art2" else "",
                                        "frase_articulo": "trato compatible con la dignidad" if i == "cdt_art2" else ""} for i in ids]})
    return FakeGemini.responder(modelo, sistema, usuario, esquema)


def montar(ajustes=None, evaluador=False, candidatos=30, azure=True):
    reloj, plazos = Reloj(), []
    gem = FakeGemini({m: _responder_evaluador for m in (FLASH, LITE, GEMMA)})
    az = FakeGemini({"gpt-5-nano": _responder_evaluador}) if azure else None
    cadena = [{"modo": "oficial", "proveedor": AZ, "modelo": "gpt-5-nano"},
              {"modo": "respaldo", "proveedor": GM, "modelo": FLASH},
              {"modo": "respaldo", "proveedor": GM, "modelo": LITE},
              {"modo": "local", "proveedor": GM, "modelo": GEMMA}]
    cfg = Config(clientes={"conector": {"secreto_sha256": hashlib.sha256(SECRETO.encode()).hexdigest(), "cliente": "conector"}},
                 jwt_secreto="x" * 40, umbral_similitud=0.3, top_k=2, evaluador=evaluador, evaluador_candidatos=candidatos, cadena=cadena)
    prov = Proveedores(gem, FakeVoyage(), FakeQdrant(), FakeLocal(), dormir=reloj.dormir, plazo_llamada=plazo_simulado(reloj, plazos), azure_openai=az)
    app = crear_app(cfg, AlmacenMemoria(), prov, reloj, ajustes=ajustes)
    return type("E", (), {"app": app, "gemini": gem, "azure": az, "config": cfg})


async def caso(e, texto="Un jefe presiona de forma reiterada a su equipo."):
    ref = str(uuid.uuid4())
    async with cliente_http(e.app) as c:
        h = await cabeceras(c)
        r = await c.post("/v1/casos", json={"ref_opaca": ref, "id_empresa": "e1", "texto": texto}, headers=h)
        assert r.status_code == 202
        await e.app.state.esperar_tareas()
        return (await c.get(f"/v1/casos/{ref}/sugerencia", headers=h)).json()


def evaluaciones(proveedor):
    return [x for x in proveedor.llamadas if "resultados" in ((x[3] or {}).get("properties") or {})]


def test_sin_ajustes_la_cadena_es_la_base():
    e = montar(None)
    g = asyncio.run(caso(e))
    assert g["modo"] == "oficial" and e.azure.generacion() and not e.gemini.generacion()
    assert not evaluaciones(e.azure) and not evaluaciones(e.gemini)  # evaluador apagado en la base


def test_ajustes_none_rigen_las_variables_de_entorno():
    aj = AjustesFalsos(None)
    e = montar(aj)
    g = asyncio.run(caso(e))
    assert aj.llamadas == 1 and g["modo"] == "oficial" and e.azure.generacion()


def test_evaluador_apagado_no_llama_al_evaluador():
    e = montar(AjustesFalsos(ef(evaluador=False)), evaluador=True)
    asyncio.run(caso(e))
    assert not evaluaciones(e.azure) and not evaluaciones(e.gemini)


def test_evaluador_encendido_por_ajustes_aunque_la_variable_este_apagada():
    e = montar(AjustesFalsos(ef(evaluador=True, candidatos=10)), evaluador=False)
    asyncio.run(caso(e))
    assert len(evaluaciones(e.azure)) == 1


def test_candidatos_limita_lo_que_ve_el_evaluador():
    e = montar(AjustesFalsos(ef(candidatos=10)), evaluador=True, candidatos=30)
    # el retriever solo devuelve 2 fragmentos de prueba: se fuerza el tope observando la configuración efectiva
    visto = []
    from kerna_nucleo import orquestador as orq
    original = orq.Orquestador._evaluar

    async def espia(self, limpio, candidatos, *a, **k):
        visto.append(self.config.evaluador_candidatos)
        return await original(self, limpio, candidatos, *a, **k)
    orq.Orquestador._evaluar = espia
    try:
        asyncio.run(caso(e))
    finally:
        orq.Orquestador._evaluar = original
    assert visto == [10]
    assert e.config.evaluador_candidatos == 30  # la base no cambia


def test_cadena_gemini_primero_el_primer_intento_es_gemini_y_modo_oficial():
    e = montar(AjustesFalsos(ef(cadena=[{"v": "gemini", "on": True}, {"v": "azure", "on": True}])))
    g = asyncio.run(caso(e))
    assert g["modo"] == "oficial" and e.gemini.generacion(FLASH) and not e.azure.llamadas


def test_cadena_con_azure_apagado_nunca_lo_llama():
    e = montar(AjustesFalsos(ef(cadena=[{"v": "azure", "on": False}, {"v": "gemini", "on": True}])))
    asyncio.run(caso(e))
    assert not e.azure.llamadas and e.gemini.generacion()


def test_dos_casos_concurrentes_con_ajustes_distintos_no_se_pisan():
    class Alternos:
        def __init__(self):
            self.n = 0

        async def efectivos(self):
            self.n += 1
            if self.n == 1:
                await asyncio.sleep(0)
                return ef(cadena=[{"v": "gemini", "on": True}, {"v": "azure", "on": True}])
            return ef()
    e = montar(Alternos())

    async def dos():
        return await asyncio.gather(caso(e), caso(e))
    asyncio.run(dos())
    assert len(e.azure.generacion()) == 1 and len(e.gemini.generacion(FLASH)) == 1


def test_contextvars_se_restablecen_al_terminar():
    from kerna_nucleo.enrutador import NIVELES_CASO
    from kerna_nucleo.orquestador import _CONFIG_CASO
    e = montar(AjustesFalsos(ef(candidatos=10)))
    asyncio.run(caso(e))
    assert NIVELES_CASO.get() is None and _CONFIG_CASO.get() is None


def test_telemetria_ajustes_aplicados_una_vez_por_guardado(monkeypatch):
    eventos = []
    from kerna_comun import telemetria
    original = telemetria.evento
    monkeypatch.setattr(telemetria, "evento", lambda n, **c: (eventos.append((n, c)), original(n, **c))[1])
    e = montar(AjustesFalsos(ef(candidatos=40, cadena=[{"v": "gemini", "on": True}, {"v": "azure", "on": True}])), evaluador=True, candidatos=50)

    async def dos():
        await caso(e)
        await caso(e)
    asyncio.run(dos())
    ap = [c for n, c in eventos if n == "ajustes_aplicados"]
    assert len(ap) == 1 and ap[0]["candidatos"] == 40 and ap[0]["cadena"] == "gemini>azure" and ap[0]["guardado_en"]
    fin = [c for n, c in eventos if n == "solicitud_terminada"]
    assert len(fin) == 2 and all(c["ajustes_de_tabla"] is True and c["candidatos"] == 40 and c["evaluador"] is True for c in fin)
    assert "presiona" not in json.dumps(eventos, default=str)


def test_ajustes_desactivados_con_almacen_memoria(monkeypatch):
    llamado = []
    monkeypatch.setattr(av.AjustesVivos, "desde_config", classmethod(lambda cls, cfg: llamado.append(1)))
    montar(None)
    assert not llamado
