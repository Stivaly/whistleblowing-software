"""Pruebas del sincronizador de embeddings, sin llamar a APIs externas.

  pip install -r requirements-dev.txt && python3 -m pytest -q

La prueba de main() usa el MongoDB de prueba (fixture `db` de conftest.py) y un Qdrant falso.
"""
import io
import urllib.error

import pytest

import embed_sync as s


class Reloj:
    """Reemplaza time.monotonic y time.sleep: el tiempo solo avanza al dormir."""

    def __init__(self):
        self.t = 1000.0
        self.esperas = []

    def monotonic(self):
        return self.t

    def sleep(self, n):
        self.esperas.append(n)
        self.t += n


@pytest.fixture
def reloj(monkeypatch):
    r = Reloj()
    monkeypatch.setattr(s.time, "monotonic", r.monotonic)
    monkeypatch.setattr(s.time, "sleep", r.sleep)
    monkeypatch.setattr(s, "_voyage_proxima", 0.0)
    monkeypatch.delenv("VOYAGE_TPM", raising=False)
    monkeypatch.delenv("VOYAGE_RPM", raising=False)
    monkeypatch.setenv("VOYAGE_API_KEY", "clave-de-prueba")
    return r


def respuesta_voyage(body, tokens):
    # Voyage puede devolver los vectores desordenados: se ordenan por "index".
    data = [{"index": i, "embedding": [float(i)] * s.DIMS} for i in range(len(body["input"]))]
    return {"data": data[::-1], "usage": {"total_tokens": tokens}}


def test_voyage_es_el_proveedor_por_defecto():
    assert next(iter(s.PROVEEDORES)) == "voyage"
    assert s.MODELOS["voyage"] == "voyage-4-large"


def test_voyage_arma_la_peticion_de_documentos(monkeypatch, reloj):
    llamadas = []

    def falso_post(url, headers, body):
        llamadas.append((url, headers, body))
        return respuesta_voyage(body, 50)

    monkeypatch.setattr(s, "_post", falso_post)
    vectores = s.embed_voyage(["Ley 1 — uno. Art. 1", "Ley 2 — dos. Art. 2"])

    [(url, headers, body)] = llamadas
    assert url == "https://api.voyageai.com/v1/embeddings"
    assert headers == {"Authorization": "Bearer clave-de-prueba"}
    assert body == {"model": "voyage-4-large", "input": ["Ley 1 — uno. Art. 1", "Ley 2 — dos. Art. 2"],
                    "input_type": "document", "output_dimension": s.DIMS}
    assert [v[0] for v in vectores] == [0.0, 1.0]  # en el orden de los textos
    assert len(vectores[0]) == s.DIMS


def test_consulta_usa_input_type_query(monkeypatch, reloj):
    bodies = []
    monkeypatch.setattr(s, "_post", lambda url, h, body: bodies.append(body) or respuesta_voyage(body, 5))
    v = s.embed_consulta("acoso laboral de un jefe")
    assert bodies[0]["input_type"] == "query" and bodies[0]["input"] == ["acoso laboral de un jefe"]
    assert len(v) == s.DIMS


def test_lotes_respetan_el_limite_de_tokens():
    textos = ["a" * 3000] * 5  # ~1001 tokens estimados cada uno
    lotes = s._lotes_por_tokens(textos, 2500)
    assert [len(l) for l in lotes] == [2, 2, 1]
    # Un texto más grande que el límite va solo en su lote, no se pierde.
    assert s._lotes_por_tokens(["a" * 30000, "b"], 2500) == [["a" * 30000], ["b"]]


def test_espera_entre_peticiones_segun_tokens_y_peticiones(monkeypatch, reloj):
    # 3 lotes: el primero gasta 8.000 tokens (48 s con 10.000/min), el segundo 100
    # (manda el límite de 3 peticiones/min: 20 s).
    usos = iter([8000, 100, 100])
    monkeypatch.setattr(s, "_post", lambda url, h, body: respuesta_voyage(body, next(usos)))
    monkeypatch.setattr(s, "_lotes_por_tokens", lambda textos, n: [[t] for t in textos])

    s.embed_voyage(["uno", "dos", "tres"])
    assert reloj.esperas == [0.0, pytest.approx(48.0), pytest.approx(20.0)]


def test_limites_configurables(monkeypatch, reloj):
    monkeypatch.setenv("VOYAGE_TPM", "2000000")
    monkeypatch.setenv("VOYAGE_RPM", "2000")
    monkeypatch.setattr(s, "_post", lambda url, h, body: respuesta_voyage(body, 1000))
    s.embed_voyage(["uno"])
    s.embed_voyage(["dos"])
    assert reloj.esperas[1] == pytest.approx(0.03)


