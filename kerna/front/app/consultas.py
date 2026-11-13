"""Consultas KQL del tablero y su ejecución en Log Analytics con la identidad administrada.

Las consultas son las del Workbook (kerna/docs/observabilidad/consultas): se copian a kql/ al empaquetar y
"ago(7d)" se sustituye por el rango pedido. Solo devuelven conteos, duraciones y nombres públicos de normas.
"""
from __future__ import annotations

import os
import time
from datetime import timedelta
from pathlib import Path

from . import cache

DIR_KQL = Path(__file__).parent / "kql"
RANGOS = (7, 30)
CONSULTAS = {
    "casos": "front_casos_por_dia",
    "modos": "solicitudes_por_modo",
    "leyes": "front_articulos_por_ley",
    "valoraciones": "front_valoraciones",
    "latencia": "front_latencia",
    "tokens": "tokens_por_solicitud",
}
TTL_S = 60
_cache: dict[int, tuple[float, dict]] = {}
_cliente = None


def kql(nombre: str, dias: int) -> str:
    return (DIR_KQL / f"{CONSULTAS[nombre]}.kql").read_text(encoding="utf-8").replace("ago(7d)", f"ago({int(dias)}d)")


def _logs():
    global _cliente
    if _cliente is None:
        from azure.identity import DefaultAzureCredential
        from azure.monitor.query import LogsQueryClient
        _cliente = LogsQueryClient(DefaultAzureCredential())
    return _cliente


def filas(texto: str, dias: int) -> list[dict]:
    """Ejecuta una consulta y devuelve filas como diccionarios con valores simples (str, número, None)."""
    from azure.monitor.query import LogsQueryStatus
    r = _logs().query_workspace(os.environ["LOG_ANALYTICS_WORKSPACE_ID"], texto, timespan=timedelta(days=dias))
    if r.status != LogsQueryStatus.SUCCESS:
        raise RuntimeError(f"consulta parcial: {r.partial_error}")
    out = []
    for tabla in r.tables:
        cols = list(tabla.columns)
        for f in tabla.rows:
            out.append({c: (v.isoformat() if hasattr(v, "isoformat") else v) for c, v in zip(cols, f)})
    return out


def _num(v, d=0):
    try:
        return round(float(v), d)
    except (TypeError, ValueError):
        return 0


def metricas(dias: int, ejecutar=None) -> dict:
    """Resumen agregado del rango. `ejecutar(texto, dias)` se inyecta en las pruebas."""
    real = ejecutar is None
    ejecutar = ejecutar or filas
    if dias not in RANGOS:
        dias = 7
    hit = _cache.get(dias)
    if real and hit and time.time() - hit[0] < TTL_S:
        return hit[1]
    res = cache.paralelo({n: (lambda n=n: ejecutar(kql(n, dias), dias)) for n in CONSULTAS})
    for r in res.values():
        if isinstance(r, Exception):
            raise r
    crudo = res

    casos = [{"dia": str(f["dia"])[:10], "casos": int(f["casos"]), "con_sugerencia": int(f["con_sugerencia"])} for f in crudo["casos"]]
    modos: dict[str, int] = {"oficial": 0, "respaldo": 0, "local": 0, "manual": 0}
    for f in crudo["modos"]:
        m = str(f["modo"]) if str(f["modo"]) in modos else "manual"
        modos[m] += int(f["solicitudes"])
    leyes = [{"norma": str(f["norma"]) or "Sin ley registrada", "articulos": int(f["articulos"])} for f in crudo["leyes"]]
    val = {"util": 0, "no_util": 0, "ninguno_aplica": 0}
    for f in crudo["valoraciones"]:
        if f["valoracion"] in val:
            val[f["valoracion"]] += int(f["total"])
    lat = crudo["latencia"]
    total_lat = sum(int(f["solicitudes"]) for f in lat)
    # Los percentiles diarios no se pueden combinar exactamente: se informa el ponderado por solicitudes.
    p50 = sum(_num(f["p50_ms"]) * int(f["solicitudes"]) for f in lat) / total_lat if total_lat else 0
    p95 = max((_num(f["p95_ms"]) for f in lat), default=0)
    tok = {"entrada": sum(_num(f["tokens_entrada_total"]) for f in crudo["tokens"]),
           "salida": sum(_num(f["tokens_salida_total"]) for f in crudo["tokens"])}
    out = {"dias": dias, "casos_por_dia": casos, "total_casos": sum(c["casos"] for c in casos), "modos": modos,
           "leyes": leyes, "valoraciones": val,
           "latencia": {"p50_ms": round(p50), "p95_ms": round(p95),
                        "por_dia": [{"dia": str(f["dia"])[:10], "p50_ms": round(_num(f["p50_ms"])), "p95_ms": round(_num(f["p95_ms"]))} for f in lat]},
           "tokens": {**tok, "total": tok["entrada"] + tok["salida"]}}
    if real:
        _cache[dias] = (time.time(), out)
    return out
