"""Recuperación: nube (Voyage + Qdrant) con respaldo en el servicio local."""
from __future__ import annotations

import asyncio

from dataclasses import dataclass, field

from kerna_comun import telemetria

from .proveedores import ErrorProveedor


class RecuperacionFallida(Exception):
    """Fallaron la nube y el servicio local."""


@dataclass
class Recuperacion:
    fragmentos: list[dict]
    recuperacion: str  # "nube" | "local"
    embedding: str
    coleccion: str
    version_corpus: int
    mejor_puntaje: float
    tokens_embedding: int = 0
    tokens_rerank: int = 0
    reranker: str = ""


class Retriever:
    def __init__(self, voyage, qdrant, local, coleccion: str, embedding: str, top_k: int, umbral: float,
                 esperas_429=(3.0, 8.0, 15.0), dormir=None,
                 rerank_modelo: str = "", rerank_candidatos: int = 30):
        self._voyage, self._qdrant, self._local = voyage, qdrant, local
        self.coleccion, self.embedding, self.top_k, self.umbral = coleccion, embedding, top_k, umbral
        # Reranking por API (desactivado con rerank_modelo vacío): recupera `rerank_candidatos` y se queda con top_k.
        self.rerank_modelo, self.rerank_candidatos = rerank_modelo, max(rerank_candidatos, top_k)
        self._esperas_429, self._dormir = tuple(esperas_429), dormir or asyncio.sleep

    async def recuperar(self, texto: str) -> Recuperacion:
        try:
            return await self._nube_con_reintento(texto)
        except ErrorProveedor as e:
            telemetria.evento("recuperacion_nube_fallida", proveedor=e.proveedor, codigo=str(e.codigo or "silencio"))
        try:
            return await self._respaldo(texto)
        except ErrorProveedor as e:
            telemetria.evento("recuperacion_local_fallida", proveedor=e.proveedor, codigo=str(e.codigo or "silencio"))
            raise RecuperacionFallida() from None

    async def _nube_con_reintento(self, texto: str) -> Recuperacion:
        """El límite de peticiones del proveedor (429) se espera y se reintenta; lo demás pasa al respaldo local."""
        for espera in self._esperas_429:
            try:
                return await self._nube(texto)
            except ErrorProveedor as e:
                if e.codigo != 429:
                    raise
                telemetria.evento("recuperacion_nube_espera", proveedor=e.proveedor, codigo="429", espera_s=espera)
                await self._dormir(espera)
        return await self._nube(texto)

    async def _nube(self, texto: str) -> Recuperacion:
        vector, tokens = await self._voyage.embed_consulta(texto)
        k = self.rerank_candidatos if self.rerank_modelo else self.top_k
        puntos = await self._qdrant.buscar(self.coleccion, vector, k)
        version = await self._qdrant.version_corpus(self.coleccion)
        rec = self._armar(puntos, "nube", self.embedding, self.coleccion, version, tokens, limite=k)
        if self.rerank_modelo and len(rec.fragmentos) > 1:
            await self._reordenar(texto, rec)
        else:
            rec.fragmentos = rec.fragmentos[: self.top_k]
        return rec

    async def _reordenar(self, texto: str, rec: Recuperacion) -> None:
        """Reordena con el reranker; si falla, conserva el orden del embedding (top_k primeros)."""
        try:
            orden, tokens = await self._voyage.rerank(texto, [f.get("texto", "") for f in rec.fragmentos],
                                                      self.rerank_modelo, self.top_k)
        except ErrorProveedor as e:
            telemetria.evento("rerank_fallido", proveedor=e.proveedor, codigo=str(e.codigo or "silencio"))
            rec.fragmentos = rec.fragmentos[: self.top_k]
            return
        frags = [dict(rec.fragmentos[i], puntaje_embedding=rec.fragmentos[i].get("puntaje", 0), puntaje=s)
                 for i, s in orden if 0 <= i < len(rec.fragmentos)][: self.top_k]
        rec.fragmentos, rec.tokens_rerank, rec.reranker = frags, tokens, self.rerank_modelo

    async def _respaldo(self, texto: str) -> Recuperacion:
        d = await self._local.buscar(texto, self.top_k)
        return self._armar(d["fragmentos"], "local", str(d.get("modelo", "")), str(d.get("coleccion", "")),
                           int(d.get("version_corpus", 0) or 0), 0)

    def _armar(self, puntos, recuperacion, embedding, coleccion, version, tokens, limite=None) -> Recuperacion:
        frags = [p for p in puntos if p.get("vigente") is not False and p.get("tipo") != "meta"
                 and p.get("fragmento_id")]
        frags = [dict(p, vigente=True) for p in frags][: limite or self.top_k]
        mejor = max((float(p.get("puntaje", 0)) for p in frags), default=0.0)
        return Recuperacion(frags, recuperacion, embedding, coleccion, version, mejor, tokens)
