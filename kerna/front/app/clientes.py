"""Administración de clientes de Kerna (vista «Clientes» del panel): listar, agregar y quitar.

Todo vive en las tablas del núcleo: `clientes` (perfil de cada cliente), `solicitud` (denuncias procesadas, PartitionKey = cliente)
y `usodiario` (uso por día, PartitionKey = cliente). Dos formas de quitar un cliente:

- Baja suave (la decide Kerna): el cliente queda en estado `baja`, sin acceso al núcleo; toda su información se conserva y se puede
  reactivar.
- Borrado por ley (el cliente lo pide expresamente): su fila sale de `clientes` y todo lo que lo identifica pasa a ser un uuid
  sustituto, de forma automática: la clave de partición y los campos `cliente` e `id_empresa` de `solicitud` y de `usodiario`, y su
  nombre o identificador si aparecen en el texto libre (`observacion`) de las sugerencias, valoraciones y clasificaciones. Los datos
  de ejecución se conservan, pero ya no se pueden asociar con la persona o empresa. La telemetría de Azure (Log Analytics) no se
  puede reescribir: conserva el identificador hasta que vence su retención. Se pierde la clave, el rubro y cualquier vínculo con el nombre
  anterior; el perfil nuevo queda como constancia (fecha, cantidad de filas y la referencia que anote quien lo ejecuta). No se
  puede deshacer. Es reanudable: si se corta, repetirlo reutiliza el mismo uuid.

El panel nunca guarda la clave de un cliente en claro: la muestra una sola vez al crearlo y guarda su sha256.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from kerna_comun import clientes_esquema as esq

import re

T_SOLICITUD, T_USO = "solicitud", "usodiario"
# Tablas con filas del cliente en PartitionKey y los campos de la fila que repiten su identificador.
EJECUCION = ((T_SOLICITUD, ("cliente", "id_empresa")), (T_USO, ()))
# Tablas de lo que Kerna sugirió y lo que el auditor respondió (PartitionKey = id_solicitud, sin cliente): solo su texto libre puede nombrarlo.
RESPUESTAS = ("sugerenciaarticulo", "valoracion", "clasificacion")
TEXTO_LIBRE = ("observacion",)


PLANES_VISTA = (("basico", "Básico"), ("pro", "Pro"), ("plataforma", "Plataforma")) 


class ErrorCliente(Exception):
    """`codigo`: protegido | no_existe | existe | estado | invalido."""

    def __init__(self, codigo: str):
        super().__init__(codigo)
        self.codigo = codigo


def _tabla(nombre):
    from azure.data.tables import TableClient
    from azure.identity import DefaultAzureCredential
    return TableClient(endpoint=os.environ["NEGOCIO_TABLA_URL"], table_name=nombre, credential=DefaultAzureCredential())


def _ahora(ahora=None) -> str:
    return (ahora or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fila(t, cid: str):
    from azure.core.exceptions import ResourceNotFoundError
    try:
        return dict(t.get_entity(cid, esq.RK))
    except ResourceNotFoundError:
        return None


def _vista(e: dict) -> dict:
    estado = e.get("estado") or esq.ACTIVO
    return {"id": e["PartitionKey"], "nombre": e.get("nombre") or e["PartitionKey"], "rubro": e.get("rubro") or "",
            "plan_tipo": e.get("plan_tipo") or "", "cuota": int(e.get("plan_denuncias_mes") or 0), "alta": e.get("fecha_alta") or "",
            "estado": estado, "con_clave": bool(e.get("secreto_sha256")), "protegido": e["PartitionKey"] in esq.PROTEGIDOS,
            "baja_en": e.get("baja_en") or "", "anonimizado_en": e.get("anonimizado_en") or "",
            "filas_anonimizadas": int(e.get("filas_anonimizadas") or 0), "referencia": e.get("referencia") or ""}


def listar(tablas=None) -> dict:
    """{"activos", "bajas", "anonimizados"}: cada uno es una lista de dicts ordenada por nombre (los anonimizados, por fecha)."""
    t = (tablas or _tabla)(esq.TABLA)
    todos = [_vista(dict(e)) for e in t.list_entities() if e.get("RowKey") == esq.RK]
    por = lambda estado: [c for c in todos if c["estado"] == estado]
    return {"activos": sorted(por(esq.ACTIVO), key=lambda c: c["nombre"].lower()),
            "bajas": sorted(por(esq.BAJA), key=lambda c: c["nombre"].lower()),
            "anonimizados": sorted(por(esq.ANONIMIZADO), key=lambda c: c["anonimizado_en"], reverse=True)}


def crear(datos: dict, tablas=None, ahora=None) -> dict:
    """Agrega un cliente activo con credenciales propias. Devuelve {"id", "secreto"}; el secreto no se vuelve a poder ver."""
    try:
        d = esq.validar_nuevo(datos)
    except ValueError:
        raise ErrorCliente("invalido") from None
    t = (tablas or _tabla)(esq.TABLA)
    if _fila(t, d["id"]) is not None:
        raise ErrorCliente("existe")
    secreto = esq.nuevo_secreto()
    t.create_entity({"PartitionKey": d["id"], "RowKey": esq.RK, "nombre": d["nombre"], "rubro": d["rubro"], "plan_tipo": d["plan_tipo"],
                     "plan_denuncias_mes": d["plan_denuncias_mes"], "origen_veridy": False, "fecha_alta": _ahora(ahora)[:10],
                     "estado": esq.ACTIVO, "cliente": d["id"], "secreto_sha256": esq.hash_secreto(secreto)})
    _invalidar()
    return {"id": d["id"], "secreto": secreto}


def _existente(t, cid: str) -> dict:
    try:
        cid = esq.validar_id(cid)
    except ValueError:
        raise ErrorCliente("invalido") from None
    if cid in esq.PROTEGIDOS:
        raise ErrorCliente("protegido")
    e = _fila(t, cid)
    if e is None:
        raise ErrorCliente("no_existe")
    return e


def dar_de_baja(cid: str, tablas=None, ahora=None) -> None:
    """Baja suave: sin acceso al núcleo, información intacta."""
    t = (tablas or _tabla)(esq.TABLA)
    e = _existente(t, cid)
    if (e.get("estado") or esq.ACTIVO) != esq.ACTIVO:
        raise ErrorCliente("estado")
    t.update_entity({"PartitionKey": e["PartitionKey"], "RowKey": esq.RK, "estado": esq.BAJA, "baja_en": _ahora(ahora)}, mode="merge")
    _invalidar()


def reactivar(cid: str, tablas=None) -> None:
    t = (tablas or _tabla)(esq.TABLA)
    e = _existente(t, cid)
    if e.get("estado") != esq.BAJA:
        raise ErrorCliente("estado")
    t.update_entity({"PartitionKey": e["PartitionKey"], "RowKey": esq.RK, "estado": esq.ACTIVO, "baja_en": ""}, mode="merge")
    _invalidar()


def _consulta(cid: str) -> str:
    return f"PartitionKey eq '{cid}'"


def previa(cid: str, tablas=None) -> dict:
    """Cuántas filas se verían afectadas por el borrado por ley (sin tocar nada)."""
    f = tablas or _tabla
    e = _existente(f(esq.TABLA), cid)
    if e.get("estado") == esq.ANONIMIZADO:
        raise ErrorCliente("estado")
    n = {tabla: sum(1 for _ in f(tabla).query_entities(_consulta(e["PartitionKey"]), select=["RowKey"])) for tabla, _ in EJECUCION}
    return {"id": e["PartitionKey"], "nombre": e.get("nombre") or e["PartitionKey"], "solicitudes": n[T_SOLICITUD], "dias_de_uso": n[T_USO]}


def anonimizar(cid: str, referencia: str = "", tablas=None, ahora=None, nuevo_id=None) -> dict:
    """Borrado por ley. Devuelve {"uuid", "filas"}. Reanudable: un intento cortado deja el uuid en la fila original."""
    f = tablas or _tabla
    tc = f(esq.TABLA)
    e = _existente(tc, cid)
    if e.get("estado") == esq.ANONIMIZADO:
        raise ErrorCliente("estado")
    origen = e["PartitionKey"]
    nuevo = e.get("anonimizando_como") or (nuevo_id or esq.identidad_sustituta)()
    if not e.get("anonimizando_como"):
        # Primero se anota el uuid (y se corta el acceso): si algo falla, repetir reutiliza el mismo y no deja dos identidades.
        tc.update_entity({"PartitionKey": origen, "RowKey": esq.RK, "anonimizando_como": nuevo, "estado": esq.BAJA, "baja_en": _ahora(ahora)},
                         mode="merge")
        _invalidar()
    filas, textos, solicitudes, nombres = 0, 0, [], {origen, str(e.get("nombre") or "")}
    for tabla, campos in EJECUCION:
        t = f(tabla)
        for fila in list(t.query_entities(_consulta(origen))):
            if tabla == T_SOLICITUD:
                solicitudes.append(str(fila.get("id_solicitud") or ""))
                nombres.add(str(fila.get("id_empresa") or ""))
            copia = dict(fila)
            copia["PartitionKey"] = nuevo
            for c in campos:
                if c in copia:
                    copia[c] = nuevo
            t.upsert_entity(copia, mode="replace")
            t.delete_entity(fila["PartitionKey"], fila["RowKey"])
            filas += 1
    textos = _limpiar_textos(f, solicitudes, nombres, nuevo)
    perfil = {"PartitionKey": nuevo, "RowKey": esq.RK, "nombre": nuevo, "rubro": "", "plan_tipo": e.get("plan_tipo") or "",
              "plan_denuncias_mes": int(e.get("plan_denuncias_mes") or 0), "origen_veridy": False, "fecha_alta": e.get("fecha_alta") or "",
              "estado": esq.ANONIMIZADO, "anonimizado_en": _ahora(ahora), "filas_anonimizadas": filas, "textos_limpiados": textos,
              "referencia": " ".join(str(referencia or "").split())[:120]}
    tc.upsert_entity(perfil, mode="replace")
    tc.delete_entity(origen, esq.RK)  # último: hasta aquí, repetir el borrado sigue siendo posible
    _invalidar()
    return {"uuid": nuevo, "filas": filas, "textos": textos}


def _limpiar_textos(f, solicitudes: list, nombres: set, nuevo: str) -> int:
    """Cambia por `nuevo` el nombre o identificador del cliente en el texto libre de las respuestas de sus solicitudes. Devuelve cuántas filas cambió."""
    fichas = [re.compile(re.escape(n), re.I) for n in sorted({x.strip() for x in nombres if len(x.strip()) >= 3}, key=len, reverse=True)]
    cambiadas = 0
    for tabla in RESPUESTAS:
        t = f(tabla)
        for sol in filter(None, solicitudes):
            for fila in list(t.query_entities(_consulta(sol))):
                nuevos = {}
                for c in TEXTO_LIBRE:
                    v = fila.get(c)
                    if isinstance(v, str) and v:
                        w = v
                        for rx in fichas:
                            w = rx.sub(nuevo, w)
                        if w != v:
                            nuevos[c] = w
                if nuevos:
                    t.update_entity({"PartitionKey": fila["PartitionKey"], "RowKey": fila["RowKey"], **nuevos}, mode="merge")
                    cambiadas += 1
    return cambiadas


def _invalidar() -> None:
    """Que Negocio vuelva a leer las tablas en vez de servir la lista anterior."""
    try:
        from . import negocio
        negocio._cache.update(t=0.0, v=None)
    except Exception:
        pass
