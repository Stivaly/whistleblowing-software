"""Reranker abierto BAAI/bge-reranker-v2-m3 (cross-encoder) que corre dentro del contenedor, en CPU."""
from __future__ import annotations

import asyncio
import os
import threading

from . import ErrorProveedor

MODELO = "BAAI/bge-reranker-v2-m3"
NOMBRES = ("bge-reranker-v2-m3",)
MAX_TOKENS = 512


def es_bge(nombre: str) -> bool:
    return nombre in NOMBRES


class ClienteBGE:
    """Carga el modelo al primer uso (la imagen ya lo trae) y reordena sin red ni API externa."""
    proveedor = "bge-reranker"

    def __init__(self, ruta: str | None = None, cargar=None):
        self._ruta = ruta or os.environ.get("KERNA_BGE_RUTA") or MODELO
        self._cargar, self._modelo, self._cerrojo = cargar, None, threading.Lock()

    def _modelo_listo(self):
        with self._cerrojo:
            if self._modelo is None:
                if self._cargar:
                    self._modelo = self._cargar(self._ruta)
                else:
                    from sentence_transformers import CrossEncoder
                    self._modelo = CrossEncoder(self._ruta, max_length=MAX_TOKENS, device="cpu")
            return self._modelo

    def _puntuar(self, consulta: str, documentos: list[str]) -> list[float]:
        pares = [[consulta, d] for d in documentos]
        return [float(x) for x in self._modelo_listo().predict(pares, batch_size=8)]

    async def rerank(self, consulta: str, documentos: list[str], modelo: str, top_k: int) -> tuple[list[tuple[int, float]], int]:
        """[(índice, puntaje)] de mayor a menor; el cómputo corre en un hilo para no bloquear el servidor."""
        try:
            puntajes = await asyncio.to_thread(self._puntuar, consulta, documentos)
        except Exception as e:  # noqa: BLE001
            raise ErrorProveedor("bge-reranker", None, True, type(e).__name__) from None
        orden = sorted(enumerate(puntajes), key=lambda p: -p[1])[:top_k]
        return orden, 0
