"""Pedido de reintento manual y estado en vivo del conector, en la tabla `reintentosmanuales`.

Filas (PartitionKey "kerna"):
- RowKey "solicitud": el panel la escribe con estado "solicitado". El conector la toma al comienzo de una pasada y la
  pasa a "en_curso" (con `inicio`, `corrida` y el progreso, que actualiza en cada pasada). Al terminar queda en
  "atendido" con el resultado. Contrato completo en pendientes/contrato-reintento-conector.md.
- RowKey "conector": estado en vivo (conteos por estado, última pasada, ajustes aplicados); se reescribe en cada pasada.

Sin REINTENTOS_TABLA_URL (o KERNA_TABLAS_URL) no hace nada. Una falla al leer o escribir la tabla nunca detiene la
pasada. Las filas no contienen textos de denuncias ni identificadores de casos.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

log = logging.getLogger("kerna.conector")
PK, RK, RK_VIVO = "kerna", "solicitud", "conector"
DURACION_MAX_S = 7200  # una corrida que no termina en 2 h se cierra con lo que haya


def _iso(t: Optional[float] = None) -> str:
    return datetime.fromtimestamp(time.time() if t is None else t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(iso: Any) -> float:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


@dataclass(frozen=True)
class Corrida:
    id: str          # identifica la corrida en el estado (clave de `objeto_procesado`)
    inicio: float    # epoch


def tabla_desde_entorno(variable: str, nombre_defecto: str, variable_nombre: str = ""):
    url = os.environ.get(variable) or os.environ.get("KERNA_TABLAS_URL", "")
    if not url:
        return None
    from azure.data.tables import TableClient  # import diferido: solo hace falta con la tabla configurada
    from azure.identity import DefaultAzureCredential
    return TableClient(endpoint=url, table_name=os.environ.get(variable_nombre, nombre_defecto) if variable_nombre else nombre_defecto,
                       credential=DefaultAzureCredential())


class SolicitudReintento:
    def __init__(self, tabla: Optional[Any] = None, ahora: Callable[[], float] = time.time):
        self._t, self._ahora = tabla, ahora

    @classmethod
    def desde_entorno(cls) -> "SolicitudReintento":
        return cls(tabla_desde_entorno("REINTENTOS_TABLA_URL", "reintentosmanuales", "REINTENTOS_TABLA"))

    def _leer(self, rk: str = RK) -> Optional[dict]:
        if self._t is None:
            return None
        try:
            return dict(self._t.get_entity(PK, rk))
        except Exception as exc:  # sin fila (404) o tabla inaccesible
            if type(exc).__name__ != "ResourceNotFoundError":
                log.warning("no se pudo leer la tabla de reintentos: %s", type(exc).__name__)
            return None

    def _escribir(self, rk: str, campos: dict) -> None:
        if self._t is None:
            return
        try:
            self._t.upsert_entity({"PartitionKey": PK, "RowKey": rk, **campos}, mode="merge")
        except Exception as exc:
            log.warning("no se pudo escribir la tabla de reintentos: %s", type(exc).__name__)

    # ---- pedido manual --------------------------------------------------------------------------------------
    def pedida(self) -> bool:
        f = self._leer()
        return bool(f) and f.get("estado") in ("solicitado", "en_curso")

    def activa(self) -> Optional[Corrida]:
        """La corrida en curso. Si hay un pedido "solicitado" lo toma (lo pasa a "en_curso"); si ya estaba en curso
        (el conector se reinició) la retoma; si lleva más de DURACION_MAX_S la cierra y devuelve None."""
        f = self._leer()
        if not f:
            return None
        ahora = self._ahora()
        if f.get("estado") == "solicitado":
            c = Corrida("m%d" % int(ahora), ahora)
            self._escribir(RK, {"estado": "en_curso", "corrida": c.id, "inicio": _iso(ahora), "total": 0, "enviados": 0,
                                "resueltos": 0, "con_sugerencia": 0, "sin_sugerencia": 0, "en_vuelo": 0, "eta_s": -1,
                                "actualizado_en": _iso(ahora), "atendido_en": "", "fin": "", "incompleto": False,
                                "origen": f.get("origen") or "panel"})
            return c
        if f.get("estado") == "en_curso" and f.get("corrida"):
            c = Corrida(str(f["corrida"]), _epoch(f.get("inicio")) or ahora)
            if ahora - c.inicio > DURACION_MAX_S:
                self.terminar(c, incompleto=True)
                return None
            return c
        return None

    def solicitar(self, origen: str = "ajustes") -> bool:
        """Crea el pedido desde el propio conector (p. ej. el ajuste «Reintentar los de revisión manual»)."""
        f = self._leer()
        if f and f.get("estado") in ("solicitado", "en_curso"):
            return False
        self._escribir(RK, {"estado": "solicitado", "solicitado_en": _iso(self._ahora()), "origen": origen})
        return True

    def progreso(self, c: Corrida, total: int, enviados: int, resueltos: int, con: int, en_vuelo: int) -> None:
        ahora = self._ahora()
        elapsed = max(1.0, ahora - c.inicio)
        eta = int(elapsed / resueltos * max(0, total - resueltos)) if resueltos else -1
        self._escribir(RK, {"estado": "en_curso", "total": total, "enviados": enviados, "resueltos": resueltos,
                            "con_sugerencia": con, "sin_sugerencia": resueltos - con, "en_vuelo": en_vuelo,
                            "eta_s": eta, "actualizado_en": _iso(ahora)})

    def terminar(self, c: Corrida, total: int = 0, resueltos: int = 0, con: int = 0, incompleto: bool = False) -> None:
        ahora = self._ahora()
        self._escribir(RK, {"estado": "atendido", "atendido_en": _iso(ahora), "fin": _iso(ahora), "total": total,
                            "resueltos": resueltos, "con_sugerencia": con, "sin_sugerencia": resueltos - con,
                            "reintentados": total, "en_vuelo": 0, "eta_s": 0, "incompleto": incompleto,
                            "actualizado_en": _iso(ahora)})

    # ---- estado en vivo ---------------------------------------------------------------------------------------
    def publicar_vivo(self, campos: dict) -> None:
        self._escribir(RK_VIVO, {**campos, "actualizado_en": _iso(self._ahora())})
