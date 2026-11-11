"""Embedder de multilingual-e5-large-instruct (sentence-transformers, CPU). El modelo se descarga al iniciar el
contenedor, nunca al construir la imagen. Las pruebas inyectan un embedder falso con la misma interfaz."""
from __future__ import annotations

from .config import DIMS, ETIQUETA_MODELO, PREFIJO_CONSULTA, PREFIJO_DOCUMENTO


def con_prefijo(textos: list[str], tipo: str) -> list[str]:
    prefijo = PREFIJO_CONSULTA if tipo == "query" else PREFIJO_DOCUMENTO
    return [prefijo + t for t in textos]


class EmbedderE5:
    dims = DIMS

    def __init__(self, etiqueta: str = ETIQUETA_MODELO):
        self._etiqueta = etiqueta
        self._modelo = None

    def cargar(self) -> None:
        from sentence_transformers import SentenceTransformer
        self._modelo = SentenceTransformer(self._etiqueta, device="cpu")
        self._modelo.max_seq_length = 512

    def embed(self, textos: list[str], tipo: str) -> list[list[float]]:
        """Vectores unitarios de 1024 dimensiones; consultas con prefijo de instrucción, documentos sin él."""
        vs = self._modelo.encode(con_prefijo(textos, tipo), normalize_embeddings=True, batch_size=4)
        return [[float(x) for x in v] for v in vs]
