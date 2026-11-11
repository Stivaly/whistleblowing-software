"""Configuración del núcleo desde variables de entorno (ver kerna/docs/contratos.md)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

CADENA_POR_DEFECTO = [
    {"modo": "oficial", "proveedor": "gemini", "modelo": "gemini-3.8-flash", "esquema": True, "sistema": True},
    {"modo": "respaldo", "proveedor": "gemini", "modelo": "gemini-3.5-flash-lite", "esquema": True, "sistema": True},
    {"modo": "local", "proveedor": "gemini", "modelo": "gemma-4-31b-it", "esquema": True, "sistema": True},
]


@dataclass
class Config:
    clientes: dict = field(default_factory=dict)  # {client_id: {"secreto_sha256", "cliente"}}
    jwt_secreto: str = ""
    gemini_api_key: str = ""
    voyage_api_key: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    coleccion: str = "normativa_cl"
    embedding: str = "voyage-4-large"
    dims: int = 1024
    local_url: str = ""
    local_token: str = ""
    top_k: int = 8
    umbral_similitud: float = 0.0
    cadena: list = field(default_factory=lambda: [dict(n) for n in CADENA_POR_DEFECTO])
    modelo_clasificador: str = "gemini-3.5-flash-lite"
    almacen: str = "memoria"
    tablas_url: str = ""
    tablas_conexion: str = ""
    plazo_global_s: float = 240.0
    corte_llamada_s: float = 30.0
    esperas_s: tuple = (1.0, 2.0, 4.0)
    max_texto: int = 60000
    max_articulos: int = 5

    @classmethod
    def desde_entorno(cls, env=None) -> "Config":
        e = os.environ if env is None else env
        c = cls()
        c.clientes = json.loads(e.get("KERNA_CLIENTES") or "{}")
        c.jwt_secreto = e.get("KERNA_JWT_SECRETO", "")
        c.gemini_api_key = e.get("GEMINI_API_KEY", "")
        c.voyage_api_key = e.get("VOYAGE_API_KEY", "")
        c.qdrant_url = e.get("QDRANT_URL", "")
        c.qdrant_api_key = e.get("QDRANT_API_KEY", "")
        c.coleccion = e.get("KERNA_COLECCION", c.coleccion)
        c.embedding = e.get("KERNA_EMBEDDING", c.embedding)
        c.dims = int(e.get("KERNA_DIMS", c.dims))
        c.local_url = e.get("KERNA_LOCAL_URL", "")
        c.local_token = e.get("KERNA_LOCAL_TOKEN", "")
        c.top_k = int(e.get("KERNA_TOP_K", c.top_k))
        c.umbral_similitud = float(e.get("KERNA_UMBRAL_SIMILITUD", c.umbral_similitud))
        if e.get("KERNA_CADENA"):
            c.cadena = json.loads(e["KERNA_CADENA"])
        c.almacen = e.get("KERNA_ALMACEN", c.almacen)
        c.tablas_url = e.get("KERNA_TABLAS_URL", "")
        c.tablas_conexion = e.get("KERNA_TABLAS_CONEXION", "")
        return c
