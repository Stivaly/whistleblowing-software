"""Límites de proveedores: reintento ante 429 en la recuperación y turnos de la cadena."""
import asyncio

import pytest

from kerna_nucleo.proveedores import ErrorProveedor
from kerna_nucleo.retriever import Retriever


class _Voyage:
    def __init__(self, fallos):
        self.fallos, self.llamadas = list(fallos), 0

    async def embed_consulta(self, texto):
        self.llamadas += 1
        if self.fallos:
            raise ErrorProveedor("voyage", self.fallos.pop(0))
        return [0.1], 3


class _Qdrant:
    async def buscar(self, coleccion, vector, k):
        return []

    async def version_corpus(self, coleccion):
        return 1


def _retriever(voyage, esperas):
    async def dormir(s):
        esperas.append(s)
    return Retriever(voyage, _Qdrant(), None, "c", "m", 5, 0.0, dormir=dormir)


def test_429_se_espera_y_se_reintenta():
    v, esperas = _Voyage([429, 429]), []
    r = asyncio.run(_retriever(v, esperas).recuperar("x"))
    assert r.origen == "nube" if hasattr(r, "origen") else True
    assert v.llamadas == 3 and esperas == [3.0, 8.0]


def test_otro_error_no_se_reintenta_en_nube():
    v, esperas = _Voyage([503]), []
    with pytest.raises(Exception):
        asyncio.run(_retriever(v, esperas).recuperar("x"))
    assert v.llamadas == 1 and esperas == []


# ---- reranking por API (desactivado por defecto)
class _VoyageRerank(_Voyage):
    def __init__(self, orden=None, falla=None):
        super().__init__([])
        self.orden, self.falla, self.rerank_llamadas = orden, falla, []

    async def rerank(self, consulta, documentos, modelo, top_k):
        self.rerank_llamadas.append((consulta, list(documentos), modelo, top_k))
        if self.falla:
            raise ErrorProveedor("voyage", self.falla)
        return self.orden, 42


class _QdrantN:
    def __init__(self, n=6):
        self.pedidos = []
        self.n = n

    async def buscar(self, coleccion, vector, k):
        self.pedidos.append(k)
        return [{"fragmento_id": f"f{i}", "texto": f"t{i}", "puntaje": 0.9 - i / 100} for i in range(self.n)][:k]

    async def version_corpus(self, coleccion):
        return 1


def _rr(voyage, qd, modelo="rerank-2.5"):
    return Retriever(voyage, qd, None, "c", "m", 3, 0.0, rerank_modelo=modelo, rerank_candidatos=5)


def test_sin_rerank_no_lo_llama_y_pide_top_k():
    v, qd = _VoyageRerank(), _QdrantN()
    r = asyncio.run(_rr(v, qd, "").recuperar("x"))
    assert qd.pedidos == [3] and not v.rerank_llamadas and len(r.fragmentos) == 3 and r.reranker == ""


def test_rerank_reordena_candidatos_y_corta_a_top_k():
    v, qd = _VoyageRerank(orden=[(4, 0.8), (0, 0.5), (2, 0.1)]), _QdrantN()
    r = asyncio.run(_rr(v, qd).recuperar("x"))
    assert qd.pedidos == [5]
    assert v.rerank_llamadas == [("x", ["t0", "t1", "t2", "t3", "t4"], "rerank-2.5", 3)]
    assert [f["fragmento_id"] for f in r.fragmentos] == ["f4", "f0", "f2"]
    assert r.tokens_rerank == 42 and r.reranker == "rerank-2.5" and r.fragmentos[0]["puntaje"] == 0.8
    assert r.mejor_puntaje == 0.9          # el umbral sigue midiendo similitud del embedding


def test_rerank_fallido_conserva_orden_del_embedding():
    v, qd = _VoyageRerank(falla=503), _QdrantN()
    r = asyncio.run(_rr(v, qd).recuperar("x"))
    assert [f["fragmento_id"] for f in r.fragmentos] == ["f0", "f1", "f2"] and r.reranker == ""


# ---- reranker abierto bge-reranker-v2-m3 (dentro del contenedor)
class _ModeloFalso:
    def __init__(self, puntajes):
        self.puntajes, self.pares = puntajes, None

    def predict(self, pares, batch_size=8):
        self.pares = pares
        return self.puntajes


def test_cliente_bge_ordena_por_puntaje_y_corta():
    from kerna_nucleo.proveedores.bge_reranker import ClienteBGE
    m = _ModeloFalso([0.1, 0.9, 0.5, 0.7])
    c = ClienteBGE(cargar=lambda ruta: m)
    orden, tokens = asyncio.run(c.rerank("q", ["a", "b", "c", "d"], "bge-reranker-v2-m3", 3))
    assert orden == [(1, 0.9), (3, 0.7), (2, 0.5)] and tokens == 0 and m.pares[0] == ["q", "a"]


def test_cliente_bge_error_se_convierte_en_error_de_proveedor():
    from kerna_nucleo.proveedores.bge_reranker import ClienteBGE

    def falla(ruta):
        raise OSError("sin modelo")
    with pytest.raises(ErrorProveedor):
        asyncio.run(ClienteBGE(cargar=falla).rerank("q", ["a"], "bge-reranker-v2-m3", 1))


def test_retriever_usa_reranker_local_para_bge_y_voyage_para_los_demas():
    v, qd = _VoyageRerank(orden=[(0, 0.1)]), _QdrantN()
    local = _VoyageRerank(orden=[(4, 0.8), (0, 0.5), (2, 0.1)])
    r = asyncio.run(Retriever(v, qd, None, "c", "m", 3, 0.0, rerank_modelo="bge-reranker-v2-m3", rerank_candidatos=5,
                              reranker_local=local).recuperar("x"))
    assert [f["fragmento_id"] for f in r.fragmentos] == ["f4", "f0", "f2"] and not v.rerank_llamadas
    assert r.reranker == "bge-reranker-v2-m3"
    r2 = asyncio.run(Retriever(v, qd, None, "c", "m", 3, 0.0, rerank_modelo="rerank-2.5", rerank_candidatos=5,
                               reranker_local=local).recuperar("x"))
    assert v.rerank_llamadas and r2.reranker == "rerank-2.5"
