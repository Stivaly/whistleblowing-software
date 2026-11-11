"""Cliente REST de Gemini (generateContent) con salida JSON."""
from __future__ import annotations

import httpx

from . import ErrorProveedor, error_http

BASE = "https://generativelanguage.googleapis.com/v1beta"


class RespuestaLLM:
    __slots__ = ("texto", "tokens_entrada", "tokens_salida")

    def __init__(self, texto: str, tokens_entrada: int = 0, tokens_salida: int = 0):
        self.texto = texto
        self.tokens_entrada = tokens_entrada
        self.tokens_salida = tokens_salida


class ClienteGemini:
    proveedor = "gemini"

    def __init__(self, api_key: str, http: httpx.AsyncClient | None = None, base_url: str = BASE,
                 timeout: float = 30.0):
        self._key = api_key
        self._http = http or httpx.AsyncClient(timeout=timeout)
        self._base = base_url.rstrip("/")

    def _cabeceras(self) -> dict:
        return {"x-goog-api-key": self._key, "Content-Type": "application/json"}

    async def generar(self, modelo: str, sistema: str, usuario: str, esquema: dict | None = None,
                      con_sistema: bool = True, temperatura: float = 0.2,
                      degradar: bool = False) -> RespuestaLLM:
        """Una llamada. `esquema` y `con_sistema` se omiten para modelos que no los aceptan (Gemma):
        en ese caso la instrucción de sistema se antepone al mensaje del usuario."""
        cuerpo: dict = {"generationConfig": {"temperature": temperatura}}
        if esquema is not None:
            cuerpo["generationConfig"]["responseMimeType"] = "application/json"
            cuerpo["generationConfig"]["responseSchema"] = esquema
        if con_sistema:
            cuerpo["systemInstruction"] = {"parts": [{"text": sistema}]}
            texto_usuario = usuario
        else:
            texto_usuario = f"{sistema}\n\n{usuario}"
        cuerpo["contents"] = [{"role": "user", "parts": [{"text": texto_usuario}]}]
        try:
            r = await self._http.post(f"{self._base}/models/{modelo}:generateContent",
                                      headers=self._cabeceras(), json=cuerpo)
        except httpx.HTTPError as e:
            raise ErrorProveedor("gemini", None, True, type(e).__name__) from None
        if r.status_code == 400 and degradar and (esquema is not None or con_sistema):
            # el modelo no acepta esquema JSON o instrucción de sistema: se repite en modo sin esquema
            return await self.generar(modelo, sistema, usuario, None, False, temperatura, degradar=False)
        if r.status_code != 200:
            raise error_http("gemini", r.status_code)
        try:
            datos = r.json()
            partes = datos["candidates"][0]["content"]["parts"]
            texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
        except (ValueError, KeyError, IndexError, TypeError):
            raise ErrorProveedor("gemini", 200, True, "respuesta sin contenido") from None
        uso = datos.get("usageMetadata") or {}
        return RespuestaLLM(texto, int(uso.get("promptTokenCount", 0) or 0),
                            int(uso.get("candidatesTokenCount", 0) or 0))

    async def salud(self, modelo: str) -> bool:
        try:
            r = await self._http.get(f"{self._base}/models/{modelo}", headers=self._cabeceras())
            return r.status_code == 200
        except httpx.HTTPError:
            return False
