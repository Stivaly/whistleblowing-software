"""OAuth 2.0 client credentials con JWT HS256 de 10 minutos."""
from __future__ import annotations

import hashlib
import hmac

import jwt

DURACION_S = 600
ALGORITMO = "HS256"
_RELLENO = "0" * 64


class Autenticador:
    def __init__(self, clientes: dict, secreto_jwt: str, reloj):
        self._clientes = clientes or {}
        self._secreto = secreto_jwt
        self._reloj = reloj

    def emitir(self, client_id: str, client_secret: str) -> str | None:
        """Token si las credenciales coinciden; el secreto se compara en tiempo constante contra su sha256."""
        datos = self._clientes.get(client_id)
        esperado = (datos or {}).get("secreto_sha256", _RELLENO)
        recibido = hashlib.sha256((client_secret or "").encode()).hexdigest()
        coincide = hmac.compare_digest(recibido.encode(), str(esperado).lower().encode())
        if not datos or not coincide:
            return None
        ahora = int(self._reloj())
        return jwt.encode({"sub": client_id, "cliente": datos.get("cliente", client_id),
                           "iat": ahora, "exp": ahora + DURACION_S}, self._secreto, algorithm=ALGORITMO)

    def verificar(self, token: str) -> str | None:
        """Devuelve el nombre del cliente si el token es válido y no venció (según el reloj inyectado)."""
        try:
            datos = jwt.decode(token, self._secreto, algorithms=[ALGORITMO],
                               options={"verify_exp": False, "verify_iat": False, "require": ["exp", "sub"]})
        except jwt.PyJWTError:
            return None
        if self._reloj() >= datos["exp"]:
            return None
        if datos["sub"] not in self._clientes:
            return None
        return str(datos.get("cliente") or datos["sub"])
