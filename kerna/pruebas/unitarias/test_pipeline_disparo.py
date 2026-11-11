"""Regla de disparo, estado por colección, punto meta y paridad del pipeline BCN (sin red).

Usa el MongoDB local de prueba (127.0.0.1:27018, base *_test); si no responde, se omiten.
Ningún proveedor ni Qdrant reales: embedders y qdrant() son falsos.
"""
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import pytest

import embed_sync as s
import extraer_bcn as x

PIPELINE = Path(__file__).resolve().parents[2] / "pipeline_bcn"

COLS = [
    {"nombre": "normativa_cl", "proveedor": "voyage", "modelo": "voyage-4-large", "dims": 4},
    {"nombre": "normativa_cl_local", "proveedor": "local", "modelo": "bge-m3", "dims": 4},
]


@pytest.fixture
def db():
    from pymongo import MongoClient

    uri = os.environ.get("MONGODB_TEST_URI", "mongodb://127.0.0.1:27018/kerna_test")
    assert urlparse(uri).hostname in ("127.0.0.1", "localhost")
    c = MongoClient(uri, serverSelectionTimeoutMS=2000)
    try:
        c.admin.command("ping")
    except Exception:
        pytest.skip("MongoDB de prueba no disponible")
    base = c.get_default_database()
    assert base.name.endswith("_test")
    c.drop_database(base.name)
    yield base
    c.drop_database(base.name)
    c.close()


def frag(i, estado="pendiente", vigente=True):
    return {"_id": f"555-art-{i}", "id_norma": 555, "norma": "Ley", "tipo_numero": "Ley 1",
            "articulo": str(i), "jerarquia": [f"Artículo {i}"], "texto": f"texto {i}",
            "texto_embedding": f"Ley 1. Artículo {i}", "materias": [], "categorias": [],
            "fecha_version": "2024", "vigente": vigente, "url_fuente": "u",
            "hash_texto": f"h{i}", "firma": f"f{i}", "estado_embedding": estado}


class Proveedores:
    """Embedders y Qdrant falsos que cuentan las llamadas."""

    def __init__(self, monkeypatch):
        self.llamadas = []   # (proveedor, cantidad de textos)
        self.upserts = []    # (coleccion, puntos)
        monkeypatch.setattr(s, "crear_embedder", self.crear)
        monkeypatch.setattr(s, "asegurar_coleccion", lambda *a, **k: None)
        monkeypatch.setattr(s, "qdrant", self.qdrant)

    def crear(self, proveedor, modelo, dims):
        def embed(textos, tipo="document"):
            self.llamadas.append((proveedor, len(textos)))
            return [[0.5] * dims for _ in textos]
        return embed

    def qdrant(self, path, body=None, method="PUT"):
        if "/points" in path and body and "points" in body:
            self.upserts.append((path.split("/")[2], body["points"]))


def resultado(tmp_path, **kw):
    r = {"ok": True, "cambios": 0}
    r.update(kw)
    ruta = tmp_path / "res.json"
    ruta.write_text(json.dumps(r))
    return ruta


@pytest.fixture
def prov(monkeypatch):
    return Proveedores(monkeypatch)


# ------------------------------------------------------------------ regla de disparo
@pytest.mark.pr("PR-21")
def test_con_cambios_vectoriza_todas_las_colecciones_activas(db, prov, tmp_path):
    db.fragmentos.insert_many([frag(1), frag(2), frag(3, "no_aplica")])
    assert s.disparar(db, COLS, resultado(tmp_path, cambios=2)) == 0
    assert sorted(prov.llamadas) == [("local", 2), ("voyage", 2)]
    assert {c for c, _ in prov.upserts if True} >= {"normativa_cl", "normativa_cl_local"}


@pytest.mark.pr("PR-21")
def test_sin_cambios_no_llama_a_ningun_proveedor(db, prov, tmp_path, capsys):
    db.fragmentos.insert_many([frag(1), frag(2)])
    s.sincronizar_todas(db, COLS)
    prov.llamadas.clear(); prov.upserts.clear()
    assert s.disparar(db, COLS, resultado(tmp_path, cambios=0)) == 0
    assert prov.llamadas == [] and prov.upserts == []
    assert "sin cambios" in capsys.readouterr().out


@pytest.mark.pr("PR-21")
@pytest.mark.parametrize("contenido", [{"ok": False, "cambios": 5}, None])
def test_extraccion_fallida_no_vectoriza(db, prov, tmp_path, contenido):
    db.fragmentos.insert_one(frag(1))
    ruta = resultado(tmp_path, **contenido) if contenido else tmp_path / "no_existe.json"
    assert s.disparar(db, COLS, ruta) == 1
    assert prov.llamadas == []


