"""Servicio local (kerna/servicio_local) con embedder falso inyectado: ningún modelo se ejecuta."""
import hashlib

import numpy as np
import pytest
from fastapi.testclient import TestClient

from kerna_servicio_local.config import PREFIJO_CONSULTA, Config
from kerna_servicio_local.embedder import con_prefijo
from kerna_servicio_local.indice import Indice, normalizar
from kerna_servicio_local.servidor import crear_app

pytestmark = [pytest.mark.rf("RF23")]
TOKEN = "token-de-prueba"
H = {"X-Token-Interno": TOKEN}
DIM = 32


class EmbedderFalso:
    """Bolsa de palabras con hash: textos con palabras en común quedan cerca."""

    def __init__(self):
        self.llamadas = []

    def embed(self, textos, tipo):
        self.llamadas.append((list(textos), tipo))
        out = []
        for t in textos:
            v = np.zeros(DIM)
            for w in t.lower().split():
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
            out.append((v / (np.linalg.norm(v) or 1)).tolist())
        return out


class BlobFalso:
    def __init__(self, datos=None):
        self.datos = dict(datos or {})

    def guardar(self, nombre, datos):
        self.datos[nombre] = datos

    def leer(self, nombre):
        return self.datos.get(nombre)


def payload(i, texto, vigente=True):
    return {"fragmento_id": f"F{i}", "id_norma": "21643", "norma": "Ley N.° 21.643", "tipo_numero": "Ley 21643",
            "articulo": f"Artículo {i}", "jerarquia": "", "texto": texto, "materias": [], "categorias": [],
            "fecha_version": "2024-08-01", "vigente": vigente, "url_fuente": "https://www.bcn.cl/x",
            "transitorio": False, "parte": 1, "clave_corpus": f"k{i}", "tipo_contenido": "articulo",
            "vigencia_desde": "2024-08-01", "vigencia_anticipada": False}


TEXTOS = ["acoso laboral maltrato jefatura", "protección del denunciante represalias", "vacaciones feriado anual",
          "texto derogado acoso laboral maltrato jefatura"]


def indice_demo(origen="qdrant"):
    emb = EmbedderFalso()
    vs = normalizar(emb.embed(TEXTOS, "document"))
    pls = [payload(i, t, vigente=(i != 3)) for i, t in enumerate(TEXTOS)]
    return Indice(vs, pls, {"tipo": "meta", "version_corpus": 9, "modelo": "x"}, origen)


def cliente(qdrant, blob=None, emb=None):
    emb = emb or EmbedderFalso()
    app = crear_app(Config(token=TOKEN), emb, qdrant=qdrant, almacen=blob, en_segundo_plano=False)
    return TestClient(app), emb


def caido():
    raise ConnectionError("qdrant caído")


@pytest.mark.pr("PR-02")
def test_buscar_devuelve_campos_del_contrato_solo_vigentes_ordenados():
    with cliente(lambda: indice_demo())[0] as c:
        r = c.post("/buscar", headers=H, json={"texto": "acoso laboral maltrato", "k": 8})
        assert r.status_code == 200
        d = r.json()
        assert d["modelo"] == "multilingual-e5-large-instruct" and d["coleccion"] == "normativa_cl_local"
        assert d["version_corpus"] == 9
        ids = [f["fragmento_id"] for f in d["fragmentos"]]
        assert ids[0] == "F0" and "F3" not in ids and len(ids) == 3  # el derogado no sale
        punt = [f["puntaje"] for f in d["fragmentos"]]
        assert punt == sorted(punt, reverse=True)
        for campo in ("fragmento_id", "norma", "articulo", "texto", "vigente", "url_fuente", "clave_corpus", "puntaje"):
            assert campo in d["fragmentos"][0]
        assert c.post("/buscar", headers=H, json={"texto": "acoso", "k": 2}).json()["fragmentos"].__len__() == 2


@pytest.mark.pr("PR-02")
def test_la_consulta_se_vectoriza_como_query():
    c, emb = cliente(lambda: indice_demo())
    with c:
        c.post("/buscar", headers=H, json={"texto": "acoso", "k": 1})
        assert emb.llamadas[-1] == (["acoso"], "query")


