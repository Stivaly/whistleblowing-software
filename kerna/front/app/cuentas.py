"""Cuentas del panel de Kerna: usuario, contraseña y rol. Viven en las tablas `cuentas` y `cuentaseventos` del Storage del núcleo.

- `cuentas`: una fila por persona (PartitionKey «cuenta», RowKey = usuario en minúsculas) con nombre, correo, rol, la huella argon2id de
  su contraseña, si está activa, si debe cambiarla, fechas, intentos fallidos, bloqueo temporal y la versión de sesión (al cambiar la
  clave, el rol o dar de baja la cuenta sube y las sesiones abiertas dejan de valer).
- `cuentaseventos`: auditoría (altas, ediciones, cambios de rol, claves, eliminaciones, accesos). Nunca guarda contraseñas, claves
  temporales ni huellas.

Las contraseñas nunca se guardan ni se registran en claro: solo la huella argon2id (con su sal). La contraseña temporal de una cuenta
nueva o restablecida se envía por correo (`correo.enviar`) y se muestra una sola vez a quien la creó o restableció.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from . import permisos

log = logging.getLogger("kerna.front.cuentas")

T_CUENTAS, T_EVENTOS = "cuentas", "cuentaseventos"
PK, PK_EVENTO = "cuenta", "evento"
INTENTOS_MAX = 5                 # fallos seguidos de una cuenta antes del bloqueo temporal
BLOQUEO_S = 15 * 60
CLAVE_MIN, CLAVE_MAX = 12, 128
CACHE_S = 10                     # cuánto se recuerda una cuenta entre peticiones (se descarta al escribirla)
ACCIONES = ("creada", "editada", "rol_cambiado", "clave_restablecida", "clave_cambiada", "eliminada", "desactivada",
            "acceso_ok", "acceso_fallido", "bloqueada")
_USUARIO = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
_CORREO = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,120}\.[^@\s.]{2,}$")
_ALFABETO_TEMPORAL = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"   # sin letras que se confunden (I, l, O, 0, 1)

_hasher = PasswordHasher()       # argon2id (RFC 9106, perfil de poca memoria: 3 pasadas, 64 MiB, 4 hilos), con sal aleatoria incluida
_cerrojo = threading.Lock()
_cache: dict[str, tuple[float, dict | None]] = {}
_sembrada = False
_DUMMY = _hasher.hash("kerna-relleno-para-igualar-tiempos")


class ErrorCuenta(Exception):
    """`codigo`: invalido | existe | no_existe | clave_corta | clave_larga | clave_igual | clave_actual | ultima_direccion | propia |
    clave_obvia | externa."""

    def __init__(self, codigo: str):
        super().__init__(codigo)
        self.codigo = codigo


def _tabla(nombre):
    from azure.data.tables import TableClient
    from azure.identity import DefaultAzureCredential
    url = os.environ.get("CUENTAS_TABLA_URL") or os.environ["NEGOCIO_TABLA_URL"]
    return TableClient(endpoint=url, table_name=nombre, credential=DefaultAzureCredential())


def _ahora(t: float | None = None) -> str:
    return datetime.fromtimestamp(t if t is not None else time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalizar(usuario: str) -> str:
    return (usuario or "").strip().lower()


# ---- lectura -----------------------------------------------------------------------------------------------------------------------

def _leer(usuario: str) -> dict | None:
    from azure.core.exceptions import ResourceNotFoundError
    try:
        return dict(_tabla(T_CUENTAS).get_entity(PK, usuario))
    except ResourceNotFoundError:
        return None


def obtener(usuario: str, fresco: bool = False) -> dict | None:
    """La fila completa de la cuenta (con su huella): solo para uso interno, nunca para una plantilla."""
    u = normalizar(usuario)
    if not _USUARIO.match(u):
        return None
    ahora = time.time()
    with _cerrojo:
        hit = _cache.get(u)
    if hit and not fresco and ahora - hit[0] < CACHE_S:
        return hit[1]
    fila = _leer(u)
    with _cerrojo:
        _cache[u] = (ahora, fila)
    return fila


def _olvidar(usuario: str) -> None:
    with _cerrojo:
        _cache.pop(usuario, None)


def olvidar_todo() -> None:
    global _sembrada
    with _cerrojo:
        _cache.clear()
    _sembrada = False


def publica(f: dict) -> dict:
    """La cuenta sin su huella ni la versión de sesión: lo único que llega a una plantilla."""
    return {"usuario": f["RowKey"], "nombre": f.get("nombre") or f["RowKey"], "correo": f.get("correo") or "", "rol": f.get("rol") or "invitado",
            "rol_nombre": permisos.nombre_rol(f.get("rol") or "invitado"), "activa": bool(f.get("activa", True)),
            "debe_cambiar_clave": bool(f.get("debe_cambiar_clave")), "creada": f.get("creada") or "", "ultimo_acceso": f.get("ultimo_acceso") or "",
            "bloqueada": (f.get("bloqueada_hasta") or "") > _ahora()}


def listar() -> list[dict]:
    filas = [publica(dict(e)) for e in _tabla(T_CUENTAS).list_entities() if e.get("PartitionKey") == PK]
    return sorted(filas, key=lambda c: (c["rol"] != permisos.DIRECCION, c["usuario"]))


def eventos(limite: int = 100) -> list[dict]:
    """Los últimos eventos, el más reciente primero."""
    salida = []
    for e in _tabla(T_EVENTOS).list_entities():
        salida.append({"fecha": e.get("fecha") or "", "actor": e.get("actor") or "", "accion": e.get("accion") or "", "cuenta": e.get("cuenta") or "",
                       "detalle": e.get("detalle") or "", "_k": e["RowKey"]})
        if len(salida) >= limite * 3:   # la clave de fila va invertida: llegan ya de más nuevo a más antiguo
            break
    salida.sort(key=lambda e: e["_k"])
    return [{k: v for k, v in e.items() if k != "_k"} for e in salida[:limite]]


def registrar_evento(actor: str, accion: str, cuenta: str, detalle: str = "") -> None:
    """Auditoría. Nunca debe romper la operación que la origina."""
    try:
        t = time.time()
        _tabla(T_EVENTOS).create_entity({
            "PartitionKey": PK_EVENTO, "RowKey": f"{9999999999999 - int(t * 1000):013d}-{uuid.uuid4().hex[:8]}", "fecha": _ahora(t),
            "actor": (actor or "")[:40], "accion": accion, "cuenta": (cuenta or "")[:40], "detalle": " ".join((detalle or "").split())[:200]})
    except Exception as e:
        log.error("evento_no_registrado tipo=%s accion=%s", type(e).__name__, accion)


# ---- contraseñas -------------------------------------------------------------------------------------------------------------------

def hash_clave(clave: str) -> str:
    return _hasher.hash(clave)


def clave_correcta(huella: str, clave: str) -> bool:
    try:
        return _hasher.verify(huella, clave)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validar_clave(clave: str, usuario: str = "", nombre: str = "") -> None:
    """Política: al menos 12 caracteres, como máximo 128, y que no sea el usuario ni el nombre."""
    if len(clave or "") < CLAVE_MIN:
        raise ErrorCuenta("clave_corta")
    if len(clave) > CLAVE_MAX:
        raise ErrorCuenta("clave_larga")
    bajas = clave.strip().lower()
    if bajas in (normalizar(usuario), (nombre or "").strip().lower()) or not clave.strip() or len(set(clave)) < 4:
        raise ErrorCuenta("clave_obvia")


def _version_nueva() -> int:
    """Versión de sesión de una cuenta nueva: al azar, para que las cookies de una cuenta eliminada no valgan si se vuelve a crear el usuario."""
    return secrets.randbelow(2**30) + 1


def clave_temporal() -> str:
    return "".join(secrets.choice(_ALFABETO_TEMPORAL) for _ in range(16))


# ---- correo (módulo de otro agente: opcional) -------------------------------------------------------------------------------------

def _enviar(tipo: str, para: str, datos: dict) -> bool:
    """True si el correo salió. Si `correo.py` no existe o falla, False (nunca rompe la operación)."""
    if not para:
        return False
    try:
        from . import correo
        return bool(correo.enviar(tipo, para, datos))
    except ImportError:
        return False
    except Exception as e:
        log.warning("correo_no_enviado tipo=%s error=%s", tipo, type(e).__name__)
        return False


# ---- sembrado ----------------------------------------------------------------------------------------------------------------------

def asegurar_admin() -> bool:
    """Si no hay ninguna cuenta, crea `admin` (Dirección) con la contraseña actual FRONT_CLAVE. Devuelve True si la creó."""
    global _sembrada
    if _sembrada:
        return False
    from azure.core.exceptions import ResourceExistsError
    from . import seguridad
    t = _tabla(T_CUENTAS)
    if next(iter(t.list_entities(results_per_page=1)), None) is not None:
        _sembrada = True
        return False
    clave = seguridad.clave_compartida()
    if not clave:
        log.warning("sin_cuentas_ni_clave: no se creó la cuenta admin (FRONT_CLAVE sin resolver)")
        return False
    ahora = _ahora()
    try:
        t.create_entity({"PartitionKey": PK, "RowKey": "admin", "usuario": "admin", "nombre": "Administración", "correo": "", "rol": permisos.DIRECCION,
                         "hash": hash_clave(clave), "activa": True, "debe_cambiar_clave": False, "creada": ahora, "actualizada": ahora,
                         "ultimo_acceso": "", "intentos_fallidos": 0, "bloqueada_hasta": "", "sesion": _version_nueva()})
    except ResourceExistsError:
        return False
    registrar_evento("sistema", "creada", "admin", "cuenta inicial con rol Dirección")
    _sembrada = True
    _olvidar("admin")
    return True


# ---- acceso ------------------------------------------------------------------------------------------------------------------------

def autenticar(usuario: str, clave: str) -> tuple[str, dict | None]:
    """(«ok», cuenta) o («fallo»|«bloqueada», None). Quien llama muestra siempre el mismo mensaje genérico en los dos últimos casos."""
    asegurar_admin()
    u = normalizar(usuario)
    fila = obtener(u, fresco=True) if _USUARIO.match(u) else None
    ahora = _ahora()
    if fila is None:
        clave_correcta(_DUMMY, clave or "")        # mismo trabajo que con una cuenta real: no se nota si el usuario existe
        return "fallo", None
    if (fila.get("bloqueada_hasta") or "") > ahora:
        clave_correcta(_DUMMY, clave or "")
        return "bloqueada", None
    if not clave_correcta(fila.get("hash") or _DUMMY, clave or ""):
        _fallo_de_clave(fila, "acceso_fallido")
        return "fallo", None
    if not fila.get("activa", True):
        registrar_evento(u, "acceso_fallido", u, "cuenta desactivada")
        return "fallo", None
    cambios = {"intentos_fallidos": 0, "bloqueada_hasta": "", "ultimo_acceso": ahora}
    if _hasher.check_needs_rehash(fila["hash"]):
        cambios["hash"] = hash_clave(clave)
    _actualizar(u, cambios)
    registrar_evento(u, "acceso_ok", u)
    return "ok", {**fila, **cambios}


def _fallo_de_clave(fila: dict, accion: str) -> None:
    u = fila["RowKey"]
    n = int(fila.get("intentos_fallidos") or 0) + 1
    if n >= INTENTOS_MAX:
        _actualizar(u, {"intentos_fallidos": 0, "bloqueada_hasta": _ahora(time.time() + BLOQUEO_S)})
        registrar_evento(u, "bloqueada", u, f"{INTENTOS_MAX} intentos fallidos: bloqueo de {BLOQUEO_S // 60} minutos")
    else:
        _actualizar(u, {"intentos_fallidos": n})
        registrar_evento(u, accion, u, f"intento fallido {n} de {INTENTOS_MAX}")


def _actualizar(usuario: str, cambios: dict) -> None:
    _tabla(T_CUENTAS).update_entity({"PartitionKey": PK, "RowKey": usuario, **cambios}, mode="merge")
    _olvidar(usuario)


def sesion_valida(usuario: str, version: int, rol: str) -> dict | None:
    """La cuenta si la sesión sigue vigente: existe, está activa y no cambió su versión ni su rol."""
    f = obtener(usuario)
    if f is None or not f.get("activa", True) or int(f.get("sesion") or 1) != version or (f.get("rol") or "") != rol:
        return None
    return f


# ---- administración (solo Dirección; lo exige permisos.py en la ruta) ---------------------------------------------------------------------

def _datos(d: dict, con_usuario: bool) -> dict:
    nombre = " ".join(str(d.get("nombre") or "").split())
    correo = str(d.get("correo") or "").strip().lower()
    rol = str(d.get("rol") or "")
    correo_ok = bool(_CORREO.match(correo)) or (not con_usuario and correo == "")   # al editar, una cuenta puede quedar sin correo (p. ej. admin)
    if not (1 <= len(nombre) <= 80) or not correo_ok or len(correo) > 120 or rol not in permisos.ASIGNABLES:
        raise ErrorCuenta("invalido")
    salida = {"nombre": nombre, "correo": correo, "rol": rol}
    if con_usuario:
        u = normalizar(d.get("usuario") or "")
        if not _USUARIO.match(u):
            raise ErrorCuenta("invalido")
        salida["usuario"] = u
    return salida


def _existente(usuario: str) -> dict:
    f = obtener(usuario, fresco=True)
    if f is None:
        raise ErrorCuenta("no_existe")
    return f


def _direcciones_activas(sin: str = "") -> int:
    return sum(1 for e in _tabla(T_CUENTAS).list_entities() if e.get("PartitionKey") == PK and e["RowKey"] != sin
               and e.get("rol") == permisos.DIRECCION and e.get("activa", True))


def crear(actor: str, datos: dict, url: str = "") -> dict:
    """Alta. Devuelve {"usuario", "correo_enviado", "clave"}: `clave` solo viene si el correo no salió (se muestra una vez)."""
    from azure.core.exceptions import ResourceExistsError
    d = _datos(datos, True)
    temporal = clave_temporal()
    ahora = _ahora()
    try:
        _tabla(T_CUENTAS).create_entity({"PartitionKey": PK, "RowKey": d["usuario"], **d, "hash": hash_clave(temporal), "activa": True, "debe_cambiar_clave": True,
                                         "creada": ahora, "actualizada": ahora, "ultimo_acceso": "", "intentos_fallidos": 0, "bloqueada_hasta": "", "sesion": _version_nueva()})
    except ResourceExistsError:
        raise ErrorCuenta("existe") from None
    _olvidar(d["usuario"])
    enviado = _enviar("cuenta_creada", d["correo"], {"usuario": d["usuario"], "nombre": d["nombre"], "rol": permisos.nombre_rol(d["rol"]),
                                                      "clave_temporal": temporal, "url": url})
    registrar_evento(actor, "creada", d["usuario"], f"rol {permisos.nombre_rol(d['rol'])}; " + ("clave temporal enviada por correo y mostrada una vez a quien la creó" if enviado else "correo no enviado: clave temporal mostrada una vez en pantalla"))
    return {"usuario": d["usuario"], "correo_enviado": enviado, "clave": temporal}   # se muestra siempre una vez: un correo mal escrito no deja la cuenta sin entrada


def editar(actor: str, usuario: str, datos: dict, activa: bool | None = None) -> dict:
    f = _existente(usuario)
    u = f["RowKey"]
    d = _datos({**datos, "usuario": u}, False)
    activa = bool(f.get("activa", True)) if activa is None else bool(activa)
    rol_antes, activa_antes = f.get("rol"), bool(f.get("activa", True))
    deja_de_dirigir = rol_antes == permisos.DIRECCION and activa_antes and (d["rol"] != permisos.DIRECCION or not activa)
    if u == normalizar(actor) and not activa:
        raise ErrorCuenta("propia")
    if deja_de_dirigir and _direcciones_activas(sin=u) < 1:
        raise ErrorCuenta("ultima_direccion")
    cambios = {**d, "activa": activa, "actualizada": _ahora()}
    rol_cambia = d["rol"] != rol_antes
    if rol_cambia or (activa_antes and not activa):
        cambios["sesion"] = int(f.get("sesion") or 1) + 1      # las sesiones abiertas dejan de valer
    _actualizar(u, cambios)
    editados = [c for c in ("nombre", "correo") if (f.get(c) or "") != d[c]]
    if editados or (activa and not activa_antes):
        registrar_evento(actor, "editada", u, ", ".join(editados + (["activada"] if activa and not activa_antes else [])))
    if rol_cambia:
        registrar_evento(actor, "rol_cambiado", u, f"{permisos.nombre_rol(rol_antes)} a {permisos.nombre_rol(d['rol'])}")
        _enviar("rol_cambiado", d["correo"], {"usuario": u, "nombre": d["nombre"], "rol": permisos.nombre_rol(d["rol"])})
    if activa_antes and not activa:
        registrar_evento(actor, "desactivada", u)
    return {"usuario": u}


def restablecer(actor: str, usuario: str, url: str = "") -> dict:
    f = _existente(usuario)
    u = f["RowKey"]
    if u == normalizar(actor):
        raise ErrorCuenta("propia")
    temporal = clave_temporal()
    _actualizar(u, {"hash": hash_clave(temporal), "debe_cambiar_clave": True, "sesion": int(f.get("sesion") or 1) + 1, "intentos_fallidos": 0,
                    "bloqueada_hasta": "", "actualizada": _ahora()})
    enviado = _enviar("clave_restablecida", f.get("correo") or "", {"usuario": u, "nombre": f.get("nombre") or u, "clave_temporal": temporal, "url": url})
    registrar_evento(actor, "clave_restablecida", u, "clave temporal enviada por correo y mostrada una vez a quien la restableció" if enviado else "correo no enviado: clave temporal mostrada una vez en pantalla")
    return {"usuario": u, "correo_enviado": enviado, "clave": temporal}


def eliminar(actor: str, usuario: str) -> dict:
    f = _existente(usuario)
    u = f["RowKey"]
    if u == normalizar(actor):
        raise ErrorCuenta("propia")
    if f.get("rol") == permisos.DIRECCION and f.get("activa", True) and _direcciones_activas(sin=u) < 1:
        raise ErrorCuenta("ultima_direccion")
    _tabla(T_CUENTAS).delete_entity(PK, u)
    _olvidar(u)
    registrar_evento(actor, "eliminada", u, f"rol {permisos.nombre_rol(f.get('rol') or '')}")
    _enviar("cuenta_eliminada", f.get("correo") or "", {"usuario": u, "nombre": f.get("nombre") or u})
    return {"usuario": u}


# ---- la propia clave ---------------------------------------------------------------------------------------------------------------

def cambiar_clave(usuario: str, actual: str, nueva: str) -> dict:
    """Cambia la contraseña de quien la usa. Devuelve la fila nueva (con la versión de sesión ya subida) para emitir su cookie."""
    f = _existente(usuario)
    u = f["RowKey"]
    if not clave_correcta(f.get("hash") or _DUMMY, actual or ""):
        _fallo_de_clave(f, "acceso_fallido")
        raise ErrorCuenta("clave_actual")
    validar_clave(nueva, u, f.get("nombre") or "")
    if nueva == actual:
        raise ErrorCuenta("clave_igual")
    cambios = {"hash": hash_clave(nueva), "debe_cambiar_clave": False, "sesion": int(f.get("sesion") or 1) + 1, "intentos_fallidos": 0,
               "bloqueada_hasta": "", "actualizada": _ahora()}
    _actualizar(u, cambios)
    registrar_evento(u, "clave_cambiada", u)
    _enviar("clave_cambiada", f.get("correo") or "", {"usuario": u, "nombre": f.get("nombre") or u})
    return {**f, **cambios}