@pytest.mark.pr("PR-21")
def test_pendientes_de_corrida_fallida_se_reintentan_sin_cambios(db, prov, tmp_path):
    db.fragmentos.insert_many([frag(1), frag(2)])
    # La colección local ya está al día; la de Voyage quedó con uno pendiente.
    s.sincronizar_todas(db, COLS)
    db.fragmentos.update_one({"_id": "555-art-2"}, {"$unset": {"embeddings.normativa_cl": ""},
                                                     "$set": {"estado_embedding": "pendiente"}})
    prov.llamadas.clear()
    assert s.disparar(db, COLS, resultado(tmp_path, cambios=0)) == 0
    assert prov.llamadas == [("voyage", 1)]


@pytest.mark.pr("PR-21")
@pytest.mark.parametrize("modo, args", [("diario", []), ("semanal", ["--forzar"]),
                                        ("vigencia-21719", ["--normas", "141599"])])
@pytest.mark.parametrize("rc_extraccion", [0, 1])
def test_run_sh_en_los_tres_modos(tmp_path, modo, args, rc_extraccion):
    bin_ = tmp_path / "bin"; bin_.mkdir()
    reg = tmp_path / "llamadas.txt"
    (bin_ / "python").write_text(f'#!/bin/sh\necho "$*" >> {reg}\n'
                                 f'if [ "$1" = extraer_bcn.py ]; then exit {rc_extraccion}; fi\n')
    (bin_ / "python").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}",
           "KERNA_RESULTADO": str(tmp_path / "r" / "res.json")}
    r = subprocess.run(["sh", "run.sh", modo], cwd=PIPELINE, env=env, capture_output=True)
    llamadas = reg.read_text().splitlines()
    res = f"--resultado {tmp_path}/r/res.json"
    assert llamadas[0] == " ".join(["extraer_bcn.py", *args, res])
    if rc_extraccion:
        assert r.returncode == 1 and len(llamadas) == 1          # no se vectoriza
    else:
        assert r.returncode == 0
        assert llamadas[1] == f"embed_sync.py --todas --si-cambios {tmp_path}/r/res.json"


# ------------------------------------------------------------------ estado, meta, voyage
@pytest.mark.pr("PR-07")
def test_estado_por_coleccion(db, prov):
    db.fragmentos.insert_many([frag(1), frag(2)])
    s.sincronizar_coleccion(db, COLS[0])
    e = db.fragmentos.find_one({"_id": "555-art-1"})
    assert e["embeddings"]["normativa_cl"]["modelo"] == "voyage-4-large"
    assert e["estado_embedding"] == "ok" and "normativa_cl_local" not in e["embeddings"]
    assert s.contar_pendientes(db, COLS[0]) == 0 and s.contar_pendientes(db, COLS[1]) == 2
    # Cambia el hash de un fragmento: solo ese queda pendiente, en ambas colecciones ya sincronizadas.
    s.sincronizar_coleccion(db, COLS[1])
    db.fragmentos.update_one({"_id": "555-art-2"}, {"$set": {"hash_texto": "nuevo"}})
    assert (s.contar_pendientes(db, COLS[0]), s.contar_pendientes(db, COLS[1])) == (1, 1)
    # Cambia el modelo configurado: todo queda pendiente en esa colección.
    otra = {**COLS[1], "modelo": "otro"}
    assert s.contar_pendientes(db, otra) == 2


@pytest.mark.pr("PR-07")
def test_legado_ok_no_se_revectoriza(db):
    db.fragmentos.insert_one({**frag(1, "ok"), "embedding_modelo": "voyage-4-large"})
    assert s.contar_pendientes(db, COLS[0]) == 0
    db.fragmentos.update_one({}, {"$set": {"estado_embedding": "pendiente"}})
    assert s.contar_pendientes(db, COLS[0]) == 1


@pytest.mark.pr("PR-07")
def test_punto_meta_al_final_con_cambios(db, prov):
    db.meta.insert_one({"_id": "corpus", "version_corpus": 7})
    db.fragmentos.insert_one(frag(1))
    s.sincronizar_coleccion(db, COLS[0])
    meta = [p for _, ps in prov.upserts for p in ps if p["id"] == s.PUNTO_META_ID]
    assert len(meta) == 1
    pl = meta[0]["payload"]
    assert (pl["tipo"], pl["vigente"], pl["version_corpus"], pl["modelo"]) == ("meta", False, 7, "voyage-4-large")
    assert pl["actualizado_en"] and len(meta[0]["vector"]) == 4
    n = len(prov.upserts)
    s.sincronizar_coleccion(db, COLS[0])        # nada pendiente: no reescribe el meta
    assert len(prov.upserts) == n


@pytest.mark.pr("PR-07")
def test_voyage_law_2_sin_output_dimension():
    assert "output_dimension" not in s._cuerpo_voyage(["a"], "document", "voyage-law-2", 1024)
    assert s._cuerpo_voyage(["a"], "query", "voyage-4-lite", 1024)["output_dimension"] == 1024
    assert s._cuerpo_voyage(["a"], "document", "voyage-4-large", 1024)["model"] == "voyage-4-large"


