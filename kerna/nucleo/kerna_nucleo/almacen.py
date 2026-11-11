"""Almacén de solicitudes, sugerencias, valoraciones y clasificaciones.

Interfaz asíncrona con dos implementaciones: AlmacenMemoria (pruebas y desarrollo) y AlmacenTablas (Azure Table
Storage). No se guarda el texto del caso. `crear_solicitud` es atómica por (cliente, ref_opaca).
"""
from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any

_JSON = "__json__"


class Almacen(ABC):
    @abstractmethod
    async def crear_solicitud(self, solicitud: dict) -> tuple[dict, bool]:
        """Inserta si no existe (cliente, ref_opaca). Devuelve (solicitud vigente, creada)."""

    @abstractmethod
    async def obtener_solicitud(self, cliente: str, ref_opaca: str) -> dict | None: ...

    @abstractmethod
    async def actualizar_solicitud(self, cliente: str, ref_opaca: str, campos: dict, solo_si_pendiente: bool = False) -> bool: ...

    @abstractmethod
    async def guardar_articulos(self, id_solicitud: str, articulos: list[dict]) -> None: ...

    @abstractmethod
    async def listar_articulos(self, id_solicitud: str) -> list[dict]: ...

    @abstractmethod
    async def guardar_valoracion(self, id_solicitud: str, id_nota: str, datos: dict) -> bool:
        """True si se creó; False si `id_nota` ya existía."""

    @abstractmethod
    async def guardar_clasificacion(self, id_solicitud: str, id_nota: str, datos: dict) -> tuple[dict, bool]:
        """Devuelve (registro vigente, creada)."""


class AlmacenMemoria(Almacen):
    def __init__(self):
        self.solicitudes: dict[tuple, dict] = {}
        self.articulos: dict[str, list] = {}
        self.valoraciones: dict[tuple, dict] = {}
        self.clasificaciones: dict[tuple, dict] = {}

    async def crear_solicitud(self, solicitud):
        k = (solicitud["cliente"], solicitud["ref_opaca"])
        if k in self.solicitudes:
            return dict(self.solicitudes[k]), False
        self.solicitudes[k] = dict(solicitud)
        return dict(solicitud), True

    async def obtener_solicitud(self, cliente, ref_opaca):
        s = self.solicitudes.get((cliente, ref_opaca))
        return dict(s) if s else None

    async def actualizar_solicitud(self, cliente, ref_opaca, campos, solo_si_pendiente=False):
        s = self.solicitudes.get((cliente, ref_opaca))
        if s is None or (solo_si_pendiente and s.get("estado") != "pendiente"):
            return False
        s.update(campos)
        return True

    async def guardar_articulos(self, id_solicitud, articulos):
        self.articulos[id_solicitud] = [dict(a) for a in articulos]

    async def listar_articulos(self, id_solicitud):
        return [dict(a) for a in self.articulos.get(id_solicitud, [])]

    async def guardar_valoracion(self, id_solicitud, id_nota, datos):
        k = (id_solicitud, id_nota)
        if k in self.valoraciones:
            return False
        self.valoraciones[k] = dict(datos)
        return True

    async def guardar_clasificacion(self, id_solicitud, id_nota, datos):
        k = (id_solicitud, id_nota)
        if k in self.clasificaciones:
            return dict(self.clasificaciones[k]), False
        self.clasificaciones[k] = dict(datos)
        return dict(datos), True


def _a_plano(d: dict) -> dict:
    return {k: (v if isinstance(v, (str, int, float, bool)) else _JSON + json.dumps(v)) for k, v in d.items()
            if v is not None}


def _de_plano(e: Any) -> dict:
    out = {}
    for k, v in dict(e).items():
        if k in ("PartitionKey", "RowKey") or k.startswith("odata"):
            continue
        out[k] = json.loads(v[len(_JSON):]) if isinstance(v, str) and v.startswith(_JSON) else v
    return out


