"""Telemetría de Kerna AI con lista de atributos permitidos (ver kerna/docs/contratos.md).

Nunca sale texto de denuncias, notas, consultas, prompts ni respuestas: solo identificadores opacos,
conteos, duraciones, códigos y nombres de modelo.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager

ATRIBUTOS_PERMITIDOS = frozenset({
    "id_solicitud", "ref_opaca", "cliente", "etapa", "modo", "recuperacion", "proveedor", "modelo",
    "embedding", "coleccion", "version_corpus", "estado", "motivo", "codigo", "intento", "duracion_ms",
    "tokens_entrada", "tokens_salida", "articulos", "citas_rechazadas", "json_valido", "contingencia",
    "resultado", "casos", "fragmentos", "tipo",
})
MAX_TEXTO = 64

_log = logging.getLogger("kerna.telemetria")
_emisores: list = []  # funciones (clase, nombre, valor, atributos) que reciben cada señal ya filtrada


def filtrar(atributos: dict) -> dict:
    """Deja solo los atributos permitidos, con valores escalares y textos cortos."""
    limpio = {}
    for clave, valor in atributos.items():
        if clave not in ATRIBUTOS_PERMITIDOS or valor is None:
            continue
        if isinstance(valor, bool) or isinstance(valor, (int, float)):
            limpio[clave] = valor
        elif isinstance(valor, str) and len(valor) <= MAX_TEXTO:
            limpio[clave] = valor
    return limpio


def registrar_emisor(emisor) -> None:
    _emisores.append(emisor)


def quitar_emisores() -> None:
    _emisores.clear()


def _emitir(clase: str, nombre: str, valor, atributos: dict) -> None:
    limpio = filtrar(atributos)
    for emisor in list(_emisores):
        try:
            emisor(clase, nombre, valor, limpio)
        except Exception:  # la telemetría nunca interrumpe el servicio
            _log.debug("emisor de telemetría falló", exc_info=True)


def evento(nombre: str, **atributos) -> None:
    _emitir("evento", nombre, None, atributos)


def contador(nombre: str, valor: float = 1, **atributos) -> None:
    _emitir("contador", nombre, valor, atributos)


@contextmanager
def etapa(nombre: str, **atributos):
    """Mide la duración de un bloque y la emite como `duracion_ms`. Los atributos se pueden completar
    dentro del bloque: `with etapa("generacion") as a: a["modelo"] = ...`."""
    inicio = time.monotonic()
    atributos = dict(atributos, etapa=nombre)
    try:
        yield atributos
    finally:
        atributos["duracion_ms"] = round((time.monotonic() - inicio) * 1000)
        _emitir("etapa", nombre, atributos["duracion_ms"], atributos)


def configurar(servicio: str) -> bool:
    """Activa el envío a Application Insights si hay cadena de conexión. Devuelve si quedó activo."""
    if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return False
    from kerna_comun import telemetria_azure  # import diferido: dependencia opcional
    telemetria_azure.activar(servicio)
    return True
