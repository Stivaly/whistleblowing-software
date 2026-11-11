"""Cliente HTTP de Veridy (GlobaLeaks): sesión de la cuenta de servicio, lectura de casos y notas internas.

Protocolo de acceso verificado contra el código de Veridy (rest/api.py, handlers/auth):
- `POST /api/auth/type` devuelve `type` y `salt`; con `type == "key"` la contraseña viaja derivada con argon2id.
- `POST /api/auth/token` entrega una prueba de trabajo (`id`, `salt`); se resuelve y se envía en `x-token`.
- `POST /api/auth/authentication` devuelve `id` (cabecera `X-Session`), `user_id` y `role`.
- La sesión dura 120 s sin renovarse por uso: el cliente la renueva antes de que venza y ante 401/412.
"""
from __future__ import annotations

import base64
import threading
import time
from typing import Any, Optional

import httpx
from nacl.pwhash import argon2id

VIDA_SESION_S = 90  # la sesión de Veridy dura 120 s; se renueva antes
CODIGOS_SESION_VENCIDA = (401, 412)


class ErrorVeridy(Exception):
    """Falla al hablar con Veridy. `codigo` es el estado HTTP (None si fue de red)."""

    def __init__(self, mensaje: str, codigo: Optional[int] = None):
        super().__init__(mensaje)
        self.codigo = codigo


class CasoNoAccesible(ErrorVeridy):
    """403 o 404: la cuenta no puede leer ese caso."""


def derivar_password(password: str, salt_b64: str) -> str:
    """base64(argon2id(password, base64(salt)[:16], opslimit=16, memlimit=2^27, 32 bytes))."""
    sal = base64.b64decode(salt_b64)[:16]
    clave = argon2id.kdf(32, password.encode(), sal, opslimit=16, memlimit=1 << 27)
    return base64.b64encode(clave).decode()


def prueba_de_trabajo(id_token: str, salt_b64: str, tope: int = 5_000_000) -> int:
    """Menor `c >= 0` tal que argon2id(id + str(c), salt, opslimit=1, memlimit=2^20) tiene el byte 31 en 0."""
    sal = base64.b64decode(salt_b64)[:16]
    for c in range(tope):
        h = argon2id.kdf(32, (id_token + str(c)).encode(), sal, opslimit=1, memlimit=1 << 20)
        if h[31] == 0:
            return c
    raise ErrorVeridy("prueba de trabajo sin solución")


MARCA_PETICION = "kerna_conector=1"


def _marca(ruta: str) -> str:
    """Parámetro inocuo que identifica las peticiones del conector en el access.log de Veridy: el vigía de
    inactividad no las cuenta como uso."""
    return ("&" if "?" in ruta else "?") + MARCA_PETICION


