"""Arranque del Conector Veridy dentro del grupo de contenedores de Veridy en Azure.

Con la identidad administrada del grupo lee de Key Vault los secretos del conector, arma el entorno y ejecuta
`kerna_conector`. Así ningún valor secreto pasa por Terraform ni por variables de entorno del grupo.

Variables: AZURE_CLIENT_ID, VERIDY_KV_URL, VERIDY_PG_FQDN (servidor del estado), VERIDY_RESOLVER_LOCAL (nombre
público de Veridy, que se resuelve a 127.0.0.1: el certificado y el nombre de host de Veridy exigen el nombre
público, y el tráfico no sale del grupo). Solo usa la biblioteca estándar.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.parse
import urllib.request

SECRETOS = {
    "VERIDY_PASSWORD": "veridy-kerna-conector-password",
    "KERNA_CLIENT_ID": "kerna-client-id",
    "KERNA_CLIENT_SECRET": "kerna-client-secret",
}
SECRETO_PG = "conector-pg-password"


def _token(client_id: str) -> str:
    q = urllib.parse.urlencode({"api-version": "2018-02-01", "resource": "https://vault.azure.net",
                                "client_id": client_id})
    req = urllib.request.Request(f"http://169.254.169.254/metadata/identity/oauth2/token?{q}",
                                 headers={"Metadata": "true"})
    for intento in range(10):
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.load(r)["access_token"]
        except OSError:
            print("identidad no disponible aún; reintento", flush=True)
            time.sleep(3 * (intento + 1))
    sys.exit("no se obtuvo token de la identidad administrada")


def leer_secreto(kv_url: str, token: str, nombre: str) -> str:
    req = urllib.request.Request(f"{kv_url.rstrip('/')}/secrets/{nombre}?api-version=7.4",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["value"]


def uri_estado(fqdn: str, clave: str) -> str:
    return (f"postgresql://kerna_conector:{urllib.parse.quote(clave, safe='')}@{fqdn}:5432/kerna_conector"
            "?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt")


def resolver_local(nombre: str) -> None:
    """Hace que `nombre` resuelva a 127.0.0.1 en este proceso (el resto sigue con el DNS normal)."""
    original = socket.getaddrinfo

    def getaddrinfo(host, *args, **kw):
        return original("127.0.0.1" if host == nombre else host, *args, **kw)

    socket.getaddrinfo = getaddrinfo


def main() -> int:
    kv = os.environ["VERIDY_KV_URL"]
    tok = _token(os.environ["AZURE_CLIENT_ID"])
    for var, secreto in SECRETOS.items():
        os.environ[var] = leer_secreto(kv, tok, secreto)
    os.environ["CONECTOR_ESTADO"] = uri_estado(os.environ["VERIDY_PG_FQDN"], leer_secreto(kv, tok, SECRETO_PG))
    if os.environ.get("VERIDY_RESOLVER_LOCAL"):
        resolver_local(os.environ["VERIDY_RESOLVER_LOCAL"])
    print("secretos cargados; iniciando el conector", flush=True)
    from kerna_conector.__main__ import main as conector
    return conector([])


if __name__ == "__main__":
    sys.exit(main())