def test_prefijo_de_instruccion_solo_en_consultas():
    assert con_prefijo(["hola"], "query") == [PREFIJO_CONSULTA + "hola"]
    assert PREFIJO_CONSULTA.startswith("Instruct: ") and PREFIJO_CONSULTA.endswith("\nQuery: ")
    assert con_prefijo(["hola"], "document") == ["hola"]


def test_embed_devuelve_vectores_y_modelo():
    with cliente(lambda: indice_demo())[0] as c:
        r = c.post("/embed", headers=H, json={"textos": ["a", "b"], "tipo": "document"})
        assert r.status_code == 200 and len(r.json()["vectores"]) == 2
        assert r.json()["modelo"] == "multilingual-e5-large-instruct"
        assert c.post("/embed", headers=H, json={"textos": ["x"] * 65}).status_code == 422
        assert c.post("/embed", headers=H, json={"textos": ["a"], "tipo": "otro"}).status_code == 422


@pytest.mark.rnf("RNF-seguridad")
@pytest.mark.parametrize("ruta,cuerpo", [("/embed", {"textos": ["a"]}), ("/buscar", {"texto": "a", "k": 1}),
                                         ("/recargar", None)])
def test_rutas_exigen_token_interno(ruta, cuerpo):
    with cliente(lambda: indice_demo())[0] as c:
        for cab in ({}, {"X-Token-Interno": "otro"}, {"X-Token-Interno": ""}):
            assert c.post(ruta, headers=cab, json=cuerpo).status_code == 401
        assert c.get("/salud").status_code == 200  # /salud no exige token


@pytest.mark.rnf("RNF-seguridad")
def test_sin_token_configurado_rechaza_todo():
    app = crear_app(Config(token=""), EmbedderFalso(), qdrant=lambda: indice_demo(), en_segundo_plano=False)
    with TestClient(app) as c:
        assert c.post("/embed", headers={"X-Token-Interno": ""}, json={"textos": ["a"]}).status_code == 401


@pytest.mark.pr("PR-12")
def test_con_qdrant_caido_carga_la_copia_del_blob():
    blob = BlobFalso()
    with cliente(lambda: indice_demo(), blob)[0]:
        pass  # con Qdrant sano deja la copia en el blob
    assert "normativa_cl_local.npz" in blob.datos
    c, _ = cliente(caido, blob)
    with c:
        s = c.get("/salud").json()
        assert s["origen_indice"] == "blob" and s["fragmentos"] == 4 and s["version_corpus"] == 9
        r = c.post("/buscar", headers=H, json={"texto": "protección denunciante", "k": 3})
        assert r.status_code == 200 and r.json()["fragmentos"][0]["fragmento_id"] == "F1"


@pytest.mark.pr("PR-12")
def test_sin_qdrant_ni_blob_no_hay_indice_pero_embed_funciona():
    with cliente(caido, BlobFalso())[0] as c:
        assert c.post("/buscar", headers=H, json={"texto": "a", "k": 1}).status_code == 503
        assert c.post("/embed", headers=H, json={"textos": ["a"]}).status_code == 200  # para poblar la colección


def test_salud_503_mientras_carga_el_modelo():
    class Lento(EmbedderFalso):
        def cargar(self):
            raise RuntimeError("sin red")

    with cliente(lambda: indice_demo(), emb=Lento())[0] as c:
        r = c.get("/salud")
        assert r.status_code == 503 and r.json()["estado"] == "cargando"
        assert c.post("/buscar", headers=H, json={"texto": "a", "k": 1}).status_code == 503


def test_recargar_toma_la_version_nueva():
    estado = {"i": indice_demo()}
    with cliente(lambda: estado["i"], BlobFalso())[0] as c:
        assert c.get("/salud").json()["version_corpus"] == 9
        nuevo = indice_demo()
        nuevo.meta = {"version_corpus": 10}
        estado["i"] = nuevo
        assert c.post("/recargar", headers=H).json()["version_corpus"] == 10


def test_copia_en_bytes_ida_y_vuelta():
    i = indice_demo()
    j = Indice.desde_bytes(i.a_bytes())
    assert j.payloads == i.payloads and j.meta == i.meta and np.allclose(j.vectores, i.vectores)
