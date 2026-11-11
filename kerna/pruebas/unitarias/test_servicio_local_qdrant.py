"""Lectura de la colección local desde Qdrant (simulada con httpx.MockTransport)."""
import httpx
import pytest

from kerna_servicio_local.indice import desde_qdrant

pytestmark = [pytest.mark.pr("PR-12"), pytest.mark.rf("RF23")]
META = "00000000-0000-0000-0000-000000000000"


def pagina(puntos, siguiente=None):
    return {"result": {"points": puntos, "next_page_offset": siguiente}}


def punto(i, vigente=True):
    return {"id": f"id{i}", "vector": [1.0, 0.0] if i % 2 else [0.0, 2.0],
            "payload": {"fragmento_id": f"F{i}", "vigente": vigente, "texto": "t"}}


def test_scroll_pagina_separa_meta_y_normaliza():
    paginas = [pagina([punto(1), {"id": META, "vector": [1.0, 0.0], "payload": {"tipo": "meta", "version_corpus": 5}}],
                      "sig"), pagina([punto(2)])]
    pedidos = []

    def manejador(req: httpx.Request):
        pedidos.append((req.headers.get("api-key"), req.read()))
        return httpx.Response(200, json=paginas.pop(0))

    ind = desde_qdrant("https://q.example", "clave", "normativa_cl_local",
                       httpx.Client(transport=httpx.MockTransport(manejador)))
    assert len(ind) == 2 and ind.version_corpus == 5 and ind.origen == "qdrant"
    assert abs(float(ind.vectores[1] @ ind.vectores[1]) - 1.0) < 1e-6  # normalizado
    assert all(c == "clave" for c, _ in pedidos) and b'"with_vector":true' in pedidos[0][1].replace(b" ", b"")


def test_coleccion_inexistente_o_vacia_lanza():
    cl = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404, json={})))
    with pytest.raises(httpx.HTTPStatusError):
        desde_qdrant("https://q.example", "k", "x", cl)
    cl = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=pagina([]))))
    with pytest.raises(RuntimeError):
        desde_qdrant("https://q.example", "k", "x", cl)
