"""Clientes de Kerna: reglas compartidas por el panel (que los administra) y el núcleo (que los autentica).

Un cliente es una fila de la tabla `clientes` (Azure Table Storage del núcleo): PartitionKey = identificador del cliente,
RowKey = "perfil". Estados: `activo`; `baja` (baja suave: sin acceso, Kerna conserva toda su información y puede reactivarlo);
`anonimizado` (borrado por ley: su identificador y nombre pasaron a ser un uuid sustituto, sin vuelta atrás; los datos de
ejecución se conservan bajo ese uuid). Si la fila trae `secreto_sha256`, ese cliente entra al núcleo con ese identificador y su clave
(OAuth client credentials); la clave en claro solo se muestra una vez al crearlo y nunca se guarda. Un cliente cuya fila
no está activa no puede entrar, aunque esté en `KERNA_CLIENTES`.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import uuid

TABLA, RK = "clientes", "perfil"
PLANES = ("basico", "pro", "plataforma")
ACTIVO, BAJA, ANONIMIZADO = "activo", "baja", "anonimizado"
# Clientes que el panel no puede quitar: son los que sostienen la plataforma real (el conector de Veridy usa esa cuenta).
PROTEGIDOS = ("veridy-dev",)
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")
MAX_NOMBRE, MAX_RUBRO, MAX_CUOTA = 80, 60, 5000


def validar_id(valor) -> str:
    """Identificador en minúsculas, dígitos y guiones (3 a 40, sin guion al borde). Lanza ValueError si no sirve."""
    v = str(valor or "").strip().lower()
    if not _ID.match(v):
        raise ValueError("id")
    return v


def validar_nuevo(datos: dict) -> dict:
    """Perfil limpio de un cliente nuevo: id, nombre, rubro, plan_tipo y plan_denuncias_mes. Lanza ValueError si algo no sirve."""
    if not isinstance(datos, dict):
        raise ValueError("datos")
    nombre = " ".join(str(datos.get("nombre") or "").split())
    rubro = " ".join(str(datos.get("rubro") or "").split())
    if not nombre or len(nombre) > MAX_NOMBRE or len(rubro) > MAX_RUBRO:
        raise ValueError("nombre")
    plan = str(datos.get("plan_tipo") or "")
    if plan not in PLANES:
        raise ValueError("plan")
    try:
        cuota = int(datos.get("plan_denuncias_mes"))
    except (TypeError, ValueError):
        raise ValueError("cuota") from None
    if not 1 <= cuota <= MAX_CUOTA:
        raise ValueError("cuota")
    return {"id": validar_id(datos.get("id")), "nombre": nombre, "rubro": rubro, "plan_tipo": plan, "plan_denuncias_mes": cuota}


def nuevo_secreto() -> str:
    return "kc_" + secrets.token_urlsafe(32)


def hash_secreto(secreto: str) -> str:
    return hashlib.sha256((secreto or "").encode()).hexdigest()


def identidad_sustituta() -> str:
    """Uuid que reemplaza el identificador y el nombre de un cliente borrado por ley."""
    return str(uuid.uuid4())
