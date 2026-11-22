"""Apoyo de las pruebas del front: tablas de cuentas simuladas y una sesión de Dirección lista para usar.

`H` lleva la cookie de sesión de la cuenta `admin` (Dirección); `csrf()` es el token que corresponde a esa cookie. `conftest.py` instala las
tablas simuladas (con `admin`) antes de cada prueba del front. Para otro rol: `sesion(rol)` crea la cuenta y devuelve (cabeceras, csrf).
"""
import functools
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("FRONT_CLAVE", "clave-de-prueba")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError  # noqa: E402

from app import cuentas, seguridad  # noqa: E402


class TablaFalsa:
    """Lo mínimo de azure.data.tables.TableClient que usan las cuentas."""

    def __init__(self):
        self.f = {}

    def list_entities(self, results_per_page=None, select=None):
        return iter([dict(e) for _, e in sorted(self.f.items())])

    def get_entity(self, pk, rk):
        if (pk, rk) not in self.f:
            raise ResourceNotFoundError("no existe")
        return dict(self.f[(pk, rk)])

    def create_entity(self, e):
        k = (e["PartitionKey"], e["RowKey"])
        if k in self.f:
            raise ResourceExistsError("ya existe")
        self.f[k] = dict(e)

    def upsert_entity(self, e, mode="merge"):
        self.f[(e["PartitionKey"], e["RowKey"])] = dict(e)

    def update_entity(self, e, mode="merge"):
        k = (e["PartitionKey"], e["RowKey"])
        if k not in self.f:
            raise ResourceNotFoundError("no existe")
        if mode == "replace":
            self.f[k] = dict(e)
        else:
            self.f[k].update(e)

    def delete_entity(self, pk, rk):
        self.f.pop((pk, rk), None)


@functools.lru_cache(maxsize=None)
def _huella(clave: str) -> str:
    return cuentas.hash_clave(clave)


def cuenta(usuario="admin", rol="direccion", clave="clave-de-prueba", **kw):
    return {"PartitionKey": cuentas.PK, "RowKey": usuario, "usuario": usuario, "nombre": kw.pop("nombre", usuario.capitalize()), "correo": kw.pop("correo", f"{usuario}@prueba.cl"),
            "rol": rol, "hash": _huella(clave), "activa": True, "debe_cambiar_clave": False, "creada": "2026-11-01T00:00:00Z", "actualizada": "2026-11-01T00:00:00Z",
            "ultimo_acceso": "", "intentos_fallidos": 0, "bloqueada_hasta": "", "sesion": 1, **kw}


def instalar(monkeypatch, con_admin=True):
    """Tablas simuladas nuevas (con `admin` si se pide). Devuelve {nombre: TablaFalsa}."""
    tablas = {cuentas.T_CUENTAS: TablaFalsa(), cuentas.T_EVENTOS: TablaFalsa()}
    monkeypatch.setattr(cuentas, "_tabla", lambda nombre: tablas[nombre])
    cuentas.olvidar_todo()
    if con_admin:
        f = cuenta()
        tablas[cuentas.T_CUENTAS].f[(f["PartitionKey"], f["RowKey"])] = f
    return tablas


def cabeceras(usuario="admin", version=1, rol="direccion"):
    valor = seguridad.emitir_cookie(usuario, version, rol)
    return {"Cookie": f"{seguridad.COOKIE}={valor}"}, seguridad.token_csrf({seguridad.COOKIE: valor})


_H, _CSRF = cabeceras()
H = _H


def csrf():
    return _CSRF


def sesion(tablas, rol, usuario=None, **kw):
    """Crea una cuenta con ese rol y devuelve (cabeceras, csrf) de su sesión."""
    usuario = usuario or rol
    f = cuenta(usuario, rol, **kw)
    tablas[cuentas.T_CUENTAS].f[(f["PartitionKey"], f["RowKey"])] = f
    cuentas.olvidar_todo()
    return cabeceras(usuario, f["sesion"], rol)
