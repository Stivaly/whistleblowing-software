"""Pruebas del sincronizador de embeddings, sin llamar a APIs externas.

  pip install -r requirements-dev.txt && python3 -m pytest -q
"""
import embed_sync as s


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


def test_gemini_es_el_proveedor_por_defecto():
    assert "gemini" in s.PROVEEDORES
