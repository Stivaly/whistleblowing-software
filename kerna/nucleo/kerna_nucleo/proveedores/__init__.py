"""Clientes de los servicios externos (cada uno simulable en las pruebas)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ErrorProveedor(Exception):
    """Falla de un proveedor. `reintentable` es True ante 5xx, 429 y silencio (timeout/conexión).
    El mensaje nunca incluye cuerpos de petición ni de respuesta."""

    def __init__(self, proveedor: str, codigo: int | None = None, reintentable: bool = True, detalle: str = ""):
        self.proveedor = proveedor
        self.codigo = codigo
        self.reintentable = reintentable
        super().__init__(f"{proveedor} falló (codigo={codigo}) {detalle}".strip())


def error_http(proveedor: str, codigo: int) -> ErrorProveedor:
    return ErrorProveedor(proveedor, codigo, reintentable=codigo >= 500 or codigo == 429)


@dataclass
class Proveedores:
    """Conjunto inyectable de clientes. `dormir` es la espera asíncrona (se simula en las pruebas)."""
    gemini: Any
    voyage: Any
    qdrant: Any
    local: Any
    dormir: Any = None
    plazo_llamada: Any = None  # corutina(awaitable, segundos); por defecto asyncio.wait_for