class ClienteVeridy:
    def __init__(self, url: str, usuario: str, password: str, tid: int = 0,
                 http: Optional[httpx.Client] = None, reloj=time.monotonic, vida_sesion_s: float = VIDA_SESION_S):
        self._url = url.rstrip("/")
        self._usuario = usuario
        self._password = password
        self._tid = tid
        self._http = http or httpx.Client(timeout=60)
        self._reloj = reloj
        self._vida = vida_sesion_s
        self._sesion: Optional[str] = None
        self._desde = 0.0
        self._id_usuario: Optional[str] = None
        self._cerrojo = threading.RLock()

    # ---- sesión -------------------------------------------------------------------------------------------
    def _crudo(self, metodo: str, ruta: str, json: Any = None, cabeceras: Optional[dict] = None) -> httpx.Response:
        try:
            return self._http.request(metodo, self._url + ruta + _marca(ruta), json=json, headers=cabeceras or {})
        except httpx.HTTPError as exc:
            raise ErrorVeridy("error de red hacia Veridy (%s)" % type(exc).__name__) from None

    @staticmethod
    def _json(r: httpx.Response) -> Any:
        try:
            return r.json()
        except ValueError:
            return {}

    def iniciar_sesion(self) -> str:
        with self._cerrojo:
            r = self._crudo("POST", "/api/auth/type", {"username": self._usuario})
            if r.status_code not in (200, 201):
                raise ErrorVeridy("no se pudo consultar el tipo de acceso", r.status_code)
            tipo = self._json(r)
            clave = self._password
            if tipo.get("type") == "key":
                clave = derivar_password(self._password, tipo["salt"])
            r = self._crudo("POST", "/api/auth/token", {})
            if r.status_code not in (200, 201):
                raise ErrorVeridy("no se pudo obtener la prueba de trabajo", r.status_code)
            t = self._json(r)
            c = prueba_de_trabajo(t["id"], t["salt"])
            r = self._crudo("POST", "/api/auth/authentication",
                            {"tid": self._tid, "username": self._usuario, "password": clave, "authcode": ""},
                            {"x-token": "%s:%d" % (t["id"], c)})
            if r.status_code not in (200, 201):
                raise ErrorVeridy("inicio de sesión rechazado", r.status_code)
            datos = self._json(r)
            self._sesion = datos["id"]
            self._id_usuario = datos.get("user_id")
            self._desde = self._reloj()
            return self._sesion

    def cerrar_sesion(self) -> None:
        with self._cerrojo:
            if not self._sesion:
                return
            try:
                self._crudo("DELETE", "/api/auth/session", cabeceras={"X-Session": self._sesion})
            except ErrorVeridy:
                pass
            finally:
                self._sesion = None

    @property
    def id_usuario(self) -> str:
        """Identificador de la cuenta de servicio (campo `user_id` de la respuesta del login)."""
        with self._cerrojo:
            if not self._sesion or not self._id_usuario:
                self.iniciar_sesion()
            return self._id_usuario  # type: ignore[return-value]

    def _sesion_vigente(self) -> str:
        with self._cerrojo:
            if not self._sesion or self._reloj() - self._desde >= self._vida:
                self.iniciar_sesion()
            return self._sesion  # type: ignore[return-value]

    def _solicitar(self, metodo: str, ruta: str, json: Any = None) -> httpx.Response:
        r = self._crudo(metodo, ruta, json, {"X-Session": self._sesion_vigente()})
        if r.status_code in CODIGOS_SESION_VENCIDA:
            with self._cerrojo:
                self._sesion = None
            r = self._crudo(metodo, ruta, json, {"X-Session": self._sesion_vigente()})
        return r

    # ---- casos --------------------------------------------------------------------------------------------
    def listar_casos(self) -> list[dict]:
        r = self._solicitar("GET", "/api/recipient/rtips")
        if r.status_code != 200:
            raise ErrorVeridy("no se pudo listar los casos", r.status_code)
        datos = self._json(r)
        return datos if isinstance(datos, list) else []

    def leer_caso(self, id_caso: str) -> dict:
        r = self._solicitar("GET", "/api/recipient/rtips/" + id_caso)
        if r.status_code in (403, 404):
            raise CasoNoAccesible("el caso no es accesible para la cuenta", r.status_code)
        if r.status_code != 200:
            raise ErrorVeridy("no se pudo leer el caso", r.status_code)
        datos = self._json(r)
        if not isinstance(datos, dict):
            raise ErrorVeridy("respuesta de caso ilegible", r.status_code)
        return datos

    def publicar_nota(self, id_caso: str, contenido: str) -> dict:
        """Publica un comentario SIEMPRE interno (visibilidad `internal`). Devuelve el comentario con su `id`."""
        r = self._solicitar("POST", "/api/recipient/rtips/%s/comments" % id_caso,
                            {"content": contenido, "visibility": "internal"})
        if r.status_code in (403, 404):
            raise CasoNoAccesible("el caso no admite la nota", r.status_code)
        if r.status_code not in (200, 201):
            raise ErrorVeridy("no se pudo publicar la nota", r.status_code)
        return self._json(r)
