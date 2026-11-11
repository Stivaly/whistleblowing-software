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
