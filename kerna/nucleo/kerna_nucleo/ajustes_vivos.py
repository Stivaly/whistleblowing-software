"""Ajustes del panel que aplica el núcleo, leídos de la tabla `ajustes` (fila kerna/actual) como mucho cada TTL_S.

Aplica: revisor automático de citas (`evaluador`), artículos por caso (`candidatos`) y orden de los modelos (`cadena`).
Sin fila rigen las variables KERNA_*; si la tabla falla se conserva el último valor leído. Nunca lanza ni registra texto.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import time
from typing import Any, Optional

from kerna_comun import ajustes_esquema as esq

from .enrutador import Nivel

log = logging.getLogger("kerna.nucleo")
TTL_S = 20.0
PK, RK, TABLA = "kerna", "actual", "ajustes"


def aplicar_config(cfg, ef: dict, retriever_k: int):
    """Copia de la configuración con el revisor y los artículos por caso de los ajustes (nunca más de lo que se recupera)."""
    return dataclasses.replace(cfg, evaluador=ef["evaluador"], evaluador_candidatos=min(ef["candidatos"], retriever_k))


def aplicar_niveles(niveles: list, cadena: list) -> list:
    """Niveles reordenados según `cadena`: grupos encendidos en su orden, luego los de otros proveedores. El primero
    queda «oficial», los demás «respaldo» (los «local» siguen «local»). Sin resultado, los niveles base."""
    out: list = []
    usados: set = set()
    for m in cadena:
        if not m.get("on"):
            continue
        prov = esq.PROVEEDOR_DE.get(m.get("v"))
        for i, n in enumerate(niveles):
            if n.proveedor == prov and i not in usados:
                usados.add(i)
                out.append(n)
    apagados = {esq.PROVEEDOR_DE.get(m.get("v")) for m in cadena if not m.get("on")}
    conocidos = set(esq.PROVEEDOR_DE.values())
    for i, n in enumerate(niveles):  # proveedores fuera de la cadena guardada (no apagados) van al final
        if i not in usados and n.proveedor not in conocidos and n.proveedor not in apagados:
            out.append(n)
    if not out:
        return list(niveles)
    return [dataclasses.replace(n, modo="oficial" if j == 0 else ("local" if n.modo == "local" else "respaldo")) for j, n in enumerate(out)]


class AjustesVivos:
    def __init__(self, tabla: Optional[Any] = None, ttl_s: float = TTL_S, reloj=time.monotonic):
        self._t, self._ttl, self._reloj = tabla, ttl_s, reloj
        self._valor: Optional[dict] = None
        self._leido_en: Optional[float] = None

    @classmethod
    def desde_config(cls, cfg) -> Optional["AjustesVivos"]:
        import os
        url = os.environ.get("AJUSTES_TABLA_URL") or getattr(cfg, "tablas_url", "")
        if not url:
            return None
        from azure.data.tables import TableClient
        from azure.identity import DefaultAzureCredential
        return cls(TableClient(endpoint=url, table_name=TABLA, credential=DefaultAzureCredential()))

    async def efectivos(self) -> Optional[dict]:
        """{"evaluador", "candidatos", "cadena", "guardado_en"} o None si no hay fila (rigen las variables de entorno)."""
        if self._t is None:
            return None
        ahora = self._reloj()
        if self._leido_en is not None and ahora - self._leido_en < self._ttl:
            return self._valor
        self._leido_en = ahora  # también tras una falla: no se insiste antes del TTL
        try:
            e = await asyncio.to_thread(self._t.get_entity, PK, RK)
        except Exception as exc:
            if type(exc).__name__ == "ResourceNotFoundError":
                self._valor = None
            else:
                log.warning("no se pudieron leer los ajustes: %s", type(exc).__name__)
            return self._valor
        try:
            v = esq.validar(json.loads(e["valores"]))
            self._valor = {"evaluador": v["evaluador"], "candidatos": v["candidatos"], "cadena": v["cadena"],
                           "guardado_en": e.get("actualizado_en")}
        except Exception as exc:
            log.warning("fila de ajustes inválida: %s", type(exc).__name__)
        return self._valor
