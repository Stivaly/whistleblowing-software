"""Pasarela de identidad de Kerna para la instalación local de prueba.

Los contenedores que corren en el computador de quien prueba (panel de Kerna y conector de Veridy) no tienen
identidad de Azure. Esta pasarela corre en Azure con su identidad administrada y les entrega tokens de corta
duración (~1 h), solo para los servicios que esos contenedores usan, a quien presente la clave de la pasarela.
Habla el mismo protocolo que la identidad administrada de App Service (IDENTITY_ENDPOINT + IDENTITY_HEADER),
así que azure-identity (DefaultAzureCredential) la usa sin cambios en el código. Todo va por HTTPS (443).
Solo biblioteca estándar. Nunca registra la clave ni los tokens.
"""
import hmac
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PERMITIDOS = ("https://api.loganalytics.io", "https://storage.azure.com", "https://management.azure.com")
log = logging.getLogger("pasarela")


def clave_valida(recibida: str) -> bool:
    esperada = os.environ.get("PASARELA_CLAVE", "")
    return bool(esperada) and hmac.compare_digest(recibida.encode(), esperada.encode())


def token_identidad(recurso: str) -> bytes:
    q = {"resource": recurso, "api-version": "2019-08-01"}
    if os.environ.get("AZURE_CLIENT_ID"):
        q["client_id"] = os.environ["AZURE_CLIENT_ID"]
    req = urllib.request.Request(os.environ["IDENTITY_ENDPOINT"] + "?" + urllib.parse.urlencode(q),
                                 headers={"X-IDENTITY-HEADER": os.environ["IDENTITY_HEADER"]})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


class Manejador(BaseHTTPRequestHandler):
    server_version = "kerna-pasarela"
    sys_version = ""

    def _responder(self, codigo: int, cuerpo: bytes, tipo: str = "application/json") -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):  # noqa: N802
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/salud":
            return self._responder(200, b"ok", "text/plain")
        if url.path != "/token":
            return self._responder(404, b'{"error":"no_existe"}')
        if not clave_valida(self.headers.get("X-IDENTITY-HEADER", "")):
            return self._responder(401, b'{"error":"clave_invalida"}')
        recurso = (urllib.parse.parse_qs(url.query).get("resource") or [""])[0].rstrip("/")
        if recurso not in PERMITIDOS:
            return self._responder(403, b'{"error":"recurso_no_permitido"}')
        try:
            cuerpo = token_identidad(recurso)
        except (urllib.error.URLError, OSError) as exc:
            log.warning("identidad no disponible: %s", type(exc).__name__)
            return self._responder(503, b'{"error":"identidad_no_disponible"}')
        log.info("token entregado: %s", recurso)
        return self._responder(200, cuerpo)

    def log_message(self, formato, *args):  # sin registro de rutas ni parámetros
        pass


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PUERTO", "8080"))), Manejador).serve_forever()


if __name__ == "__main__":
    main()
