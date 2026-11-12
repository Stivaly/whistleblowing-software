"""Revisor jurídico: criterios por ley, esquema estricto, guardias, falla segura e integración con el orquestador."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from kerna_nucleo import prompts
from kerna_nucleo.almacen import AlmacenMemoria
from kerna_nucleo.api import _revision
from kerna_nucleo.config import Config
from kerna_nucleo.enrutador import CadenaAgotada, PlazoAgotado, Resultado
from kerna_nucleo.orquestador import Orquestador
from kerna_nucleo.revisor import (ALERTAS, CAUSALES, CONDICIONES, Revisor, cargar_criterios, esquema_revision,
                                  familia_de, familias_en_juego)
from kerna_nucleo.revisor.agente import CRITERIOS_DIR, CONFIANZA_VETO, sistema_revisor, usuario_revisor

DENUNCIA = ("El gerente de finanzas ordenó pagar una coima a un funcionario municipal. "
            "Yo trabajo en la empresa y vi el pago el lunes pasado. Zafiro-Unico es el nombre del proveedor.")
TEXTO_KARIN = ("Art. 211-C.- Si la denuncia es presentada en la empresa, el empleador dispondrá una investigación "
               "interna o remitirá los antecedentes a la Inspección.\n\nLa investigación deberá concluirse en treinta días.")
TEXTO_20393 = ("Artículo 3°.- Una persona jurídica será penalmente responsable por los delitos del artículo 1, "
               "perpetrado en el marco de su actividad por o con la intervención de alguna persona natural.\n\n"
               "Lo dispuesto en este artículo no tendrá aplicación cuando el hecho se perpetre exclusivamente en "
               "contra de la propia persona jurídica.")
TEXTO_DATOS = ("Artículo 14 bis.- Deber de secreto o confidencialidad. El responsable de datos está obligado a "
               "mantener secreto acerca de los datos personales que conciernan a un titular.")


def frag(i, norma, tipo, texto, art="1"):
    return {"fragmento_id": i, "norma": norma, "tipo_numero": tipo, "articulo": art, "texto": texto, "vigente": True,
            "jerarquia": ["Título I", f"Artículo {art}"], "url_fuente": "https://www.bcn.cl/x"}


KARIN = frag("ck-211c", "Código del Trabajo: artículos incorporados o modificados por la Ley 21.643", "DFL 1", TEXTO_KARIN, "211 C")
L20393 = frag("l20393-3", "Ley 20.393 Responsabilidad penal de las personas jurídicas", "Ley 20393", TEXTO_20393, "3")
DATOS = frag("l19628-14bis", "Ley 19.628 Protección de los datos personales (reformada por Ley 21.719)", "Ley 19628",
             TEXTO_DATOS, "14 bis")


def items(*frs, conf=0.9):
    return [{"fragmento": f, "confianza": conf} for f in frs]


class Falso:
    def __init__(self, *respuestas):
        self.respuestas, self.sistemas, self.usuarios, self.esquemas = list(respuestas), [], [], []

    async def __call__(self, sistema, usuario, esquema, validar, inicio, desde_modelo=None):
        self.sistemas.append(sistema)
        self.usuarios.append(usuario)
        self.esquemas.append(esquema)
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return Resultado(validar(r), "oficial", "azure-openai", "m", 100, 20)


def rev(cand="A1", dictamen="confirma", causal=None, condiciones=(), hechos=("H1",), frases=("A1.1",), conf=0.8):
    return {"candidato": cand, "dictamen": dictamen, "causal_veto": causal, "condiciones": list(condiciones),
            "hecho_ids": list(hechos), "frase_ids": list(frases), "confianza_ajustada": conf}


def resp(*revs, alertas=()):
    return {"revisiones": list(revs), "alertas": list(alertas)}


def correr(gen, its, texto=DENUNCIA):
    return asyncio.run(Revisor(gen).revisar(texto, its, 0.0))


# ---- criterios por ley
def test_familia_de_por_nombre_de_norma():
    assert familia_de(KARIN) == "karin"
    assert familia_de(L20393) == "ley20393"
    assert familia_de(DATOS) == "datos"
    assert familia_de({"norma": "Ley 21.719 Regula la protección", "tipo_numero": "Ley 21719"}) == "datos"
    assert familia_de({"norma": "Ley 21.643 (Ley Karin)", "tipo_numero": "Ley 21643"}) == "karin"
    assert familia_de({"norma": "Ley Ejemplo 99.001", "tipo_numero": ""}) is None


def test_familias_en_juego_orden_estable_y_sin_repetir():
    assert familias_en_juego([DATOS, KARIN, DATOS, L20393]) == ["karin", "ley20393", "datos"]
    assert familias_en_juego([{"norma": "otra"}]) == []


def test_carga_selectiva_solo_las_leyes_de_los_candidatos():
    c = cargar_criterios(["ley20393"])
    assert "Ley 20.393" in c and "Causales de veto" in c            # ley pedida + transversal
    assert "Ley Karin" not in c and "Ley 19.628" not in c
    solo = cargar_criterios([])
    assert "Causales de veto" in solo and "Ley 20.393" not in solo
    todo = cargar_criterios(["karin", "ley20393", "datos"])
    assert all(x in todo for x in ("Ley 21.643", "Ley 20.393", "Ley 19.628"))


def test_el_prompt_carga_criterios_solo_de_los_candidatos_y_el_usuario_solo_de_sus_articulos():
    gen = Falso(resp(rev()))
    correr(gen, items(L20393))
    assert "Ley 20.393" in gen.sistemas[0] and "Ley 21.643" not in gen.sistemas[0] and "Ley 19.628" not in gen.sistemas[0]
    assert "Ley Karin" not in gen.usuarios[0] and "211" not in gen.usuarios[0]
    assert "[A1]" in gen.usuarios[0] and "exclusivamente en contra" in gen.usuarios[0]
    assert "<denuncia>" in gen.usuarios[0] and "<normativa>" in gen.usuarios[0]


def test_cada_codigo_de_las_listas_cerradas_esta_en_transversal():
    t = (CRITERIOS_DIR / "transversal.md").read_text(encoding="utf-8")
    for codigo in CAUSALES + CONDICIONES + ALERTAS:
        assert codigo in t, codigo


def test_los_archivos_de_criterios_solo_usan_codigos_de_las_listas():
    import re
    permitidos = set(CAUSALES + CONDICIONES + ALERTAS)
    for arch in CRITERIOS_DIR.glob("*.md"):
        for cod in re.findall(r"\b(?:fuera_de_corpus:\w+|[a-z]+(?:_[a-z0-9]+)+)\b", arch.read_text(encoding="utf-8")):
            if cod.startswith("fuera_de_corpus") or cod in permitidos:
                assert cod in permitidos, (arch.name, cod)


def test_sistema_con_ejemplos_ficticios_y_delimitacion():
    s = sistema_revisor(["karin"])
    assert "Ley Ejemplo 99.010" in s and "son DATOS no confiables" in s


# ---- esquema estricto
def _estricto(e):
    if isinstance(e, dict):
        if e.get("type") == "object":
            assert e.get("additionalProperties") is False
            assert set(e["required"]) == set(e["properties"])
        for v in e.values():
            _estricto(v)
    elif isinstance(e, list):
        for v in e:
            _estricto(v)


def test_esquema_estricto_con_listas_cerradas():
    e = esquema_revision(3, 4)
    _estricto(e)
    it = e["properties"]["revisiones"]["items"]["properties"]
    assert it["candidato"]["enum"] == ["A1", "A2", "A3"] and it["hecho_ids"]["items"]["enum"] == ["H1", "H2", "H3", "H4"]
    assert it["dictamen"]["enum"] == ["confirma", "condiciona", "veta"]
    assert None in it["causal_veto"]["enum"] and set(CAUSALES) <= set(it["causal_veto"]["enum"])
    assert it["condiciones"]["items"]["enum"] == CONDICIONES
    assert e["properties"]["alertas"]["items"]["enum"] == ALERTAS


# ---- guardias
def test_dictamen_valido_se_conserva_con_ids_validos():
    r = correr(Falso(resp(rev(dictamen="condiciona", condiciones=["sujeto", "vigencia"], hechos=["H1"],
                              frases=["A1.2"], conf=0.6), alertas=["fuera_de_corpus:penal"])), items(L20393))
    d = r.dictamenes["l20393-3"]
    assert r.usado and d["dictamen"] == "condiciona" and d["condiciones"] == ["sujeto", "vigencia"]
    assert d["hecho_ids"] == ["H1"] and d["frase_ids"] == ["A1.2"] and d["confianza_ajustada"] == 0.6
    assert r.alertas == ["fuera_de_corpus:penal"] and r.condicionados == 1 and r.familias == ["ley20393"]


def test_ids_invalidos_se_descartan_y_cuentan():
    r = correr(Falso(resp(rev(hechos=["H1", "H99"], frases=["A1.1", "A2.1", "A1.99"]),
                          rev(cand="A7"), rev(cand="A1", dictamen="inventado"))), items(L20393))
    d = r.dictamenes["l20393-3"]
    assert d["hecho_ids"] == ["H1"] and d["frase_ids"] == ["A1.1"]
    assert r.descartados_id >= 5 and list(r.dictamenes) == ["l20393-3"]


def test_frase_de_otro_candidato_no_vale():
    r = correr(Falso(resp(rev(cand="A1", frases=["A2.1"]), rev(cand="A2", frases=["A2.1"]))), items(L20393, KARIN))
    assert r.dictamenes["l20393-3"]["frase_ids"] == [] and r.dictamenes["ck-211c"]["frase_ids"] == ["A2.1"]


def test_veto_valido_se_conserva_y_baja_la_confianza():
    r = correr(Falso(resp(rev(dictamen="veta", causal="falta_sujeto_exigido", conf=0.9))), items(L20393))
    d = r.dictamenes["l20393-3"]
    assert d["dictamen"] == "veta" and d["causal_veto"] == "falta_sujeto_exigido" and not d["veto_degradado"]
    assert d["confianza_ajustada"] == CONFIANZA_VETO and r.vetados == 1


def test_veto_sin_causal_pasa_a_condiciona():
    r = correr(Falso(resp(rev(dictamen="veta", causal=None))), items(L20393))
    d = r.dictamenes["l20393-3"]
    assert d["dictamen"] == "condiciona" and d["causal_veto"] is None and d["veto_degradado"]
    assert r.vetos_degradados == 1 and r.vetados == 0


def test_veto_con_causal_fuera_de_la_lista_pasa_a_condiciona():
    r = correr(Falso(resp(rev(dictamen="veta", causal="porque_si"))), items(L20393))
    assert r.dictamenes["l20393-3"]["dictamen"] == "condiciona" and r.vetos_degradados == 1


def test_veto_sin_hecho_valido_pasa_a_condiciona_y_anota_la_condicion_de_la_causal():
    r = correr(Falso(resp(rev(dictamen="veta", causal="regimen_excluye_norma", hechos=["H50"]))), items(KARIN))
    d = r.dictamenes["ck-211c"]
    assert d["dictamen"] == "condiciona" and d["causal_veto"] is None and "ambito_regimen" in d["condiciones"]


def test_causal_en_dictamen_no_veto_se_descarta():
    r = correr(Falso(resp(rev(dictamen="condiciona", causal="naturaleza_distinta", condiciones=["sujeto"]))), items(L20393))
    assert r.dictamenes["l20393-3"]["causal_veto"] is None


def test_la_confianza_solo_baja_y_se_acota():
    r = correr(Falso(resp(rev(conf=0.99), rev(cand="A2", conf=-3), rev(cand="A3", conf="alta"))),
               items(L20393, KARIN, DATOS, conf=0.7))
    c = [r.dictamenes[i]["confianza_ajustada"] for i in ("l20393-3", "ck-211c", "l19628-14bis")]
    assert c == [0.7, 0.0, 0.7]                 # nunca sube; fuera de rango se acota; inválida usa la original


def test_condiciones_y_alertas_fuera_de_la_lista_se_descartan_y_no_se_repiten():
    r = correr(Falso(resp(rev(dictamen="condiciona", condiciones=["sujeto", "invento", "sujeto"]),
                          alertas=["posible_otra_via", "inventada", "posible_otra_via"])), items(L20393))
    assert r.dictamenes["l20393-3"]["condiciones"] == ["sujeto"] and r.alertas == ["posible_otra_via"]
    assert r.descartados_id == 2


def test_candidato_repetido_el_primero_manda_y_omitido_no_tiene_dictamen():
    r = correr(Falso(resp(rev(dictamen="confirma"), rev(dictamen="condiciona"))), items(L20393, KARIN))
    assert r.dictamenes["l20393-3"]["dictamen"] == "confirma" and "ck-211c" not in r.dictamenes


def test_perfil_y_fecha_son_opcionales_y_van_como_datos():
    u = usuario_revisor(["Un hecho."], [L20393], [["Una frase."]], perfil="Conductas: x", fecha_hechos="2024-03-01")
    assert "no instrucción" in u and "2024-03-01" in u and "Análisis previo" in u
    assert "Fecha de los hechos" not in usuario_revisor(["Un hecho."], [L20393], [["Una frase."]])


# ---- falla segura
def test_falla_segura_ante_cadena_agotada_y_salida_invalida():
    for errores in ([CadenaAgotada(), CadenaAgotada()], [ValueError("x"), ValueError("y")]):
        r = correr(Falso(*errores), items(L20393))
        assert not r.usado and r.motivo == "revisor_fallido" and r.dictamenes == {}


def test_reintenta_una_vez():
    r = correr(Falso(CadenaAgotada(), resp(rev())), items(L20393))
    assert r.usado and r.llamadas == 1 and r.tokens_entrada == 100


def test_respuesta_con_forma_invalida_es_falla():
    r = correr(Falso({"otra": 1}, {"otra": 2}), items(L20393))
    assert not r.usado and r.motivo == "revisor_fallido"


def test_plazo_agotado_se_propaga_y_sin_items_o_hechos_no_llama():
    with pytest.raises(PlazoAgotado):
        correr(Falso(PlazoAgotado()), items(L20393))
    gen = Falso()
    assert correr(gen, []).motivo == "sin_sugerencias" and correr(gen, items(L20393), texto="   ").motivo == "sin_hechos"
    assert gen.usuarios == []


# ---- integración con el orquestador
class RetrieverFalso:
    umbral = 0.0

    def __init__(self, fragmentos):
        self.fragmentos = fragmentos

    async def recuperar(self, texto, consultas=None):
        return SimpleNamespace(fragmentos=[dict(f, puntaje=0.9) for f in self.fragmentos], mejor_puntaje=0.9,
                               recuperacion="nube", embedding="e", coleccion="c", version_corpus=3, tokens_embedding=5)


class EnrutadorFalso:
    """Distingue clasificador, generador y revisor por el esquema; el revisor responde `rev_resp`."""

    def __init__(self, fragmentos, rev_resp):
        self.fragmentos, self.rev_resp, self.revisiones, self.sistemas = fragmentos, list(rev_resp), 0, []
        self.usuarios_rev = []

    async def generar(self, sistema, usuario, esquema, validar, inicio, desde_modelo=None):
        props = esquema["properties"]
        if "materia" in props:
            return Resultado(validar({"materia": "penal", "riesgo": "alto"}), "oficial", "p", "m", 10, 5)
        if "conductas" in props:                      # extracción del perfil (evaluador por IDs)
            return Resultado(validar({"conductas": [{"conducta": "cohecho a funcionario público", "hecho_ids": ["H1"]}],
                                      "partes": ["gerente"], "relacion_laboral": "si", "datos_personales": False,
                                      "posibles_delitos": ["cohecho"]}), "oficial", "p", "m", 10, 5)
        if "evaluaciones" in props:                   # evaluador: todos probables
            ev = [{"candidato": f"A{i}", "puntaje": 2, "hecho_ids": ["H1"], "frase_ids": [f"A{i}.1"]}
                  for i in range(1, len(self.fragmentos) + 1)]
            return Resultado(validar({"evaluaciones": ev}), "oficial", "p", "m", 10, 5)
        if "revisiones" in props:
            self.revisiones += 1
            self.sistemas.append(sistema)
            self.usuarios_rev.append(usuario)
            r = self.rev_resp.pop(0)
            if isinstance(r, Exception):
                raise r
            return Resultado(validar(r), "oficial", "p", "m", 50, 10)
        arts = [{"fragmento_id": f["fragmento_id"], "explicacion": "Los hechos podrían relacionarse con esta norma.",
                 "cita": f["texto"][:40], "confianza": 0.9 - 0.1 * n} for n, f in enumerate(self.fragmentos)]
        return Resultado(validar({"articulos": arts}), "oficial", "p", "m", 200, 40)


def orquestar(rev_resp, revisor=True, fragmentos=(L20393, KARIN), **cfg_kw):
    fr = list(fragmentos)
    cfg = Config(revisor=revisor, **cfg_kw)
    almacen = AlmacenMemoria()
    enr = EnrutadorFalso(fr, rev_resp)
    orq = Orquestador(cfg, almacen, enr, RetrieverFalso(fr), lambda: 1_700_000_000.0)
    sol = {"cliente": "c", "ref_opaca": "r1", "id_solicitud": "s1", "estado": "pendiente", "creada_en": 1_700_000_000.0}
    asyncio.run(almacen.crear_solicitud(sol))
    asyncio.run(orq.procesar(sol, DENUNCIA))
    return enr, asyncio.run(almacen.obtener_solicitud("c", "r1")), asyncio.run(almacen.listar_articulos("s1"))


def test_flag_apagado_por_defecto_no_llama_ni_agrega_campos():
    assert Config().revisor is False
    assert Config.desde_entorno({"KERNA_REVISOR": "1"}).revisor is True
    assert Config.desde_entorno({}).revisor is False
    enr, sol, arts = orquestar([], revisor=False)
    assert enr.revisiones == 0 and sol["estado"] == "completada" and len(arts) == 2
    assert all("revision_juridica" not in a and "dictamen" not in a for a in arts) and "revision_juridica" not in sol
    assert all(_revision(a) == {} for a in arts)


def test_integracion_anota_y_no_elimina_los_vetados():
    enr, sol, arts = orquestar([resp(rev(cand="A1", dictamen="veta", causal="falta_sujeto_exigido", hechos=["H1"], frases=["A1.2"]),
                                     rev(cand="A2", dictamen="condiciona", condiciones=["ambito_regimen"], hechos=["H2"], frases=["A2.1"], conf=0.5),
                                     alertas=["fuera_de_corpus:penal"])])
    assert sol["estado"] == "completada" and len(arts) == 2          # anotar antes que eliminar
    por = {a["id_articulo"]: a for a in arts}
    v, c = por["l20393-3"], por["ck-211c"]
    assert v["dictamen"] == "veta" and v["causal_veto"] == "falta_sujeto_exigido" and v["revision_juridica"] == "revisado"
    assert c["dictamen"] == "condiciona" and c["condiciones"] == ["ambito_regimen"] and c["confianza_revisor"] == 0.5
    assert c["alertas_revision"] == ["fuera_de_corpus:penal"] and c["hecho_ids_revision"] == ["H2"]
    assert sol["revision_juridica"] == "revisado" and sol["alertas_revision"] == ["fuera_de_corpus:penal"]
    assert "Ley 20.393" in enr.sistemas[0] and "Ley 21.643" in enr.sistemas[0] and "Ley 19.628" not in enr.sistemas[0]
    assert sol["tokens_entrada"] == 10 + 200 + 50 + 5 and enr.revisiones == 1
    assert set(_revision(c)) >= {"dictamen", "condiciones", "revision_juridica"}


@pytest.mark.parametrize("falla", [[CadenaAgotada(), CadenaAgotada()], [PlazoAgotado()], [RuntimeError("x")], [{"mal": 1}, {"mal": 2}]])
def test_integracion_falla_segura_entrega_las_sugerencias_marcadas(falla):
    enr, sol, arts = orquestar(falla)
    assert sol["estado"] == "completada" and len(arts) == 2
    assert all(a["revision_juridica"] == "sin_revision" and "dictamen" not in a for a in arts)
    assert sol["revision_juridica"] == "sin_revision" and sol["alertas_revision"] == []


def test_integracion_articulo_sin_dictamen_queda_sin_revision():
    _, sol, arts = orquestar([resp(rev(cand="A1"))])
    por = {a["id_articulo"]: a for a in arts}
    assert por["l20393-3"]["revision_juridica"] == "revisado" and por["ck-211c"]["revision_juridica"] == "sin_revision"


def test_el_texto_de_la_denuncia_no_se_persiste():
    _, sol, arts = orquestar([resp(rev(cand="A1", dictamen="condiciona", condiciones=["sujeto"]), alertas=["posible_otra_via"])])
    volcado = json.dumps([sol, arts], ensure_ascii=False, default=str)
    for dato in ("Zafiro-Unico", "coima", "gerente de finanzas"):
        assert dato not in volcado


def test_con_multiquery_el_revisor_recibe_el_perfil_y_sin_el_no():
    enr, sol, arts = orquestar([resp(rev())], evaluador=True, evaluador_variante="3", multiquery=True)
    assert sol["revision_juridica"] == "revisado"
    assert "Análisis previo" in enr.usuarios_rev[0] and "cohecho a funcionario público" in enr.usuarios_rev[0]
    enr, _, _ = orquestar([resp(rev())])           # sin multiquery no hay perfil: el revisor recibe ""
    assert "Análisis previo" not in enr.usuarios_rev[0]
