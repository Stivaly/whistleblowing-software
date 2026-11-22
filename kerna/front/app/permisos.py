"""Roles y permisos del panel de Kerna: una sola tabla que el servidor aplica a TODAS las rutas /panel y /api (el menú solo la refleja).

Cada rol dice, por sección, si puede «ver» (GET) o «editar» (POST y demás). Lo que no figura, no se puede. Una ruta que no está en RUTAS
no se atiende (404 con sesión): agregar una ruta nueva exige darle sección aquí, y una prueba lo comprueba.
"""
from __future__ import annotations

import re

VER, EDITAR = "ver", "editar"

# Secciones del panel (clave -> nombre que ve la persona).
SECCIONES = {"resumen": "Resumen", "informe": "Informe", "negocio": "Negocio", "clientes": "Administrar clientes", "ajustes": "Ajustes",
             "cuentas": "Cuentas", "demo": "Demo"}

# Roles asignables a una cuenta: clave -> (nombre, frase de qué hace).
ROLES = {
    "direccion": ("Dirección", "Todo el panel, con las cuentas"),
    "operacion": ("Operación de IA", "Resumen, informe y ajustes"),
    "comercial": ("Comercial", "Resumen, informe, negocio y clientes"),
    "evaluacion": ("Evaluación", "Ve todo, no cambia nada"),
    "invitado": ("Invitado", "Solo la demo"),
}
DIRECCION = "direccion"

_TODO = {s: EDITAR for s in SECCIONES}
MATRIZ = {
    "direccion": dict(_TODO),
    "operacion": {"resumen": EDITAR, "informe": EDITAR, "ajustes": EDITAR, "demo": EDITAR},
    "comercial": {"resumen": EDITAR, "informe": EDITAR, "negocio": EDITAR, "clientes": EDITAR, "demo": EDITAR},
    # La Demo no cambia nada del sistema (no guarda el texto): Evaluación puede probarla aunque no pueda modificar el resto.
    "evaluacion": {**{s: VER for s in SECCIONES}, "demo": EDITAR},
    "invitado": {"demo": EDITAR},
    # No es un rol de persona: la clave compartida X-Clave de los scripts que consultan /api/*. Solo lectura.
    "servicio": {"resumen": VER, "negocio": VER},
}
ASIGNABLES = tuple(ROLES)

# (patrón de la ruta, sección). La primera que coincide manda. «propia» = cualquier persona con sesión (su cuenta, salir).
RUTAS = [
    (re.compile(r"^/panel/?$"), "resumen"),
    (re.compile(r"^/panel/reintentar/estado$"), "resumen"),       # lo consulta el Resumen cada pocos segundos
    (re.compile(r"^/panel/reintentar$"), "ajustes"),
    (re.compile(r"^/panel/informe(/.*)?$"), "informe"),
    (re.compile(r"^/panel/negocio$"), "negocio"),
    (re.compile(r"^/panel/clientes(/.*)?$"), "clientes"),
    (re.compile(r"^/panel/ajustes$"), "ajustes"),
    (re.compile(r"^/panel/cuentas(/.*)?$"), "cuentas"),
    (re.compile(r"^/panel/demo(/.*)?$"), "demo"),
    (re.compile(r"^/api/(metricas|proveedores)$"), "resumen"),
    (re.compile(r"^/api/negocio$"), "negocio"),
    (re.compile(r"^/cuenta(/clave)?$"), "propia"),
]


def seccion_de(ruta: str) -> str | None:
    for patron, seccion in RUTAS:
        if patron.match(ruta):
            return seccion
    return None


def protegida(ruta: str) -> bool:
    return ruta.startswith(("/panel", "/api/", "/cuenta"))


def nivel(rol: str, seccion: str) -> str | None:
    """«editar», «ver» o None."""
    if seccion == "propia":
        return EDITAR
    return MATRIZ.get(rol, {}).get(seccion)


def requerido(metodo: str) -> str:
    return VER if metodo.upper() in ("GET", "HEAD", "OPTIONS") else EDITAR


def permite(rol: str, seccion: str, accion: str = VER) -> bool:
    n = nivel(rol, seccion)
    return n == EDITAR or (n == VER and accion == VER)


def puede_ver(rol: str, seccion: str) -> bool:
    return permite(rol, seccion, VER)


def puede_editar(rol: str, seccion: str) -> bool:
    return permite(rol, seccion, EDITAR)


def nombre_rol(rol: str) -> str:
    return ROLES.get(rol, (rol,))[0]


def menu(rol: str) -> dict[str, str]:
    """Sección -> «ver»/«editar» de lo que el rol puede abrir (para el menú)."""
    return {s: n for s, n in MATRIZ.get(rol, {}).items() if s in SECCIONES}


INICIO = {"resumen": "/panel", "informe": "/panel/informe", "negocio": "/panel/negocio", "clientes": "/panel/clientes", "ajustes": "/panel/ajustes",
          "cuentas": "/panel/cuentas", "demo": "/panel/demo"}


def inicio(rol: str) -> str:
    """Primera página del panel que el rol puede abrir (a donde lo lleva «Entrar»)."""
    return next((INICIO[s] for s in SECCIONES if puede_ver(rol, s)), "/cuenta")
