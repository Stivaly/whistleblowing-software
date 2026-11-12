"""Cliente REST de chat de Azure OpenAI (despliegues gpt-5-*), con la misma interfaz que ClienteGemini."""
from __future__ import annotations

import httpx

from . import ErrorProveedor, error_http
from .gemini import RespuestaLLM

API_VERSION = "2025-04-01-preview"


class ClienteAzureOpenAI:
    proveedor = "azure-openai"

    def __init__(self, endpoint: str, api_key: str, http: httpx.AsyncClient | None = None,
                 timeout: float = 180.0, esfuerzo: str = "low", api_version: str = API_VERSION,
                 max_salida: int = 16000):
        self._base = endpoint.rstrip("/")
        self._key = api_key
        self._http = http or httpx.AsyncClient(timeout=timeout)
        self._esfuerzo, self._ver, self._max = esfuerzo, api_version, max_salida

    def _url(self, modelo: str) -> str:
        return f"{self._base}/openai/deployments/{modelo}/chat/completions?api-version={self._ver}"

    async def generar(self, modelo: str, sistema: str, usuario: str, esquema: dict | None = None,
                      con_sistema: bool = True, temperatura: float = 0.2,
                      degradar: bool = False) -> RespuestaLLM:
        """`esquema` solo activa el modo JSON (el esquema ya viaja descrito en el prompt); la temperatura
        no se envía (los modelos de razonamiento solo aceptan la predeterminada)."""
        cuerpo: dict = {"messages": [{"role": "system" if con_sistema else "user", "content": sistema},
                                     {"role": "user", "content": usuario}],
                        "max_completion_tokens": self._max}
        if esquema is not None:
            cuerpo["response_format"] = {"type": "json_object"}
        if self._esfuerzo:
            cuerpo["reasoning_effort"] = self._esfuerzo
        try:
            r = await self._http.post(self._url(modelo), headers={"api-key": self._key}, json=cuerpo)
        except httpx.HTTPError as e:
            raise ErrorProveedor("azure-openai", None, True, type(e).__name__) from None
        if r.status_code != 200:
            raise error_http("azure-openai", r.status_code)
        try:
            datos = r.json()
            texto = datos["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError):
            raise ErrorProveedor("azure-openai", 200, True, "respuesta sin contenido") from None
        uso = datos.get("usage") or {}
        return RespuestaLLM(texto, int(uso.get("prompt_tokens", 0) or 0), int(uso.get("completion_tokens", 0) or 0))

    async def salud(self, modelo: str) -> bool:
        try:
            r = await self.generar(modelo, "Responde {}", "{}", {"type": "object"})
            return bool(r.texto)
        except (ErrorProveedor, ValueError):
            return False
