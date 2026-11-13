"""Búsqueda híbrida (BM25 + RRF) y multi-query por conductas: índice léxico, fusión, retriever, perfil reutilizado."""
import asyncio
from types import SimpleNamespace

import pytest

from kerna_nucleo.almacen import AlmacenMemoria
from kerna_nucleo.bm25 import IndiceBM25, rrf, tokenizar
from kerna_nucleo.config import Config
from kerna_nucleo.enrutador import Resultado
from kerna_nucleo.evaluador_ids import EvaluadorIds, VARIANTES, conductas_consulta
from kerna_nucleo.orquestador import Orquestador
from kerna_nucleo.proveedores import ErrorProveedor
from kerna_nucleo.retriever import Retriever

DOCS = {
    "lic": "El empleador no podrá poner término al contrato durante la licencia médica del trabajador.",
    "cot": "Las cotizaciones previsionales deberán ser declaradas y pagadas por el empleador dentro del plazo.",
    "cam": "Los sistemas de cámaras de videovigilancia deberán respetar la privacidad de las personas.",
    "dat": "El tratamiento de datos personales requiere el consentimiento del titular.",
    "aco": "El acoso laboral es toda conducta que constituya agresión u hostigamiento reiterados.",
}


def pl(i, **kw):
    return {"fragmento_id": i, "id_norma": "n", "norma": "Ley X", "articulo": i, "texto": DOCS[i], "vigente": True, **kw}


# ---- tokenización, índice y RRF
def test_tokeniza_sin_tildes_vacias_y_con_stemming_liviano():
    assert tokenizar("La Cotización, de las Licencias médicas") == ["cotiz", "licenci", "medic"] or \
        tokenizar("La Cotización, de las Licencias médicas")[0] == "cotiz"
    assert "de" not in tokenizar("de la ley") and "la" not in tokenizar("de la ley")
    assert tokenizar("Artículo 211", stemming=False) == ["articulo", "211"]
    assert tokenizar("cotizaciones", True) == tokenizar("cotización", True)


def test_bm25_encuentra_terminos_concretos_y_ordena():
    idx = IndiceBM25(DOCS.items())
    assert idx.buscar("me despidieron durante la licencia médica")[0][0] == "lic"
    assert idx.buscar("no pagan las cotizaciones")[0][0] == "cot"
    assert idx.buscar("instalaron cámaras para vigilar")[0][0] == "cam"
    assert idx.buscar("palabras sin ninguna coincidencia xyz") == []
    assert len(idx.buscar("empleador", k=1)) == 1
    assert IndiceBM25([]).buscar("algo") == []


