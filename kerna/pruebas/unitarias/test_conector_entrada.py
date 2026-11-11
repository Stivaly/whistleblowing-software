"""Envoltorio de arranque del conector (entrada.py) y marca de las peticiones a Veridy."""
import importlib.util
import socket
from pathlib import Path

import httpx

from kerna_conector.veridy import MARCA_PETICION, ClienteVeridy

RUTA = Path(__file__).resolve().parents[2] / "conector" / "entrada.py"
spec = importlib.util.spec_from_file_location("entrada", RUTA)
entrada = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entrada)


def test_uri_estado_codifica_la_clave_y_exige_tls():
    uri = entrada.uri_estado("srv.postgres.database.azure.com", "a/b:c@d")
    assert uri.startswith("postgresql://kerna_conector:a%2Fb%3Ac%40d@srv.postgres.database.azure.com:5432/kerna_conector")
    assert "sslmode=verify-full" in uri


def test_resolver_local_solo_afecta_al_nombre(monkeypatch):
    vistos = []
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *a, **k: vistos.append(host) or [])
    entrada.resolver_local("veridy.example")
    socket.getaddrinfo("veridy.example", 443)
    socket.getaddrinfo("otro.example", 443)
    assert vistos == ["127.0.0.1", "otro.example"]


def test_peticiones_a_veridy_llevan_la_marca():
    urls = []

    def responder(req: httpx.Request):
        urls.append(str(req.url))
        return httpx.Response(200, json=[])

    c = ClienteVeridy("https://v.example:8443", "u", "p", http=httpx.Client(transport=httpx.MockTransport(responder)))
    c._crudo("GET", "/api/recipient/rtips")
    c._crudo("GET", "/api/x?a=1")
    assert urls == ["https://v.example:8443/api/recipient/rtips?" + MARCA_PETICION,
                    "https://v.example:8443/api/x?a=1&" + MARCA_PETICION]
