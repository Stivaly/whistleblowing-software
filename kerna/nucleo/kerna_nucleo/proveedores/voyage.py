"""Cliente de embeddings de Voyage."""
from __future__ import annotations

import httpx

from . import ErrorProveedor, error_http

URL = "https://api.voyageai.com/v1/embeddings"
URL_RERANK = "https://api.voyageai.com/v1/rerank"


class ClienteVoyage:
    proveedor = "voyage"

    def __init__(self, api_key: str, modelo: str = "voyage-4-large", dims: int = 1024,
                 http: httpx.AsyncClient | None = None, url: str = URL, timeout: float = 20.0):
        self._key, self.modelo, self.dims, self._url = api_key, modelo, dims, url
        self._http = http or httpx.AsyncClient(timeout=timeout)

    async def embed_consulta(self, texto: str) -> tuple[list[float], int]:
        """Vector de la consulta (input_type "query") y tokens usados."""
        try:
            r = await self._http.post(self._url, headers={"Authorization": f"Bearer {self._key}"},
                                      json={"model": self.modelo, "input": [texto], "input_type": "query",
                                            "output_dimension": self.dims})
        except httpx.HTTPError as e:
            raise ErrorProveedor("voyage", None, True, type(e).__name__) from None
        if r.status_code != 200:
            raise error_http("voyage", r.status_code)
        try:
            d = r.json()
            return d["data"][0]["embedding"], int((d.get("usage") or {}).get("total_tokens", 0))
        except (ValueError, KeyError, IndexError, TypeError):
            raise ErrorProveedor("voyage", 200, True, "respuesta inválida") from None

    async def rerank(self, consulta: str, documentos: list[str], modelo: str, top_k: int,
                     url: str = URL_RERANK) -> tuple[list[tuple[int, float]], int]:
        """Reordena `documentos` por relevancia a la consulta: [(índice, puntaje)] de mayor a menor y tokens usados."""
        try:
            r = await self._http.post(url, headers={"Authorization": f"Bearer {self._key}"},
                                      json={"model": modelo, "query": consulta, "documents": documentos,
                                            "top_k": top_k, "truncation": True})
        except httpx.HTTPError as e:
            raise ErrorProveedor("voyage", None, True, type(e).__name__) from None
        if r.status_code != 200:
            raise error_http("voyage", r.status_code)
        try:
            d = r.json()
            orden = [(int(x["index"]), float(x["relevance_score"])) for x in d["data"]]
            return orden, int((d.get("usage") or {}).get("total_tokens", 0))
        except (ValueError, KeyError, TypeError):
            raise ErrorProveedor("voyage", 200, True, "respuesta inválida") from None
