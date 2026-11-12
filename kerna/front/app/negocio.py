"""Datos de negocio del front: clientes, plan, tarifa, uso diario, costo de IA, margen y adopción.

Todo sale de las tablas `clientes` y `usodiario` (Azure Table Storage del núcleo, rol Table Data Reader de la
identidad del App Service) y de los parámetros financieros del informe de Kerna (capítulo 25, ver finanzas.py);
nada está fijo en el código salvo los precios de la API de Anthropic. Sin textos de denuncias.

Moneda: tarifas, ingresos, costos, margen y proyección en UF. El costo de IA se mide en USD y se convierte a UF.
Costos aplicados al período (capítulo 25): costo de servir por cliente (IA con tope de cuota del plan, más infraestructura
y soporte, Tabla 110), participación de Veridy (30 % del ingreso neto de sus contratos), costos fijos prorrateados por
días (Tabla 111), depreciación, interés del crédito e impuesto de primera categoría (Tablas 112 a 114).
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta, timezone

from . import finanzas

T_CLIENTES, T_USO = "clientes", "usodiario"
TTL_S = 120
# USD por millón de tokens (entrada, salida). gpt-5-nano ~ Claude Haiku 5.5; gpt-5-mini ~ Claude Sonnet 5.5.
PRECIOS = {"nano": (0.10, 0.50), "mini": (2.00, 10.00)}
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


def _uf(v):
    return round(v, 2)


def construir(clientes: list[dict], uso: list[dict], hoy: date | None = None, dias: int = 30, crec: float | None = None) -> dict | None:
    """`crec` se acepta por compatibilidad y se ignora: la proyección usa los supuestos del capítulo 25."""
    if not clientes:
        return None
    hoy = hoy or datetime.now(timezone.utc).date()
    ini = hoy - timedelta(days=dias - 1)
    dias_l = [ini + timedelta(days=i) for i in range(dias)]
    anio = finanzas.anio_operacion(hoy)
    par = finanzas.parametros()
    por_cli: dict[str, dict[date, dict]] = {}
    for u in uso:
        por_cli.setdefault(u["PartitionKey"], {})[date.fromisoformat(u["RowKey"])] = u
    filas = []
    g = {"tot": 0, "sug": 0, "val": 0, "uti": 0, "ing": 0.0, "ia": 0.0, "ia_bruto": 0.0, "otros": 0.0, "neto_veridy": 0.0}
    for c in sorted(clientes, key=lambda x: x.get("nombre", "")):
        if c.get("estado") not in (None, "activo"):
            continue
        d = por_cli.get(c["PartitionKey"], {})
        ventana = [d.get(x, {}) for x in dias_l]
        serie = [int(v.get("denuncias") or 0) for v in ventana]
        tot, sug = sum(serie), sum(int(v.get("con_sugerencia") or 0) for v in ventana)
        val, uti = sum(int(v.get("valoradas") or 0) for v in ventana), sum(int(v.get("utiles") or 0) for v in ventana)
        plan_dmes = int(c.get("plan_denuncias_mes") or 0)
        clave = finanzas.plan_de(c.get("plan_tipo"), plan_dmes)
        # Tarifa en UF por año de contrato; sin ella, el precio del plan del capítulo 25.
        tarifa = float(c.get("precio_anual_uf") or finanzas.a_uf(finanzas.precio_anual_clp(clave, anio), anio))
        ing = finanzas.prorrata(tarifa, dias)
        ia_bruto = finanzas.usd_a_uf(sum(costo_ia(v) for v in ventana), anio)
        ia = min(ia_bruto, finanzas.a_uf(finanzas.prorrata(finanzas.cuota_api_anual_clp(clave), dias), anio))  # RF25: sobre la cuota pasa al modo local
        otros = finanzas.a_uf(finanzas.prorrata(finanzas.costo_servir_sin_ia_anual_clp(clave, anio), dias), anio)
        veridy = bool(c["origen_veridy"]) if "origen_veridy" in c else (par["planes"][clave]["origen_veridy"] or c["PartitionKey"] == "veridy-dev")
        costo_servir = ia + otros
        activos = [x for x, v in d.items() if int(v.get("denuncias") or 0) > 0 and x <= hoy]
        ult = max(activos) if activos else None
        sin = (hoy - ult).days if ult else None
        riesgo = "bad" if sin is None or sin > DIAS_RIESGO else ("warn" if sin > DIAS_ATENCION else "ok")
        uso_plan = _pct(tot, plan_dmes * dias / 30)
        filas.append({"id": c["PartitionKey"], "nombre": c.get("nombre"), "rubro": c.get("rubro"), "plan": plan_dmes, "plan_tipo": par["planes"][clave]["nombre"],
                      "tarifa_uf_anual": _uf(tarifa), "origen_veridy": veridy,
                      "alta": c.get("fecha_alta"), "serie": serie, "tot": tot, "uso_plan": uso_plan,
                      "estado_uso": "bad" if uso_plan > 110 else ("warn" if uso_plan > 90 or uso_plan < 30 else "ok"),
                      "ingreso": _uf(ing), "costo_ia": round(ia, 4), "costo_servir": _uf(costo_servir), "margen": _uf(ing - costo_servir),
                      "margen_pct": _pct(ing - costo_servir, ing), "ultimo_uso": ult.isoformat() if ult else None, "dias_sin_uso": sin,
                      "riesgo": riesgo, "con_sugerencia": sug, "valoradas": val, "utiles": uti})
        for k, v in (("tot", tot), ("sug", sug), ("val", val), ("uti", uti), ("ing", ing), ("ia", ia), ("ia_bruto", ia_bruto), ("otros", otros)):
            g[k] += v
        if veridy:
            g["neto_veridy"] += ing - costo_servir
    serie_dia = [sum(f["serie"][i] for f in filas) for i in range(dias)]
    # Resultado del período con todos los costos del capítulo 25.
    uf = par["uf_clp"]
    cs = g["ia"] + g["otros"]
    particip = par["participacion_veridy"] * max(g["neto_veridy"], 0.0)
    fijos = finanzas.a_uf(finanzas.prorrata(finanzas.total_fijos_clp(anio), dias), anio)
    dep = finanzas.a_uf(finanzas.prorrata(finanzas.depreciacion_anual_clp(anio), dias), anio)
    interes = finanzas.a_uf(finanzas.prorrata(finanzas.tabla_credito()[anio - 1]["interes"], dias), anio)
    m_oper = g["ing"] - cs - particip - fijos
    uai = m_oper - dep - interes
    imp = max(uai, 0.0) * finanzas.tasa_impuesto(anio)
    util = uai - imp
    pc = finanzas.proyeccion_capitulo()
    proy = {"fuente": "Informe de Kerna, capítulo 25 (Tablas 108 a 115)", "tasa_descuento_pct": round(pc["tasa_descuento"] * 100, 1),
            "inflacion_pct": round(par["inflacion_anual"] * 100, 1), "participacion_veridy_pct": round(par["participacion_veridy"] * 100),
            "inicio_operacion": par["inicio_operacion"], "inversion": _uf(finanzas.a_uf(pc["inversion"])),
            "van": _uf(finanzas.a_uf(pc["van"])), "tir_pct": round(pc["tir"] * 100, 1) if pc["tir"] is not None else None,
            "indice_rentabilidad": round(pc["indice_rentabilidad"], 2), "recuperacion_anio": pc["recuperacion_anio"],
            "anios": [{"anio": a["anio"], "calendario": a["calendario"], "clientes": a["clientes"], **{k: _uf(finanzas.a_uf(a[k], a["anio"])) for k in
                       ("ventas", "costo_ventas", "participacion_veridy", "costos_fijos", "depreciacion", "interes", "uai", "impuesto", "utilidad", "flujo", "margen_operativo")},
                       "margen_operativo_pct": _pct(a["margen_operativo"], a["ventas"])} for a in pc["anios"]]}
    return {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "dias": dias, "desde": ini.isoformat(), "hasta": hoy.isoformat(),
        "fuente": "tablas clientes y usodiario (Azure Table Storage del núcleo); costos y supuestos del informe de Kerna, capítulo 25",
        "moneda": "UF", "uf_clp": round(finanzas.uf_del_anio(anio)), "usd_clp": par["usd_clp"], "anio_operacion": anio,
        "precios": {"nano": {"entrada": 0.10, "salida": 0.50, "equivale": "Claude Haiku 5.5"},
                    "mini": {"entrada": 2.00, "salida": 10.00, "equivale": "Claude Sonnet 5.5"}},
        "clientes": filas, "dias_serie": [x.isoformat() for x in dias_l], "serie_total": serie_dia,
        "totales": {"denuncias": g["tot"], "ingreso": _uf(g["ing"]), "costo_ia": round(g["ia"], 4), "costo_ia_bruto": round(g["ia_bruto"], 4),
                    "costo_servir": _uf(cs), "margen_bruto": _uf(g["ing"] - cs), "margen_bruto_pct": _pct(g["ing"] - cs, g["ing"]),
                    "participacion_veridy": _uf(particip), "costos_fijos": _uf(fijos), "depreciacion": _uf(dep), "interes": _uf(interes),
                    "margen_operativo": _uf(m_oper), "margen_operativo_pct": _pct(m_oper, g["ing"]), "resultado_antes_impuesto": _uf(uai),
                    "impuesto": _uf(imp), "utilidad": _uf(util), "margen_neto_pct": _pct(util, g["ing"]),
                    "margen": _uf(util), "margen_pct": _pct(util, g["ing"]),
                    "clientes_activos": len(filas), "en_riesgo": [f["nombre"] for f in filas if f["riesgo"] == "bad"]},
        "adopcion": {"con_sugerencia_pct": _pct(g["sug"], g["tot"]), "valoradas_pct": _pct(g["val"], g["tot"]),
                     "utiles_pct": _pct(g["uti"], g["val"]), "valoradas": g["val"], "utiles": g["uti"]},
        "proyeccion": proy,
    }


def cargar(crec: float | None = None, dias: int = 30, clientes=None, uso=None) -> dict | None:
    """Lee las tablas (con caché breve). Lanza si no responden."""
    if clientes is None:
        ahora = time.monotonic()
        if _cache["v"] is None or ahora - _cache["t"] >= TTL_S:
            _cache.update(t=ahora, v=([dict(e) for e in _tabla(T_CLIENTES).list_entities()], [dict(e) for e in _tabla(T_USO).list_entities()]))
        clientes, uso = _cache["v"]
    return construir(clientes, uso or [], dias=dias, crec=crec)
