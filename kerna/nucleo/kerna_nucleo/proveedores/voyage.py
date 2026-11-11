"""Cliente de embeddings de Voyage."""
from __future__ import annotations

import httpx

from . import ErrorProveedor, error_http

URL = "https://api.voyageai.com/v1/embeddings"


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
