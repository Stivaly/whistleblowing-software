"""Cliente del servicio local de embeddings e índice (kerna/servicio_local)."""
from __future__ import annotations

import httpx

from . import ErrorProveedor, error_http


class ClienteLocal:
    proveedor = "local"

    def __init__(self, url: str, token: str, http: httpx.AsyncClient | None = None, timeout: float = 60.0):
        self._url = url.rstrip("/")
        self._token = token
        self._http = http or httpx.AsyncClient(timeout=timeout)  # tolera el arranque desde escala a cero

    async def buscar(self, texto: str, k: int) -> dict:
        """{"fragmentos": [...], "modelo", "coleccion", "version_corpus"} (solo vigentes)."""
        if not self._url:
            raise ErrorProveedor("local", None, False, "sin URL")
        try:
            r = await self._http.post(self._url + "/buscar", headers={"X-Token-Interno": self._token},
                                      json={"texto": texto, "k": k})
        except httpx.HTTPError as e:
            raise ErrorProveedor("local", None, True, type(e).__name__) from None
        if r.status_code != 200:
            raise error_http("local", r.status_code)
        try:
            d = r.json()
            d["fragmentos"]
            return d
        except (ValueError, KeyError, TypeError):
            raise ErrorProveedor("local", 200, True, "respuesta inválida") from None
