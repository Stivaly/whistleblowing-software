"""Protección de /panel y /api/*: sesión de una cuenta (usuario + contraseña + rol) en una cookie firmada.

Modo "clave" (FRONT_AUTH=clave, por defecto): la persona entra en /acceso con su usuario y contraseña (cuentas.py). La cookie
`kerna_panel` va firmada (HMAC con la clave de la app, FRONT_CLAVE, que llega de Key Vault), dura 8 horas y lleva el usuario, el rol y la
versión de sesión; en cada petición se comprueba contra la cuenta (existe, está activa, misma versión y rol), así que cambiar la clave o el
rol, desactivar o eliminar la cuenta la invalida al instante.
La clave compartida FRONT_CLAVE solo vale por cabecera X-Clave en las rutas /api/* (la usan scripts) y da lectura de Resumen y Negocio.
Modo "entra": Easy Auth de App Service ya autenticó a la persona; se exige su cabecera X-MS-CLIENT-PRINCIPAL-ID y se le da rol Dirección.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

COOKIE = "kerna_panel"
VIDA_S = 8 * 3600
_fallos: dict[str, list[float]] = {}


@dataclass(frozen=True)
class Sesion:
    usuario: str
    nombre: str
    rol: str
    cambiar: bool = False        # debe cambiar su contraseña antes de entrar al panel
    via: str = "cookie"          # cookie | clave (X-Clave en /api) | entra (Easy Auth)

    @property
    def propia(self) -> bool:
        """Tiene contraseña propia que puede cambiar en «Mi cuenta»."""
        return self.via == "cookie"


def _clave() -> str:
    c = os.environ.get("FRONT_CLAVE", "")
    # Una referencia de Key Vault sin resolver llega como texto literal: se trata como "sin clave".
    return "" if not c or c.startswith("@Microsoft.KeyVault") else c


def clave_compartida() -> str:
    return _clave()


def _firmar(texto: str) -> str:
    return hmac.new(_clave().encode(), f"kerna-sesion:{texto}".encode(), hashlib.sha256).hexdigest()


def emitir_cookie(usuario: str = "admin", version: int = 1, rol: str = "direccion", vida_s: int = VIDA_S) -> str:
    """Cookie de sesión: «carga.firma». La carga (usuario, rol, versión de sesión, vencimiento) va en base64 y la firma la protege."""
    carga = base64.urlsafe_b64encode(json.dumps({"u": usuario, "r": rol, "v": int(version), "e": int(time.time()) + vida_s}, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{carga}.{_firmar(carga)}"


def leer_cookie(valor: str | None) -> dict | None:
    if not valor or not _clave() or valor.count(".") != 1:
        return None
    carga, firma = valor.split(".")
    if not hmac.compare_digest(firma, _firmar(carga)):
        return None
    try:
        d = json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))
        if int(d["e"]) <= time.time() or not isinstance(d["u"], str) or not isinstance(d["r"], str):
            return None
        return {"u": d["u"], "r": d["r"], "v": int(d["v"])}
    except (ValueError, KeyError, TypeError):
        return None


def clave_valida(candidata: str) -> bool:
    c = _clave()
    return bool(c) and hmac.compare_digest((candidata or "").encode(), c.encode())


def sesion_de(cabeceras, cookies, ruta: str = "") -> Sesion | None:
    """La sesión de quien hace la petición, o None. Con la tabla de cuentas caída lanza la excepción (quien llama responde 503)."""
    if os.environ.get("FRONT_AUTH", "clave") == "entra":
        pid = cabeceras.get("x-ms-client-principal-id")
        if not pid:
            return None
        nombre = (cabeceras.get("x-ms-client-principal-name") or pid)[:80]
        return Sesion(usuario=nombre, nombre=nombre, rol="direccion", via="entra")
    if ruta.startswith("/api/") and clave_valida(cabeceras.get("x-clave", "")):
        return Sesion(usuario="scripts", nombre="Scripts con clave compartida", rol="servicio", via="clave")
    d = leer_cookie(cookies.get(COOKIE))
    if d is None:
        return None
    from . import cuentas
    f = cuentas.sesion_valida(d["u"], d["v"], d["r"])
    if f is None:
        return None
    return Sesion(usuario=f["RowKey"], nombre=f.get("nombre") or f["RowKey"], rol=f.get("rol") or "invitado", cambiar=bool(f.get("debe_cambiar_clave")))


def limitar(ip: str, max_fallos: int = 5, ventana_s: int = 300) -> bool:
    """True si la IP puede intentar; registra el intento fallido con `fallo(ip)`."""
    ahora = time.time()
    _fallos[ip] = [t for t in _fallos.get(ip, []) if ahora - t < ventana_s]
    return len(_fallos[ip]) < max_fallos


def espera_s(ip: str, ventana_s: int = 300) -> float:
    """Segundos que faltan para que la IP bloqueada pueda intentar de nuevo (0 si no está bloqueada)."""
    ts = [t for t in _fallos.get(ip, []) if time.time() - t < ventana_s]
    return max(0.0, min(ts) + ventana_s - time.time()) if ts else 0.0


def fallo(ip: str) -> None:
    _fallos.setdefault(ip, []).append(time.time())


def token_csrf(cookies) -> str:
    """Token ligado a la sesión: se deriva de la cookie del panel. Va en un campo oculto del formulario."""
    base = cookies.get(COOKIE) or "sin-cookie"
    return hmac.new(_clave().encode(), f"kerna-csrf:{base}".encode(), hashlib.sha256).hexdigest()


def csrf_valido(cookies, candidato: str) -> bool:
    return bool(_clave()) and hmac.compare_digest((candidato or "").encode(), token_csrf(cookies).encode())