@pytest.mark.pr("PR-07")
def test_azure_openai_y_local_arman_la_peticion(monkeypatch):
    visto = []
    monkeypatch.setattr(s, "_post", lambda url, h, b: visto.append((url, h, b)) or (
        {"data": [{"index": i, "embedding": [0.0]} for i in range(len(b["input"]))], "usage": {"total_tokens": 3}}
        if "input" in b else {"vectores": [[0.0]] * len(b["textos"])}))
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_KEY", "k")
    monkeypatch.setenv("KERNA_LOCAL_URL", "http://local:8080")
    monkeypatch.setenv("KERNA_LOCAL_TOKEN", "t")
    s.reiniciar_medicion()
    s.embed_azure_openai(["a", "b"], "document", "text-embedding-3-large", 1024)
    s.embed_local(["a"], "query")
    (u1, h1, b1), (u2, h2, b2) = visto
    assert u1.startswith("https://x.openai.azure.com/openai/deployments/text-embedding-3-large/embeddings")
    assert h1 == {"api-key": "k"} and b1["dimensions"] == 1024
    assert u2 == "http://local:8080/embed" and h2 == {"X-Token-Interno": "t"}
    assert b2 == {"textos": ["a"], "tipo": "query"}
    assert s.MEDICION["tokens"] == 3 and len(s.MEDICION["latencias_ms"]) == 2


def test_colecciones_json_activas():
    cols = s.cargar_colecciones()
    assert cols[0] == {"nombre": "normativa_cl", "proveedor": "voyage", "modelo": "voyage-4-large",
                       "dims": 1024, "activa": True}


# ------------------------------------------------------------------ paridad
@pytest.mark.pr("PR-07")
def test_verificar_paridad_simulada(db):
    db.fragmentos.insert_many([frag(1), frag(2), frag(3), frag(4, vigente=False), frag(5, "no_aplica")])
    punto = lambda i, texto=None, vigente=True: {"fragmento_id": f"555-art-{i}",
                                                 "texto": texto or f"texto {i}", "vigente": vigente}
    puntos = {"555-art-1": punto(1),                      # igual
              "555-art-2": punto(2, "texto viejo"),       # texto desactualizado
              "555-art-4": punto(4, vigente=True),        # ya no vigente en Mongo: sobrante
              "555-art-9": punto(9)}                      # no existe en Mongo: sobrante
    r = s.verificar_paridad("c", db, puntos)
    assert r["faltantes"] == ["555-art-3"]
    assert r["desactualizados"] == ["555-art-2"]
    assert r["sobrantes"] == ["555-art-4", "555-art-9"]
    assert not r["ok"]
    ok = s.verificar_paridad("c", db, {"555-art-1": punto(1), "555-art-2": punto(2), "555-art-3": punto(3),
                                       "555-art-4": punto(4, vigente=False)})
    assert ok["ok"]


# ------------------------------------------------------------------ extractor
@pytest.mark.pr("PR-21")
def test_extractor_version_corpus_resultado_y_retiro(db, tmp_path):
    norma = {"_id": "n1", "clave": "n1", "hash_fuente": "a", "vigente": True,
             "vigencia_anticipada": False, "fecha_version": "2024"}

    def f(i, texto="t"):
        d = frag(i, "pendiente"); d.pop("firma"); d["clave_corpus"] = "n1"
        d.update(texto_embedding=texto, vigencia_anticipada=False, tipo_contenido="sustantiva")
        return d

    r1 = x.upsert_mongo(db, norma, [f(1), f(2)])
    assert r1["nuevos"] == 2
    assert x.subir_version_corpus(db) == 1 and s.version_corpus(db) == 1
    # Un artículo desaparece: queda no vigente y pendiente aunque su hash_texto no cambie.
    db.fragmentos.update_many({}, {"$set": {"embeddings.normativa_cl": {
        "modelo": "voyage-4-large", "hash_texto": "h1", "firma": ""}}})
    for d in db.fragmentos.find():
        db.fragmentos.update_one({"_id": d["_id"]}, {"$set": {"embeddings.normativa_cl.hash_texto": d["hash_texto"],
                                                              "embeddings.normativa_cl.firma": d["firma"],
                                                              "estado_embedding": "ok"}})
    assert s.contar_pendientes(db, COLS[0]) == 0
    norma2 = {**norma, "hash_fuente": "b"}
    r2 = x.upsert_mongo(db, norma2, [f(1, "otro")])
    assert (r2["cambiados"], r2["retirados"]) == (1, 1)
    assert db.fragmentos.find_one({"_id": "555-art-2"})["vigente"] is False
    assert s.contar_pendientes(db, COLS[0]) == 2          # ambos vuelven a subirse (payload vigente=false)
    assert db.fragmentos.find_one({"_id": "555-art-1"})["embeddings"]["normativa_cl"]   # mapa conservado
    ruta = tmp_path / "r" / "res.json"
    x.escribir_resultado(str(ruta), True, 1, 0, {"nuevos": 0, "cambiados": 1, "retirados": 1}, 2)
    assert json.loads(ruta.read_text())["cambios"] == 2
