"""Protección de /panel y /api/*.

Modo "clave" (FRONT_AUTH=clave, por defecto): clave compartida guardada en Key Vault, entregada a la app como
referencia de Key Vault en FRONT_CLAVE. Se acepta por cabecera X-Clave (APIs) o por cookie firmada tras /acceso.
Modo "entra": Easy Auth de App Service ya autenticó a la persona; se exige su cabecera X-MS-CLIENT-PRINCIPAL-ID.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

COOKIE = "kerna_panel"
VIDA_S = 8 * 3600
_fallos: dict[str, list[float]] = {}


def _clave() -> str:
    c = os.environ.get("FRONT_CLAVE", "")
    # Una referencia de Key Vault sin resolver llega como texto literal: se trata como "sin clave".
    return "" if not c or c.startswith("@Microsoft.KeyVault") else c


def _firma(exp: int) -> str:
    return hmac.new(_clave().encode(), f"kerna-panel:{exp}".encode(), hashlib.sha256).hexdigest()


def emitir_cookie() -> str:
    exp = int(time.time()) + VIDA_S
    return f"{exp}.{_firma(exp)}"


def clave_valida(candidata: str) -> bool:
    c = _clave()
    return bool(c) and hmac.compare_digest(candidata.encode(), c.encode())


def _cookie_valida(valor: str | None) -> bool:
    if not valor or not _clave() or "." not in valor:
        return False
    exp, firma = valor.split(".", 1)
    return exp.isdigit() and int(exp) > time.time() and hmac.compare_digest(firma, _firma(int(exp)))


def autorizado(cabeceras, cookies) -> bool:
    if os.environ.get("FRONT_AUTH", "clave") == "entra":
        return bool(cabeceras.get("x-ms-client-principal-id"))
    return clave_valida(cabeceras.get("x-clave", "")) or _cookie_valida(cookies.get(COOKIE))


def limitar(ip: str, max_fallos: int = 5, ventana_s: int = 300) -> bool:
    """True si la IP puede intentar; registra el intento fallido con `fallo(ip)`."""
    ahora = time.time()
    _fallos[ip] = [t for t in _fallos.get(ip, []) if ahora - t < ventana_s]
    return len(_fallos[ip]) < max_fallos


def fallo(ip: str) -> None:
    _fallos.setdefault(ip, []).append(time.time())
