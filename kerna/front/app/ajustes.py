"""Ajustes de Kerna (vista del panel): definición de los controles, valores recomendados y persistencia.

Los valores se guardan en la tabla `ajustes` (Azure Table Storage del núcleo): una sola fila, PartitionKey "kerna" y RowKey
"actual", con los valores en JSON y la fecha. Solo se escribe desde una sesión del panel con token CSRF. El conector ya lee y aplica APLICA_YA (cada pasada, sin reiniciar; ver pendientes/contrato-reintento-conector.md);
el núcleo y el panel aún no leen el resto, y la vista lo indica en cada fila.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

TABLA, PK, RK = "ajustes", "kerna", "actual"
CADENA = ("azure", "gemini")
MODELOS = {"azure": ("Azure OpenAI (gpt-5-nano)", ""), "gemini": ("Google Gemini", "")}
EQUIPOS = (("analista", "Analistas de cumplimiento"), ("comite", "Comité de ética"), ("auditoria", "Auditoría interna"), ("legal", "Fiscalía legal"))
APLICA_YA = ("envios", "reintentos", "espera", "revision", "reprocesar")  # los lee el conector desplegado; lo demás se guarda pero aún nadie lo aplica
RECOMENDADO = {"envios": 5, "reintentos": 3, "espera": 24, "revision": 30, "reprocesar": False, "evaluador": True, "candidatos": 10,
               "cadena": [{"v": "azure", "on": True}, {"v": "gemini", "on": True}], "compartir": ["analista", "comite"], "maxresp": 15, "alerta": 6}


def _seg(v):
    return v // 3600 if v >= 3600 and v % 3600 == 0 else None


def _fh(valores):  # texto de opciones en segundos/minutos/horas
    return [{"v": v, "t": f"{v // 3600} h" if v >= 3600 else f"{v // 60} min" if v >= 60 else f"{v} s"} for v in valores]


GRUPOS = [
    {"id": "proc", "t": "Procesamiento", "i": "workflow", "items": [
        {"k": "envios", "t": "rg", "l": "Casos por ronda", "d": "Cuántas denuncias se envían juntas a Kerna.", "min": 1, "max": 10, "u": ("caso", "casos")},
        {"k": "reintentos", "t": "rg", "l": "Reintentos automáticos", "d": "Veces que se vuelve a probar un caso que falló.", "min": 0, "max": 5, "u": ("vez", "veces"), "cero": "No reintentar"},
        {"k": "espera", "t": "sg", "l": "Esperar entre reintentos", "d": "Tiempo antes de volver a intentar.", "o": [{"v": v, "t": f"{v} h"} for v in (6, 12, 24, 48)]},
        {"k": "revision", "t": "sg", "l": "Revisar Veridy cada", "d": "Frecuencia con que el conector mira Veridy.", "o": _fh((15, 30, 60, 300))},
        {"k": "reprocesar", "t": "sw", "l": "Reintentar los de revisión manual", "d": "Una vez, al guardar. Úsalo tras arreglar una falla."}]},
    {"id": "ia", "t": "Inteligencia artificial", "i": "sparkles", "items": [
        {"k": "evaluador", "t": "sw", "l": "Revisor automático de citas", "d": "Comprueba que las citas respalden cada artículo."},
        {"k": "candidatos", "t": "rg", "l": "Artículos por caso", "d": "Por cada caso.", "min": 3, "max": 20, "u": ("artículo", "artículos"), "dep": "evaluador"},
        {"k": "cadena", "t": "cd", "l": "Orden de los modelos", "d": "Cuál se usa primero y cuáles respaldan."}]},
    {"id": "comp", "t": "Compartir", "i": "users", "items": [
        {"k": "compartir", "t": "ch", "l": "Compartir con", "d": "Equipos que reciben el caso con la sugerencia.", "o": [{"v": v, "t": t} for v, t in EQUIPOS]}]},
    {"id": "plazos", "t": "Plazos", "i": "timer", "items": [
        {"k": "maxresp", "t": "rg", "l": "Meta de respuesta", "d": "Más allá de esto, un caso se marca como lento.", "min": 5, "max": 60, "step": 5, "u": ("segundo", "segundos")},
        {"k": "alerta", "t": "sg", "l": "Avisar sin sugerencia tras", "d": "Se destaca en el panel.", "o": [{"v": v, "t": f"{v} h"} for v in (1, 6, 24)]}]},
]
for _g in GRUPOS:
    for _it in _g["items"]:
        _it["ya"] = _it["k"] in APLICA_YA
_ITEMS = {it["k"]: it for g in GRUPOS for it in g["items"]}


def validar(v: dict) -> dict:
    """Devuelve los valores limpios (tipos y rangos); lanza ValueError si algo no es válido."""
    out = {}
    for k, it in _ITEMS.items():
        x = v.get(k, RECOMENDADO[k])
        if it["t"] == "sw":
            if not isinstance(x, bool):
                raise ValueError(k)
        elif it["t"] == "rg":
            if isinstance(x, bool) or not isinstance(x, int) or not it["min"] <= x <= it["max"] or (x - it["min"]) % it.get("step", 1):
                raise ValueError(k)
        elif it["t"] == "sg":
            if x not in [o["v"] for o in it["o"]]:
                raise ValueError(k)
        elif it["t"] == "ch":
            if not isinstance(x, list) or any(e not in [o["v"] for o in it["o"]] for e in x) or len(set(x)) != len(x):
                raise ValueError(k)
        elif it["t"] == "cd":
            if (not isinstance(x, list) or sorted(m.get("v") for m in x if isinstance(m, dict)) != sorted(CADENA)
                    or any(not isinstance(m.get("on"), bool) for m in x)):
                raise ValueError(k)
            x = [{"v": m["v"], "on": m["on"]} for m in x]
        out[k] = x
    return out


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