class AlmacenTablas(Almacen):
    """Azure Table Storage con el SDK síncrono, ejecutado en hilos."""

    T_SOLICITUD, T_ARTICULO, T_VALORACION, T_CLASIFICACION = "solicitud", "sugerenciaarticulo", "valoracion", "clasificacion"

    def __init__(self, url: str = "", conexion: str = "", credencial=None):
        from azure.data.tables import TableServiceClient
        if conexion:
            self._svc = TableServiceClient.from_connection_string(conexion)
        else:
            if credencial is None:
                from azure.identity import DefaultAzureCredential
                credencial = DefaultAzureCredential()
            self._svc = TableServiceClient(endpoint=url, credential=credencial)
        self._t = {}
        for n in (self.T_SOLICITUD, self.T_ARTICULO, self.T_VALORACION, self.T_CLASIFICACION):
            self._t[n] = self._svc.create_table_if_not_exists(n)

    @staticmethod
    def _rk(valor: str) -> str:  # las claves de Tables no admiten / \ # ?
        return "".join(c if c not in "/\\#?" and ord(c) >= 32 else "_" for c in valor)

    async def _hilo(self, f, *a, **kw):
        return await asyncio.to_thread(f, *a, **kw)

    def _insertar(self, tabla, pk, rk, datos) -> bool:
        from azure.core.exceptions import ResourceExistsError
        try:
            self._t[tabla].create_entity({"PartitionKey": self._rk(pk), "RowKey": self._rk(rk), **_a_plano(datos)})
            return True
        except ResourceExistsError:
            return False

    def _leer(self, tabla, pk, rk):
        from azure.core.exceptions import ResourceNotFoundError
        try:
            return _de_plano(self._t[tabla].get_entity(self._rk(pk), self._rk(rk)))
        except ResourceNotFoundError:
            return None

    async def crear_solicitud(self, solicitud):
        creada = await self._hilo(self._insertar, self.T_SOLICITUD, solicitud["cliente"], solicitud["ref_opaca"], solicitud)
        if creada:
            return dict(solicitud), True
        return await self.obtener_solicitud(solicitud["cliente"], solicitud["ref_opaca"]), False

    async def obtener_solicitud(self, cliente, ref_opaca):
        return await self._hilo(self._leer, self.T_SOLICITUD, cliente, ref_opaca)

    def _actualizar(self, cliente, ref, campos, solo_si_pendiente):
        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceModifiedError, ResourceNotFoundError
        from azure.data.tables import UpdateMode
        try:
            e = self._t[self.T_SOLICITUD].get_entity(self._rk(cliente), self._rk(ref))
        except ResourceNotFoundError:
            return False
        if solo_si_pendiente and e.get("estado") != "pendiente":
            return False
        try:
            self._t[self.T_SOLICITUD].update_entity(
                {"PartitionKey": e["PartitionKey"], "RowKey": e["RowKey"], **_a_plano(campos)}, mode=UpdateMode.MERGE,
                etag=e.metadata["etag"], match_condition=MatchConditions.IfNotModified)
            return True
        except ResourceModifiedError:
            return False

    async def actualizar_solicitud(self, cliente, ref_opaca, campos, solo_si_pendiente=False):
        return await self._hilo(self._actualizar, cliente, ref_opaca, campos, solo_si_pendiente)

    def _guardar_articulos(self, id_solicitud, articulos):
        from azure.data.tables import UpdateMode
        for a in articulos:
            self._t[self.T_ARTICULO].upsert_entity(
                {"PartitionKey": self._rk(id_solicitud), "RowKey": self._rk(a["id_sugerencia"]), **_a_plano(a)},
                mode=UpdateMode.REPLACE)

    async def guardar_articulos(self, id_solicitud, articulos):
        await self._hilo(self._guardar_articulos, id_solicitud, articulos)

    def _listar(self, id_solicitud):
        filas = self._t[self.T_ARTICULO].query_entities(f"PartitionKey eq '{self._rk(id_solicitud)}'")
        return sorted((_de_plano(f) for f in filas), key=lambda a: -float(a.get("confianza", 0)))

    async def listar_articulos(self, id_solicitud):
        return await self._hilo(self._listar, id_solicitud)

    async def guardar_valoracion(self, id_solicitud, id_nota, datos):
        return await self._hilo(self._insertar, self.T_VALORACION, id_solicitud, id_nota, datos)

    async def guardar_clasificacion(self, id_solicitud, id_nota, datos):
        creada = await self._hilo(self._insertar, self.T_CLASIFICACION, id_solicitud, id_nota, datos)
        if creada:
            return dict(datos), True
        return await self._hilo(self._leer, self.T_CLASIFICACION, id_solicitud, id_nota), False


def crear_almacen(config) -> Almacen:
    if config.almacen == "tablas":
        return AlmacenTablas(config.tablas_url, config.tablas_conexion)
    return AlmacenMemoria()
