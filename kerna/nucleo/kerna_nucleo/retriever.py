"""Recuperación: nube (Voyage + Qdrant) con respaldo en el servicio local."""
from __future__ import annotations

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


class Retriever:
    def __init__(self, voyage, qdrant, local, coleccion: str, embedding: str, top_k: int, umbral: float):
        self._voyage, self._qdrant, self._local = voyage, qdrant, local
        self.coleccion, self.embedding, self.top_k, self.umbral = coleccion, embedding, top_k, umbral

    async def recuperar(self, texto: str) -> Recuperacion:
        try:
            return await self._nube(texto)
        except ErrorProveedor as e:
            telemetria.evento("recuperacion_nube_fallida", proveedor=e.proveedor, codigo=str(e.codigo or "silencio"))
        try:
            return await self._respaldo(texto)
        except ErrorProveedor as e:
            telemetria.evento("recuperacion_local_fallida", proveedor=e.proveedor, codigo=str(e.codigo or "silencio"))
            raise RecuperacionFallida() from None

    async def _nube(self, texto: str) -> Recuperacion:
        vector, tokens = await self._voyage.embed_consulta(texto)
        puntos = await self._qdrant.buscar(self.coleccion, vector, self.top_k)
        version = await self._qdrant.version_corpus(self.coleccion)
        return self._armar(puntos, "nube", self.embedding, self.coleccion, version, tokens)

    async def _respaldo(self, texto: str) -> Recuperacion:
        d = await self._local.buscar(texto, self.top_k)
        return self._armar(d["fragmentos"], "local", str(d.get("modelo", "")), str(d.get("coleccion", "")),
                           int(d.get("version_corpus", 0) or 0), 0)

    def _armar(self, puntos, recuperacion, embedding, coleccion, version, tokens) -> Recuperacion:
        frags = [p for p in puntos if p.get("vigente") is not False and p.get("tipo") != "meta"
                 and p.get("fragmento_id")]
        frags = [dict(p, vigente=True) for p in frags][: self.top_k]
        mejor = max((float(p.get("puntaje", 0)) for p in frags), default=0.0)
        return Recuperacion(frags, recuperacion, embedding, coleccion, version, mejor, tokens)
