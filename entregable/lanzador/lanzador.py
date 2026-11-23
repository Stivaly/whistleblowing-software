"""Página de inicio de la instalación local: dice si cada parte está lista y lleva a cada lugar con un botón.

Solo biblioteca estándar. Corre en el contenedor «inicio» (misma imagen que el panel de Kerna).
"""
import json
import os
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

AQUI = Path(__file__).parent
FUENTES = Path(os.environ.get("FUENTES_DIR", "/app/app/estaticos"))
MANUALES = Path(os.environ.get("MANUALES_DIR", "/app/manuales"))

COMPROBACIONES = {
    "veridy": os.environ.get("VERIDY_SALUD", "http://veridy:8080/api/health"),
    "panel": os.environ.get("PANEL_SALUD", "http://panel:8000/salud"),
    "nube": os.environ.get("NUBE_SALUD", "") ,
}
TIPOS = {".html": "text/html; charset=utf-8", ".pdf": "application/pdf", ".woff2": "font/woff2",
         ".png": "image/png", ".svg": "image/svg+xml", ".css": "text/css", ".js": "text/javascript"}


def _responde(url: str) -> bool:
    if not url:
        return False
    try:
        with urllib.request.urlopen(url, timeout=25, context=ssl.create_default_context()) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def estado() -> dict:
    with ThreadPoolExecutor(3) as ex:
        res = dict(zip(COMPROBACIONES, ex.map(_responde, COMPROBACIONES.values())))
    return res


def datos_pagina() -> dict:
    e = os.environ
    return {
        "veridy": e.get("VERIDY_PUBLICA", "http://localhost:8401"),
        "panel": e.get("PANEL_PUBLICO", "http://localhost:8402"),
        "auditor_usuario": e.get("VERIDY_AUDITOR_USUARIO", ""),
        "auditor_clave": e.get("VERIDY_AUDITOR_CLAVE", ""),
        "panel_usuario": e.get("KERNA_PANEL_USUARIO", ""),
        "panel_clave": e.get("KERNA_PANEL_CLAVE", ""),
    }


class Manejador(BaseHTTPRequestHandler):
    server_version = "inicio"
    sys_version = ""

    def _enviar(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, base: Path, nombre: str) -> None:
        ruta = (base / nombre).resolve()
        if base.resolve() not in ruta.parents or not ruta.is_file():
            return self._enviar(404, b"No existe", "text/plain; charset=utf-8")
        self._enviar(200, ruta.read_bytes(), TIPOS.get(ruta.suffix, "application/octet-stream"))

    def do_GET(self):  # noqa: N802
        ruta = self.path.split("?", 1)[0]
        if ruta in ("/", "/index.html"):
            html = (AQUI / "inicio.html").read_text(encoding="utf-8")
            html = html.replace("/*DATOS*/{}", json.dumps(datos_pagina(), ensure_ascii=False))
            return self._enviar(200, html.encode("utf-8"), TIPOS[".html"])
        if ruta == "/estado":
            return self._enviar(200, json.dumps(estado()).encode(), "application/json")
        if ruta.startswith("/fuentes/"):
            return self._archivo(FUENTES, ruta[len("/fuentes/"):])
        if ruta.startswith("/manuales/"):
            return self._archivo(MANUALES, ruta[len("/manuales/"):])
        if ruta.startswith("/recursos/"):
            return self._archivo(AQUI / "recursos", ruta[len("/recursos/"):])
        return self._enviar(404, b"No existe", "text/plain; charset=utf-8")

    def log_message(self, formato, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8400), Manejador).serve_forever()
