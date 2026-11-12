"""Solicitud de reintento manual hecha desde el panel de Kerna.

El panel escribe una fila (`reintentosmanuales`, PartitionKey "kerna", RowKey "solicitud") con estado "solicitado".
Al comienzo de cada pasada el conector la lee; si está pedida, esa pasada reintenta sin esperas ni tope de envíos y la
fila queda en "atendido" con la cantidad de casos reintentados. Sin REINTENTOS_TABLA_URL no hace nada. Una falla al
leer o escribir la tabla nunca detiene la pasada. La fila no contiene textos de denuncias ni identificadores de casos.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger("kerna.conector")
PK, RK = "kerna", "solicitud"


class SolicitudReintento:
    def __init__(self, tabla: Optional[Any] = None):
        self._t = tabla

    @classmethod
    def desde_entorno(cls) -> "SolicitudReintento":
        url = os.environ.get("REINTENTOS_TABLA_URL", "")
        if not url:
            return cls(None)
        from azure.data.tables import TableClient  # import diferido: solo hace falta con la tabla configurada
        from azure.identity import DefaultAzureCredential
        return cls(TableClient(endpoint=url, table_name=os.environ.get("REINTENTOS_TABLA", "reintentosmanuales"),
                               credential=DefaultAzureCredential()))

    def pedida(self) -> bool:
        if self._t is None:
            return False
        try:
            return self._t.get_entity(PK, RK).get("estado") == "solicitado"
        except Exception as exc:  # sin fila (404) o tabla inaccesible: no hay solicitud
            if type(exc).__name__ != "ResourceNotFoundError":
                log.warning("no se pudo leer la solicitud de reintento: %s", type(exc).__name__)
            return False

    def atender(self, reintentados: int) -> None:
        if self._t is None:
            return
        try:
            self._t.upsert_entity({"PartitionKey": PK, "RowKey": RK, "estado": "atendido", "reintentados": int(reintentados),
                                   "atendido_en": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}, mode="merge")
        except Exception as exc:
            log.warning("no se pudo marcar atendida la solicitud: %s", type(exc).__name__)
