import asyncio

import httpx
import pytest

from kerna_nucleo.enrutador import Enrutador, Nivel
from kerna_nucleo.proveedores import ErrorProveedor
from kerna_nucleo.proveedores.azure_openai import ClienteAzureOpenAI
from nucleo_apoyo import FakeGemini, Reloj, plazo_simulado


def cliente(handler, **kw):
    return ClienteAzureOpenAI("https://oai.openai.azure.com/", "k", http=httpx.AsyncClient(
        transport=httpx.MockTransport(handler)), **kw)


def test_generar_arma_la_peticion_y_lee_tokens():
    vistas = []

    def h(req):
        vistas.append(req)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{\"a\":1}"}}],
                                         "usage": {"prompt_tokens": 7, "completion_tokens": 3}})
    r = asyncio.run(cliente(h).generar("gpt-5-nano", "sis", "usu", {"type": "object"}))
    assert (r.texto, r.tokens_entrada, r.tokens_salida) == ("{\"a\":1}", 7, 3)
    q = vistas[0]
    assert "/deployments/gpt-5-nano/chat/completions" in str(q.url) and q.headers["api-key"] == "k"
    import json
    c = json.loads(q.content)
    assert c["response_format"] == {"type": "json_object"} and "temperature" not in c
    assert c["reasoning_effort"] == "low" and c["messages"][0]["role"] == "system"


@pytest.mark.parametrize("codigo,reint", [(429, True), (500, True), (400, False)])
def test_errores_http(codigo, reint):
    with pytest.raises(ErrorProveedor) as e:
        asyncio.run(cliente(lambda req: httpx.Response(codigo)).generar("m", "s", "u"))
    assert e.value.reintentable is reint


def test_respuesta_sin_contenido():
    with pytest.raises(ErrorProveedor):
        asyncio.run(cliente(lambda req: httpx.Response(200, json={})).generar("m", "s", "u"))


def test_enrutador_elige_cliente_por_proveedor():
    reloj = Reloj()
    azure = FakeGemini({"gpt-5-nano": lambda *a, **k: None})
    llamadas = []

    class Az:
        async def generar(self, modelo, *a, **k):
            llamadas.append(modelo)
            from kerna_nucleo.proveedores.gemini import RespuestaLLM
            return RespuestaLLM("{\"x\":1}", 5, 2)
    r = Enrutador([Nivel("oficial", "azure-openai", "gpt-5-nano")], azure, reloj=reloj, dormir=reloj.dormir,
                  plazo_llamada=plazo_simulado(reloj, []), clientes={"azure-openai": Az()})
    res = asyncio.run(r.generar("s", "u", None, lambda d: d, reloj()))
    assert llamadas == ["gpt-5-nano"] and res.proveedor == "azure-openai" and res.tokens_entrada == 5
