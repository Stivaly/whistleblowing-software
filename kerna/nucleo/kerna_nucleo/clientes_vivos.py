"""Clientes que el panel administra, leídos de la tabla `clientes` como mucho cada TTL_S.

Suma a `KERNA_CLIENTES` los clientes de la tabla que traen `secreto_sha256` y están activos, y quita los que figuran
dados de baja. Si la tabla falla se conserva lo último leído (o solo `KERNA_CLIENTES` si nunca se leyó). Nunca lanza
ni registra secretos.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

from kerna_comun import clientes_esquema as esq

log = logging.getLogger("kerna.nucleo")
TTL_S = 20.0


class ClientesVivos:
    def __init__(self, tabla: Optional[Any] = None, ttl_s: float = TTL_S, reloj=time.monotonic):
        self._t, self._ttl, self._reloj = tabla, ttl_s, reloj
        self._filas: list = []
        self._leido_en: Optional[float] = None
        self._cerrojo = threading.Lock()

    @classmethod
    def desde_config(cls, cfg) -> Optional["ClientesVivos"]:
        import os
        url = os.environ.get("CLIENTES_TABLA_URL") or getattr(cfg, "tablas_url", "")
        if not url:
            return None
        from azure.data.tables import TableClient
        from azure.identity import DefaultAzureCredential
        return cls(TableClient(endpoint=url, table_name=esq.TABLA, credential=DefaultAzureCredential()))

    def _refrescar(self) -> None:
        with self._cerrojo:
            ahora = self._reloj()
            if self._leido_en is not None and ahora - self._leido_en < self._ttl:
                return
            self._leido_en = ahora  # también tras una falla: no se insiste antes del TTL
            try:
                self._filas = [dict(e) for e in self._t.query_entities(f"RowKey eq '{esq.RK}'")]
            except Exception as exc:
                log.warning("clientes_no_leidos %s", type(exc).__name__)

    def aplicar(self, base: dict) -> dict:
        """`base` (KERNA_CLIENTES) más los clientes activos de la tabla, sin los dados de baja."""
        if self._t is None:
            return base
        self._refrescar()
        out = dict(base)
        for e in self._filas:
            cid = str(e.get("PartitionKey") or "")
            if e.get("estado") not in (None, "activo"):
                out.pop(cid, None)
            elif e.get("secreto_sha256"):
                out[cid] = {"secreto_sha256": str(e["secreto_sha256"]), "cliente": str(e.get("cliente") or cid)}
        return out
