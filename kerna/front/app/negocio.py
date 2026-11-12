"""Datos de negocio del front: clientes, plan, tarifa, uso diario, costo de IA, margen y adopción.

Todo sale de las tablas `clientes` y `usodiario` (Azure Table Storage del núcleo, rol Table Data Reader de la
identidad del App Service); nada está fijo en el código salvo los precios de la API de Anthropic. Sin textos de denuncias.
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta, timezone

T_CLIENTES, T_USO = "clientes", "usodiario"
TTL_S = 120
# USD por millón de tokens (entrada, salida). gpt-5-nano ~ Claude Haiku 5.5; gpt-5-mini ~ Claude Sonnet 5.5.
PRECIOS = {"nano": (0.10, 0.50), "mini": (2.00, 10.00)}
COSTO_FIJO_MES = 40.0
DIAS_RIESGO, DIAS_ATENCION = 7, 3
_cache: dict = {"t": 0.0, "v": None}


def _tabla(nombre):
    from azure.data.tables import TableClient
    from azure.identity import DefaultAzureCredential
    return TableClient(endpoint=os.environ["NEGOCIO_TABLA_URL"], table_name=nombre, credential=DefaultAzureCredential())


def costo_ia(u: dict) -> float:
    """Costo en USD de una fila de uso, a precios de Anthropic por modelo."""
    t = 0.0
    for m, (pe, ps) in PRECIOS.items():
        t += (u.get(f"{m}_in") or 0) * pe / 1e6 + (u.get(f"{m}_out") or 0) * ps / 1e6
    return t


def _pct(a, b):
    return round(100 * a / b) if b else 0


def construir(clientes: list[dict], uso: list[dict], hoy: date | None = None, dias: int = 30, crec: float = 15.0) -> dict | None:
    if not clientes:
        return None
    hoy = hoy or datetime.now(timezone.utc).date()
    ini = hoy - timedelta(days=dias - 1)
    dias_l = [ini + timedelta(days=i) for i in range(dias)]
    por_cli: dict[str, dict[date, dict]] = {}
    for u in uso:
        por_cli.setdefault(u["PartitionKey"], {})[date.fromisoformat(u["RowKey"])] = u
    filas, tot_g = [], {"tot": 0, "sug": 0, "val": 0, "uti": 0, "ing": 0.0, "cos": 0.0}
    for c in sorted(clientes, key=lambda x: x.get("nombre", "")):
        if c.get("estado") not in (None, "activo"):
            continue
        d = por_cli.get(c["PartitionKey"], {})
        ventana = [d.get(x, {}) for x in dias_l]
        serie = [int(v.get("denuncias") or 0) for v in ventana]
        tot, sug = sum(serie), sum(int(v.get("con_sugerencia") or 0) for v in ventana)
        val, uti = sum(int(v.get("valoradas") or 0) for v in ventana), sum(int(v.get("utiles") or 0) for v in ventana)
        cos = sum(costo_ia(v) for v in ventana)
        tarifa, plan = float(c.get("tarifa_usd_denuncia") or 0), int(c.get("plan_denuncias_mes") or 0)
        ing = tot * tarifa
        activos = [x for x, v in d.items() if int(v.get("denuncias") or 0) > 0 and x <= hoy]
        ult = max(activos) if activos else None
        sin = (hoy - ult).days if ult else None
        riesgo = "bad" if sin is None or sin > DIAS_RIESGO else ("warn" if sin > DIAS_ATENCION else "ok")
        uso_plan = _pct(tot, plan * dias / 30)
        filas.append({"id": c["PartitionKey"], "nombre": c.get("nombre"), "rubro": c.get("rubro"), "plan": plan, "tarifa": tarifa,
                      "alta": c.get("fecha_alta"), "serie": serie, "tot": tot, "uso_plan": uso_plan,
                      "estado_uso": "bad" if uso_plan > 110 else ("warn" if uso_plan > 90 or uso_plan < 30 else "ok"),
                      "ingreso": round(ing, 2), "costo_ia": round(cos, 4), "margen": round(ing - cos, 2),
                      "margen_pct": _pct(ing - cos, ing), "ultimo_uso": ult.isoformat() if ult else None, "dias_sin_uso": sin,
                      "riesgo": riesgo, "con_sugerencia": sug, "valoradas": val, "utiles": uti})
        for k, v in (("tot", tot), ("sug", sug), ("val", val), ("uti", uti), ("ing", ing), ("cos", cos)):
            tot_g[k] += v
    serie_dia = [sum(f["serie"][i] for f in filas) for i in range(dias)]
    base = tot_g["tot"] * 30 / dias
    proy, tf, ing_m = [], 1.0, 0.0
    cos_u = tot_g["cos"] / tot_g["tot"] if tot_g["tot"] else 0
    ing_u = tot_g["ing"] / tot_g["tot"] if tot_g["tot"] else 0
    for m in range(1, 7):
        tf *= 1 + crec / 100
        n = base * tf
        ing_m, cos_m = n * ing_u, n * cos_u + COSTO_FIJO_MES
        proy.append({"mes": m, "denuncias": round(n), "ingreso": round(ing_m, 2), "costo": round(cos_m, 2),
                     "margen": round(ing_m - cos_m, 2), "margen_pct": _pct(ing_m - cos_m, ing_m)})
    return {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "dias": dias, "desde": ini.isoformat(), "hasta": hoy.isoformat(),
        "fuente": "tablas clientes y usodiario (Azure Table Storage del núcleo); Veridy desde la tabla de solicitudes real",
        "precios": {"nano": {"entrada": 0.10, "salida": 0.50, "equivale": "Claude Haiku 5.5"},
                    "mini": {"entrada": 2.00, "salida": 10.00, "equivale": "Claude Sonnet 5.5"}},
        "clientes": filas, "dias_serie": [x.isoformat() for x in dias_l], "serie_total": serie_dia,
        "totales": {"denuncias": tot_g["tot"], "ingreso": round(tot_g["ing"], 2), "costo_ia": round(tot_g["cos"], 4),
                    "margen": round(tot_g["ing"] - tot_g["cos"], 2), "margen_pct": _pct(tot_g["ing"] - tot_g["cos"], tot_g["ing"]),
                    "clientes_activos": len(filas), "en_riesgo": [f["nombre"] for f in filas if f["riesgo"] == "bad"]},
        "adopcion": {"con_sugerencia_pct": _pct(tot_g["sug"], tot_g["tot"]), "valoradas_pct": _pct(tot_g["val"], tot_g["tot"]),
                     "utiles_pct": _pct(tot_g["uti"], tot_g["val"]), "valoradas": tot_g["val"], "utiles": tot_g["uti"]},
        "proyeccion": {"crecimiento_pct": crec, "costo_fijo_mes": COSTO_FIJO_MES, "meses": proy},
    }


def cargar(crec: float = 15.0, dias: int = 30, clientes=None, uso=None) -> dict | None:
    """Lee las tablas (con caché breve). Lanza si no responden."""
    if clientes is None:
        ahora = time.monotonic()
        if _cache["v"] is None or ahora - _cache["t"] >= TTL_S:
            _cache.update(t=ahora, v=([dict(e) for e in _tabla(T_CLIENTES).list_entities()], [dict(e) for e in _tabla(T_USO).list_entities()]))
        clientes, uso = _cache["v"]
    return construir(clientes, uso or [], dias=dias, crec=crec)