def test_rrf_fusiona_con_k60_pesos_y_empate_por_primera_lista():
    f = dict(rrf([["a", "b", "c"], ["b", "a"]]))
    assert f["a"] == pytest.approx(1 / 61 + 1 / 62) and f["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert [i for i, _ in rrf([["a", "b"], ["b", "a"]])] == ["a", "b"]           # empate: gana la primera lista
    assert [i for i, _ in rrf([["a", "b"], ["b", "a"]], pesos=[1, 2])] == ["b", "a"]
    assert [i for i, _ in rrf([["a", "b", "b"]])] == ["a", "b"]                   # sin contar repetidos


# ---- retriever
class Voyage:
    def __init__(self):
        self.una, self.varias = [], []

    async def embed_consulta(self, t):
        self.una.append(t)
        return [0.0], 4

    async def embed_consultas(self, ts):
        self.varias.append(list(ts))
        return [[float(i)] for i, _ in enumerate(ts)], 9


class Qdrant:
    """`buscar` devuelve la lista densa asociada al vector (por su primer valor)."""

    def __init__(self, densas, falla_indice=False):
        self.densas, self.falla_indice, self.scrolls, self.version = densas, falla_indice, 0, 1

    async def buscar(self, col, vector, k):
        return [pl(i, puntaje=0.9 - 0.1 * n) for n, i in enumerate(self.densas[int(vector[0])])][:k]

    async def version_corpus(self, col):
        return self.version

    async def fragmentos_vigentes(self, col):
        self.scrolls += 1
        if self.falla_indice:
            raise ErrorProveedor("qdrant", 503)
        return [pl(i) for i in DOCS]


def ret(q, v=None, **kw):
    return Retriever(v or Voyage(), q, None, "c", "m", kw.pop("top_k", 3), 0.0, **kw)


def ids(r):
    return [f["fragmento_id"] for f in r.fragmentos]


def test_flags_apagados_usan_solo_la_busqueda_densa_de_siempre():
    v, q = Voyage(), Qdrant([["dat", "aco", "cam"]])
    r = asyncio.run(ret(q, v).recuperar("me despidieron en licencia médica"))
    assert ids(r) == ["dat", "aco", "cam"] and v.una and not v.varias and q.scrolls == 0
    assert "puntaje_rrf" not in r.fragmentos[0]


def test_hibrida_agrega_candidatos_lexicos_conserva_coseno_y_umbral():
    q = Qdrant([["dat", "aco", "cam"]])
    r = asyncio.run(ret(q, hibrida=True, hibrida_profundidad=10, top_k=5).recuperar("despido durante licencia médica"))
    assert "lic" in ids(r) and ids(r)[0] in ("lic", "dat")                      # entra el candidato que la densa no trae
    por_id = {f["fragmento_id"]: f for f in r.fragmentos}
    assert por_id["lic"]["puntaje"] == 0.0 and por_id["dat"]["puntaje"] == pytest.approx(0.9)
    assert por_id["lic"]["puntaje_rrf"] > 0 and r.mejor_puntaje == pytest.approx(0.9)
    assert all(f["vigente"] is True and f["texto"] for f in r.fragmentos)


def test_el_indice_se_construye_una_vez_y_se_rehace_si_cambia_la_version():
    q = Qdrant([["dat"]])
    rt = ret(q, hibrida=True)
    asyncio.run(rt.recuperar("licencia médica"))
    asyncio.run(rt.recuperar("cotizaciones"))
    assert q.scrolls == 1
    q.version = 2
    asyncio.run(rt.recuperar("cotizaciones"))
    assert q.scrolls == 2


def test_si_el_indice_no_se_puede_construir_sigue_con_la_densa():
    q = Qdrant([["dat", "aco"]], falla_indice=True)
    r = asyncio.run(ret(q, hibrida=True).recuperar("licencia médica"))
    assert ids(r) == ["dat", "aco"]


def test_multiquery_fusiona_relato_y_conductas_en_una_sola_llamada_de_embeddings():
    v = Voyage()
    q = Qdrant([["dat", "aco"], ["cot", "lic"], ["cot", "cam"]])
    r = asyncio.run(ret(q, v, top_k=4).recuperar("relato", consultas=["pago de cotizaciones", "licencia médica"]))
    assert v.varias == [["relato", "pago de cotizaciones", "licencia médica"]] and not v.una
    assert ids(r)[0] == "cot" and set(ids(r)) == {"dat", "aco", "cot", "lic"}                # cot: 2 listas; el corte es top_k=4
    assert r.tokens_embedding == 9


def test_multiquery_peso_del_relato_y_solo_conductas():
    q = Qdrant([["dat", "aco"], ["cot"], ["lic"]])
    pesado = asyncio.run(ret(q, peso_relato=3.0).recuperar("r", consultas=["a", "b"]))
    assert ids(pesado)[0] == "dat"
    v = Voyage()
    sin = asyncio.run(ret(q, v, multiquery_relato=False).recuperar("r", consultas=["a", "b"]))
    assert v.varias == [["a", "b"]] and "lic" not in ids(sin)                   # el relato no entra (el vector 2 no se usa)
    solo_relato = asyncio.run(ret(q, multiquery_relato=False).recuperar("r"))  # sin conductas: el relato vuelve a valer
    assert ids(solo_relato) == ["dat", "aco"]


def test_multiquery_con_hibrida_usa_bm25_por_cada_frase():
    q = Qdrant([["dat"], ["dat"], ["dat"]])
    r = asyncio.run(ret(q, hibrida=True, top_k=5).recuperar("relato sin pistas", consultas=["cotizaciones previsionales", "cámaras"]))
    assert {"cot", "cam"} <= set(ids(r))


# ---- perfil, conductas y evaluador
def test_conductas_consulta_sanea_deduplica_y_limita():
    d = {"conductas": [{"conducta": "acoso laboral por superior jerárquico", "hecho_ids": ["H1"]},
                       {"conducta": "  Acoso laboral por superior   jerárquico ", "hecho_ids": []},
                       {"conducta": "x", "hecho_ids": []}, {"conducta": 5}, "texto",
                       {"conducta": "tratamiento de datos sin consentimiento", "hecho_ids": []}]}
    assert conductas_consulta(d) == ["acoso laboral por superior jerárquico", "tratamiento de datos sin consentimiento"]
    assert conductas_consulta(d, maximo=1) == ["acoso laboral por superior jerárquico"] and conductas_consulta(None) == []


def test_variante_3m_cambia_solo_la_extraccion_y_pide_frases_cortas():
    assert VARIANTES["3m"]["perfil"] and "extraccion" in VARIANTES["3m"] and "extraccion" not in VARIANTES["3"]
    assert "5 a 12 palabras" in VARIANTES["3m"]["extraccion"] and "sin nombrar leyes" in VARIANTES["3m"]["extraccion"]


DENUNCIA = "Mi jefe me grita todos los días. Me amenaza con despedirme si reclamo."
PERFIL = {"conductas": [{"conducta": "acoso laboral", "hecho_ids": ["H1"]},
                        {"conducta": "medidas de resguardo para la persona denunciante", "hecho_ids": ["H2"]}],
          "partes": ["jefatura"], "relacion_laboral": "si", "datos_personales": False, "posibles_delitos": []}
CANDS = [pl(i) for i in DOCS]


class Gen:
    def __init__(self):
        self.extracciones = self.evaluaciones = 0

    async def __call__(self, sistema, usuario, esquema, validar, inicio, desde_modelo=None):
        props = esquema["properties"]
        if "materia" in props:
            return Resultado(validar({"materia": "laboral", "riesgo": "medio"}), "oficial", "p", "m", 10, 5)
        if "conductas" in props:
            self.extracciones += 1
            return Resultado(validar(PERFIL), "oficial", "p", "m", 100, 20)
        if "evaluaciones" in props:
            self.evaluaciones += 1
            return Resultado(validar({"evaluaciones": [{"candidato": "A5", "puntaje": 3, "hecho_ids": ["H1"],
                                                        "frase_ids": ["A5.1"]}]}), "oficial", "p", "m", 300, 50)
        arts = [{"fragmento_id": "aco", "explicacion": "Los hechos podrían relacionarse con esta norma.",
                 "cita": DOCS["aco"][:40], "confianza": 0.9}]
        return Resultado(validar({"articulos": arts}), "oficial", "p", "m", 200, 40)


def test_evaluador_reutiliza_el_perfil_sin_pagar_dos_veces():
    gen = Gen()
    ev = EvaluadorIds(gen, variante="3m", salida=5)
    p = asyncio.run(ev.extraer_perfil(DENUNCIA, 0.0))
    assert p.ok and p.conductas == ["acoso laboral", "medidas de resguardo para la persona denunciante"]
    assert p.tokens_entrada == 100 and "Conductas jurídicamente relevantes" in p.texto
    r = asyncio.run(ev.evaluar(DENUNCIA, CANDS, 0.0, perfil=p))
    assert gen.extracciones == 1 and gen.evaluaciones == 1 and r.perfil is True and r.tokens_entrada == 300
    r2 = asyncio.run(ev.evaluar(DENUNCIA, CANDS, 0.0))                          # sin perfil previo: la extrae él
    assert gen.extracciones == 2 and r2.tokens_entrada == 400
    assert [f["fragmento_id"] for f in r.fragmentos][0] == "aco"


def test_extraccion_fallida_da_perfil_vacio_y_variantes_sin_perfil_no_extraen():
    class Mala(Gen):
        async def __call__(self, *a, **k):
            raise ErrorProveedor("p", 500)
    from kerna_nucleo.enrutador import CadenaAgotada

    class Agotada(Gen):
        async def __call__(self, *a, **k):
            raise CadenaAgotada()
    p = asyncio.run(EvaluadorIds(Agotada(), variante="3m").extraer_perfil(DENUNCIA, 0.0))
    assert not p.ok and p.conductas == [] and p.texto == ""
    g = Gen()
    assert asyncio.run(EvaluadorIds(g, variante="3b").extraer_perfil(DENUNCIA, 0.0)).ok is False and g.extracciones == 0


# ---- orquestador
class RetrieverFalso:
    umbral = 0.0

    def __init__(self):
        self.llamadas = []

    async def recuperar(self, texto, consultas=None):
        self.llamadas.append(consultas)
        return SimpleNamespace(fragmentos=[dict(f, puntaje=0.9) for f in CANDS], mejor_puntaje=0.9, recuperacion="nube",
                               embedding="e", coleccion="c", version_corpus=3, tokens_embedding=5)


def orquestar(**cfg):
    gen, rt, almacen = Gen(), RetrieverFalso(), AlmacenMemoria()
    enr = SimpleNamespace(generar=gen)
    config = Config(evaluador=True, evaluador_variante=cfg.pop("variante", "3m"), evaluador_candidatos=5, **cfg)
    orq = Orquestador(config, almacen, enr, rt, lambda: 1_700_000_000.0)
    sol = {"cliente": "c", "ref_opaca": "r", "id_solicitud": "s", "estado": "pendiente", "creada_en": 1_700_000_000.0}
    asyncio.run(almacen.crear_solicitud(sol))
    asyncio.run(orq.procesar(sol, DENUNCIA))
    return gen, rt, asyncio.run(almacen.obtener_solicitud("c", "r"))


def test_flags_de_busqueda_apagados_por_defecto_y_se_leen_del_entorno():
    c = Config()
    assert c.hibrida is False and c.multiquery is False and c.hibrida_stemming is True and c.multiquery_relato is True
    e = Config.desde_entorno({"KERNA_HIBRIDA": "1", "KERNA_MULTIQUERY": "true", "KERNA_MULTIQUERY_MAX": "3",
                              "KERNA_MULTIQUERY_RELATO": "0", "KERNA_MULTIQUERY_PESO_RELATO": "2",
                              "KERNA_HIBRIDA_STEMMING": "0"})
    assert (e.hibrida, e.multiquery, e.multiquery_max, e.multiquery_relato, e.multiquery_peso_relato,
            e.hibrida_stemming) == (True, True, 3, False, 2.0, False)


def test_orquestador_con_multiquery_extrae_una_vez_y_pasa_las_conductas():
    gen, rt, sol = orquestar(multiquery=True)
    assert gen.extracciones == 1 and gen.evaluaciones == 1
    assert rt.llamadas == [["acoso laboral", "medidas de resguardo para la persona denunciante"]]
    assert sol["estado"] == "completada" and sol["tokens_entrada"] >= 100 + 300


def test_orquestador_respeta_multiquery_max_y_no_extrae_antes_si_esta_apagado():
    gen, rt, _ = orquestar(multiquery=True, multiquery_max=1)
    assert rt.llamadas == [["acoso laboral"]]
    gen, rt, _ = orquestar()
    assert rt.llamadas == [None] or rt.llamadas == [[]] or len(rt.llamadas) == 1
    assert gen.extracciones == 1                                                # la hace el evaluador, como siempre


def test_multiquery_sin_evaluador_por_ids_no_hace_nada():
    gen, rt, _ = orquestar(multiquery=True, variante="3b")
    assert gen.extracciones == 0 and len(rt.llamadas) == 1 and not rt.llamadas[0]


def test_extras_de_fusion_protegen_los_primeros_candidatos_densos():
    q = Qdrant([["dat", "aco", "cam"]])
    prot = asyncio.run(ret(q, hibrida=True, hibrida_profundidad=10, top_k=3, extras_fusion=1)
                       .recuperar("licencia médica cotizaciones"))
    assert {"dat", "aco"} <= set(ids(prot)) and len(ids(prot)) == 3 and ({"lic", "cot"} & set(ids(prot)))
    assert Config().hibrida_extras == 0 and Config.desde_entorno({"KERNA_HIBRIDA_EXTRAS": "15"}).hibrida_extras == 15


# ---- experimento de enriquecimiento (KERNA_ENR_*): BM25 con enriquecimiento, factor de rol, literales deduplicados
class QdrantEnr(Qdrant):
    def __init__(self, densas, extra, **kw):
        super().__init__(densas, **kw)
        self.extra = extra

    async def buscar(self, col, vector, k):
        return [pl(i, puntaje=0.9 - 0.1 * n, **self.extra.get(i, {})) for n, i in enumerate(self.densas[int(vector[0])])][:k]

    async def fragmentos_vigentes(self, col):
        return [pl(i, **self.extra.get(i, {})) for i in DOCS]


def test_bm25_con_enriquecimiento_concatenado_encuentra_hechos_que_el_texto_no_dice():
    q = QdrantEnr([["dat"]], {"cam": {"enriquecimiento": "el jefe me grababa en el baño con una webcam"}})
    sin = asyncio.run(ret(q, hibrida=True, top_k=5).recuperar("webcam"))
    con = asyncio.run(ret(q, hibrida=True, top_k=5, enr_bm25="concat").recuperar("webcam"))
    aparte = asyncio.run(ret(q, hibrida=True, top_k=5, enr_bm25="aparte").recuperar("webcam"))
    assert "cam" not in ids(sin) and "cam" in ids(con) and "cam" in ids(aparte)


def test_factor_de_rol_baja_procedimiento_y_sancion():
    q = QdrantEnr([["lic", "cot", "dat"]], {"lic": {"rol": "procedimiento"}, "cot": {"rol": "sustantivo"}})
    assert ids(asyncio.run(ret(q, hibrida=True, top_k=3).recuperar("x")))[0] == "lic"
    assert ids(asyncio.run(ret(q, hibrida=True, top_k=3, rol_factor=0.5).recuperar("x")))[0] == "cot"


def test_literales_se_deduplican_por_articulo():
    q = QdrantEnr([["lic", "cot", "dat", "aco"]], {i: {"literal": "a", "articulo_id": "A1"} for i in ("lic", "cot")})
    r = asyncio.run(ret(q, hibrida=True, top_k=4).recuperar("x"))
    assert ids(r)[:3] == ["lic", "dat", "aco"] and "cot" not in ids(r)


def test_lista_densa_aparte_agrega_candidatos():
    class Q2(QdrantEnr):
        async def buscar(self, col, vector, k):
            return [pl("aco", puntaje=0.8)] if col == "aparte" else await super().buscar(col, vector, k)
    q = Q2([["dat", "cam", "lic"]], {})
    assert "aco" not in ids(asyncio.run(ret(q, top_k=3, hibrida=True).recuperar("zzz")))
    assert "aco" in ids(asyncio.run(ret(q, top_k=3, hibrida=True, coleccion_aparte="aparte", peso_aparte=3).recuperar("zzz")))
