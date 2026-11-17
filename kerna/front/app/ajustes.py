"""Ajustes de Kerna (vista del panel): definición de los controles, valores recomendados y persistencia.

Los valores se guardan en la tabla `ajustes` (Azure Table Storage del núcleo): una sola fila, PartitionKey "kerna" y RowKey
"actual", con los valores en JSON y la fecha. Solo se escribe desde una sesión del panel con token CSRF. Valores y rangos viven en kerna_comun/ajustes_esquema.py. Los consumen el conector (cada pasada), el núcleo (cada 20 s) y el panel.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from kerna_comun import ajustes_esquema as esq

TABLA, PK, RK = "ajustes", "kerna", "actual"
CADENA = tuple(esq.PROVEEDOR_DE)
MODELOS = {"azure": ("Azure OpenAI (gpt-5-nano)", ""), "gemini": ("Google Gemini", "")}
EQUIPOS = tuple((k, e["etiqueta"]) for k, e in esq.EQUIPOS.items())
APLICA_YA = tuple(esq.DEFECTOS)  # los 11 ajustes tienen consumidor: conector, núcleo o panel
RECOMENDADO = esq.DEFECTOS
validar = esq.validar


def _seg(v):
    return v // 3600 if v >= 3600 and v % 3600 == 0 else None


def _fh(valores):  # texto de opciones en segundos/minutos/horas
    return [{"v": v, "t": f"{v // 3600} h" if v >= 3600 else f"{v // 60} min" if v >= 60 else f"{v} s"} for v in valores]


GRUPOS = [
    {"id": "proc", "t": "Procesamiento", "i": "workflow", "items": [
        {"k": "envios", "t": "rg", "l": "Casos por ronda", "d": "Cuántas denuncias se envían juntas a Kerna.", **esq.RANGOS["envios"], "u": ("caso", "casos")},
        {"k": "reintentos", "t": "rg", "l": "Reintentos automáticos", "d": "Veces que se vuelve a probar un caso que falló.", **esq.RANGOS["reintentos"], "u": ("vez", "veces"), "cero": "No reintentar"},
        {"k": "espera", "t": "sg", "l": "Esperar entre reintentos", "d": "Tiempo antes de volver a intentar.", "o": [{"v": v, "t": f"{v} h"} for v in esq.OPCIONES["espera"]]},
        {"k": "revision", "t": "sg", "l": "Revisar Veridy cada", "d": "Frecuencia con que el conector mira Veridy.", "o": _fh(esq.OPCIONES["revision"])},
        {"k": "reprocesar", "t": "sw", "l": "Reintentar los de revisión manual", "d": "Una vez, al guardar. Úsalo tras arreglar una falla."}]},
    {"id": "ia", "t": "Inteligencia artificial", "i": "sparkles", "items": [
        {"k": "evaluador", "t": "sw", "l": "Revisor automático de citas", "d": "Comprueba que las citas respalden cada artículo."},
        {"k": "candidatos", "t": "rg", "l": "Artículos por caso", "d": "Por cada caso.", **esq.RANGOS["candidatos"], "u": ("artículo", "artículos"), "dep": "evaluador"},
        {"k": "cadena", "t": "cd", "l": "Orden de los modelos", "d": "Cuál se usa primero y cuáles respaldan."}]},
    {"id": "comp", "t": "Compartir", "i": "users", "items": [
        {"k": "compartir", "t": "ch", "l": "Compartir con", "d": "Equipos que reciben el caso con la sugerencia.", "o": [{"v": v, "t": t} for v, t in EQUIPOS]}]},
    {"id": "plazos", "t": "Plazos", "i": "timer", "items": [
        {"k": "maxresp", "t": "rg", "l": "Meta de respuesta", "d": "Más allá de esto, un caso se marca como lento.", **esq.RANGOS["maxresp"], "u": ("segundo", "segundos")},
        {"k": "alerta", "t": "sg", "l": "Avisar sin sugerencia tras", "d": "Se destaca en el panel.", "o": [{"v": v, "t": f"{v} h"} for v in esq.OPCIONES["alerta"]]}]},
]
for _g in GRUPOS:
    for _it in _g["items"]:
        _it["ya"] = _it["k"] in APLICA_YA
_ITEMS = {it["k"]: it for g in GRUPOS for it in g["items"]}


def _tabla():
    from azure.data.tables import TableClient
    from azure.identity import DefaultAzureCredential
    url = os.environ.get("AJUSTES_TABLA_URL") or os.environ["NEGOCIO_TABLA_URL"]
    return TableClient(endpoint=url, table_name=TABLA, credential=DefaultAzureCredential())


def cargar(tabla=None) -> dict:
    """{"valores", "guardado_en"}: lo guardado o, si no hay nada, los valores recomendados (guardado_en None)."""
    from azure.core.exceptions import ResourceNotFoundError
    t = tabla or _tabla()
    try:
        e = t.get_entity(PK, RK)
    except ResourceNotFoundError:
        return {"valores": json.loads(json.dumps(RECOMENDADO)), "guardado_en": None}
    try:
        return {"valores": validar(json.loads(e.get("valores") or "{}")), "guardado_en": e.get("actualizado_en")}
    except (ValueError, TypeError):
        return {"valores": json.loads(json.dumps(RECOMENDADO)), "guardado_en": None}


def guardar(valores: dict, tabla=None, ahora=None) -> dict:
    limpio = validar(valores)
    marca = (ahora or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tabla or _tabla()).upsert_entity({"PartitionKey": PK, "RowKey": RK, "valores": json.dumps(limpio, ensure_ascii=False), "actualizado_en": marca}, mode="replace")
    return {"valores": limpio, "guardado_en": marca}


def meta_respuesta_s() -> int:
    """Meta de respuesta guardada (segundos) para el Resumen; ante cualquier error, la del defecto."""
    try:
        from . import cache
        return int(cache.obtener(("ajustes",), cargar, 15, vida_max=86400)["valores"]["maxresp"])
    except Exception:
        return esq.DEFECTOS["maxresp"]
