"""Cliente de Qdrant Cloud (REST)."""
from __future__ import annotations

import httpx

from . import ErrorProveedor, error_http

ID_META = "00000000-0000-0000-0000-000000000000"


class ClienteQdrant:
    proveedor = "qdrant"

    def __init__(self, url: str, api_key: str, http: httpx.AsyncClient | None = None, timeout: float = 20.0):
        self._url = url.rstrip("/")
        self._key = api_key
        self._http = http or httpx.AsyncClient(timeout=timeout)

    async def _post(self, ruta: str, cuerpo: dict) -> dict:
        try:
            r = await self._http.post(self._url + ruta, headers={"api-key": self._key}, json=cuerpo)
        except httpx.HTTPError as e:
            raise ErrorProveedor("qdrant", None, True, type(e).__name__) from None
        if r.status_code != 200:
            raise error_http("qdrant", r.status_code)
        try:
            return r.json()
        except ValueError:
            raise ErrorProveedor("qdrant", 200, True, "respuesta inválida") from None

    async def buscar(self, coleccion: str, vector: list[float], k: int) -> list[dict]:
        """Top-k vigentes (filtro vigente = true, sin el punto meta). Cada resultado: payload + "puntaje"."""
        cuerpo = {"vector": vector, "limit": k, "with_payload": True, "with_vector": False,
                  "filter": {"must": [{"key": "vigente", "match": {"value": True}}],
                             "must_not": [{"has_id": [ID_META]}]}}
        out = await self._post(f"/collections/{coleccion}/points/search", cuerpo)
        try:
            return [dict(p["payload"], puntaje=float(p["score"])) for p in out["result"]]
        except (KeyError, TypeError, ValueError):
            raise ErrorProveedor("qdrant", 200, True, "respuesta inválida") from None

    async def version_corpus(self, coleccion: str) -> int:
        """`version_corpus` del punto meta; 0 si no existe."""
        out = await self._post(f"/collections/{coleccion}/points",
                               {"ids": [ID_META], "with_payload": True, "with_vector": False})
        try:
            puntos = out.get("result") or []
            return int((puntos[0].get("payload") or {}).get("version_corpus", 0)) if puntos else 0
        except (AttributeError, TypeError, ValueError):
            return 0