def test_429_espera_y_reintenta(monkeypatch, reloj):
    intentos = []

    def falso_post(url, headers, body):
        intentos.append(1)
        if len(intentos) == 1:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {"Retry-After": "30"}, io.BytesIO())
        return respuesta_voyage(body, 10)

    monkeypatch.setattr(s, "_post", falso_post)
    assert len(s.embed_voyage(["uno"])) == 1
    assert len(intentos) == 2 and reloj.esperas == [0.0, 30.0]


def test_otros_errores_no_se_reintentan(monkeypatch, reloj):
    def falso_post(url, headers, body):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, io.BytesIO())

    monkeypatch.setattr(s, "_post", falso_post)
    with pytest.raises(urllib.error.HTTPError):
        s.embed_voyage(["uno"])


def test_gemini_arma_la_peticion_y_lee_los_vectores(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    llamadas = []

    def falso_post(url, headers, body):
        llamadas.append((url, headers, body))
        return {"embeddings": [{"values": [0.1] * s.DIMS} for _ in body["requests"]]}

    monkeypatch.setattr(s, "_post", falso_post)
    vectores = s.embed_gemini(["Ley 1 — uno. Art. 1", "Ley 2 — dos. Art. 2"])

    url, headers, body = llamadas[0]
    assert url.endswith("/models/gemini-embedding-2:batchEmbedContents")
    assert headers == {"x-goog-api-key": "clave-de-prueba"}
    assert len(body["requests"]) == 2
    req = body["requests"][0]
    assert req["model"] == "models/gemini-embedding-2"
    assert req["outputDimensionality"] == s.DIMS
    assert req["content"]["parts"][0]["text"] == "title: none | text: Ley 1 — uno. Art. 1"
    assert len(vectores) == 2 and len(vectores[0]) == s.DIMS


def fragmento(i, estado="pendiente"):
    return {"_id": f"555-art-{i}", "id_norma": 555, "norma": "Ley de prueba", "tipo_numero": "Ley 99999",
            "articulo": str(i), "jerarquia": [f"Artículo {i}"], "texto": f"Artículo {i}.- texto",
            "texto_embedding": f"Ley 99999 — Ley de prueba. Artículo {i}", "materias": ["Prueba"],
            "categorias": ["test"], "fecha_version": "2024-02-02", "vigente": True,
            "url_fuente": "https://www.bcn.cl/leychile/navegar?idNorma=555", "estado_embedding": estado}


def uri_de(db):
    host, puerto = db.client.address
    return f"mongodb://{host}:{puerto}/{db.name}"


def test_main_sincroniza_pendientes_con_voyage(db, monkeypatch, reloj):
    db.fragmentos.insert_many([fragmento(1), fragmento(2), fragmento(3), fragmento(4, "no_aplica")])
    monkeypatch.setenv("MONGODB_URI", uri_de(db))
    peticiones, upserts = [], []
    monkeypatch.setattr(s, "_post", lambda url, h, body: peticiones.append(body) or respuesta_voyage(body, 10))
    monkeypatch.setattr(s, "asegurar_coleccion", lambda: None)
    monkeypatch.setattr(s, "qdrant", lambda path, body=None, method="PUT": upserts.append(body))
    monkeypatch.setattr("sys.argv", ["embed_sync.py", "--batch", "2"])

    s.main()

    assert [len(p["input"]) for p in peticiones] == [2, 1]
    puntos = [p for u in upserts for p in u["points"]]
    assert sorted(p["payload"]["fragmento_id"] for p in puntos) == ["555-art-1", "555-art-2", "555-art-3"]
    assert puntos[0]["id"] == s.punto_id(puntos[0]["payload"]["fragmento_id"])
    assert db.fragmentos.count_documents({"estado_embedding": "ok", "embedding_modelo": "voyage-4-large"}) == 3
    assert db.fragmentos.find_one({"_id": "555-art-4"})["estado_embedding"] == "no_aplica"


def test_main_no_marca_ok_si_faltan_dimensiones(db, monkeypatch, reloj):
    db.fragmentos.insert_one(fragmento(1))
    monkeypatch.setenv("MONGODB_URI", uri_de(db))
    monkeypatch.setattr(s, "_post", lambda url, h, body: {
        "data": [{"index": 0, "embedding": [0.1] * 512}], "usage": {"total_tokens": 1}})
    monkeypatch.setattr(s, "asegurar_coleccion", lambda: None)
    monkeypatch.setattr(s, "qdrant", lambda *a, **k: pytest.fail("no debe subir vectores inválidos"))
    monkeypatch.setattr("sys.argv", ["embed_sync.py"])

    with pytest.raises(RuntimeError):
        s.main()
    assert db.fragmentos.find_one({"_id": "555-art-1"})["estado_embedding"] == "pendiente"
