"""Costos y supuestos financieros de Kerna AI, tomados del capítulo 25 del informe («Presupuesto y evaluación
financiera», Tablas 107 a 115; base de conocimiento en kerna-vault, fuera del repo).

Los valores viven en datos/parametros_financieros.json (con variables de entorno para UF, dólar, inicio de operación y
tasa de descuento). Este módulo no tiene constantes de negocio: modela lo fijo prorrateado por período, lo variable por
cliente y la proyección a cinco años con el mismo método del capítulo, y expresa todo en UF.
"""
from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

RUTA = Path(__file__).parent / "datos" / "parametros_financieros.json"
DIAS_ANIO = 365


@lru_cache(maxsize=1)
def parametros() -> dict:
    p = json.loads(RUTA.read_text(encoding="utf-8"))
    for env, clave, tipo in (("KERNA_UF_CLP", "uf_clp", float), ("KERNA_USD_CLP", "usd_clp", float), ("KERNA_TASA_DESCUENTO", "tasa_descuento", float),
                             ("KERNA_INICIO_OPERACION", "inicio_operacion", str)):
        if os.environ.get(env):
            p[clave] = tipo(os.environ[env])
    return p


def limpiar_cache() -> None:
    parametros.cache_clear()


def uf_del_anio(anio: int = 1) -> float:
    """Valor de la UF en pesos al año de operación `anio`: parte de `uf_clp` (año 1) y se reajusta con la inflación, porque la UF
    sigue al IPC (cap. 25). Así un precio pactado en UF queda constante en UF aunque suba en pesos."""
    return parametros()["uf_clp"] * factor(anio)


def a_uf(clp: float, anio: int = 1) -> float:
    return clp / uf_del_anio(anio)


def usd_a_uf(usd: float, anio: int = 1) -> float:
    """Costo en dólares (p. ej. API de IA) convertido a UF con el dólar de los parámetros y la UF del año."""
    return usd * parametros()["usd_clp"] / uf_del_anio(anio)


def factor(anio: int) -> float:
    """Reajuste acumulado de precios y costos en pesos al año de operación `anio` (1 = sin reajuste)."""
    return (1 + parametros()["inflacion_anual"]) ** (anio - 1)


def anio_operacion(dia: date) -> int:
    """Año de operación (1 a horizonte) que corresponde a una fecha; antes del inicio cuenta como año 1."""
    ini = date.fromisoformat(parametros()["inicio_operacion"])
    n = dia.year - ini.year + (1 if (dia.month, dia.day) >= (ini.month, ini.day) else 0)
    return min(max(n, 1), parametros()["horizonte_anios"])


def plan_de(tipo: str | None, denuncias_mes: int = 0) -> str:
    """Clave del plan: la declarada en el cliente o, si falta, la que corresponde a su cuota mensual."""
    planes = parametros()["planes"]
    if tipo in planes:
        return tipo
    tope = planes["basico"]["casos_maximos_mes"]
    return "basico" if denuncias_mes <= tope else ("pro" if denuncias_mes <= 400 else "plataforma")


def precio_anual_clp(plan: str, anio: int) -> float:
    return parametros()["planes"][plan]["precio_anual_clp_anio1"] * factor(anio)


def costo_servir_anual_clp(plan: str, anio: int) -> float:
    """Costo anual de servir a un cliente del plan (modelos con tope, infraestructura y soporte), Tabla 110."""
    return parametros()["planes"][plan]["costo_servir_anual_clp_anio1"] * factor(anio)


def cuota_api_anual_clp(plan: str) -> float:
    return parametros()["planes"][plan]["cuota_api_mensual_clp"] * 12


def costo_servir_sin_ia_anual_clp(plan: str, anio: int) -> float:
    """Parte del costo de servir que no es API de IA (infraestructura y soporte): costo de servir menos la cuota de API."""
    return max(costo_servir_anual_clp(plan, anio) - cuota_api_anual_clp(plan), 0.0)


def _fijo(c: dict, anio: int) -> float:
    if "por_anio_clp" in c:
        return float(c["por_anio_clp"][anio - 1])
    if anio > c.get("hasta_anio", 99) or anio < c.get("desde_anio", 1):
        return 0.0
    base = c.get("anio1_clp", c.get("anio2_clp"))
    desde = c.get("desde_anio", 1)
    return base * ((1 + parametros()["inflacion_anual"]) ** (anio - desde) if c.get("reajusta") else 1)


def costos_fijos(anio: int) -> list[tuple[str, int]]:
    """Costos fijos anuales por concepto (Tabla 111), en pesos."""
    return [(c["concepto"], round(_fijo(c, anio))) for c in parametros()["costos_fijos_anuales"]]


def total_fijos_clp(anio: int) -> int:
    return sum(m for _, m in costos_fijos(anio))


def inversion_total_clp() -> int:
    return sum(c["clp"] for c in parametros()["inversion_inicial"])


def depreciacion_anual_clp(anio: int) -> float:
    d = parametros()["depreciacion"]
    return sum(d["activos_clp"]) / d["vida_acelerada_anios"] if anio <= d["vida_acelerada_anios"] else 0.0


def tabla_credito() -> list[dict]:
    """Amortización anual del crédito (sistema francés, cuota mensual constante), Tabla 113."""
    c = parametros()["credito"]
    r, n, k = c["tasa_mensual"], c["cuotas"], c["monto_clp"]
    cuota = k * r / (1 - (1 + r) ** -n)
    saldo, filas = float(k), []
    for anio in range(1, parametros()["horizonte_anios"] + 1):
        interes = amort = 0.0
        for _ in range(12):
            if saldo <= 0.5:
                break
            i = saldo * r
            a = min(cuota - i, saldo)
            interes, amort, saldo = interes + i, amort + a, saldo - a
        filas.append({"anio": anio, "interes": interes, "amortizacion": amort, "saldo": max(saldo, 0.0)})
    return filas


def tasa_impuesto(anio: int) -> float:
    t = parametros()["impuesto_primera_categoria"]
    return t[min(anio, len(t)) - 1]


def prorrata(monto_anual: float, dias: int) -> float:
    return monto_anual * dias / DIAS_ANIO


def van(flujos: list[float], tasa: float) -> float:
    return sum(f / (1 + tasa) ** t for t, f in enumerate(flujos))


def tir(flujos: list[float]) -> float | None:
    lo, hi = -0.99, 100.0
    if van(flujos, lo) * van(flujos, hi) > 0:
        return None
    for _ in range(200):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if van(flujos, lo) * van(flujos, m) > 0 else (lo, m)
    return (lo + hi) / 2


def proyeccion_capitulo() -> dict:
    """Flujo de caja financiado a cinco años con el método del capítulo 25 (Tablas 108, 110, 111 y 112 a 115), en pesos."""
    p = parametros()
    cred = tabla_credito()
    anios = []
    for a in range(1, p["horizonte_anios"] + 1):
        ventas = costo = 0.0
        clientes = 0
        for plan in p["planes"].values():
            n = plan["clientes_por_anio"][a - 1]
            clientes += n
            ventas += n * plan["precio_anual_clp_anio1"] * factor(a)
            costo += n * plan["costo_servir_anual_clp_anio1"] * factor(a)
        ext = p["planes"]["plataforma"]["clientes_por_anio"][a - 1] - p["planes"]["plataforma"]["origen_veridy_por_anio"][a - 1]
        particip = p["participacion_veridy"] * (ventas - costo - ext * p["ingreso_neto_plataforma_externa"])
        fijos, dep, interes = total_fijos_clp(a), depreciacion_anual_clp(a), cred[a - 1]["interes"]
        uai = ventas - costo - particip - fijos - dep - interes
        imp = max(uai, 0.0) * tasa_impuesto(a)
        util = uai - imp
        flujo = util + dep - cred[a - 1]["amortizacion"]
        anios.append({"anio": a, "calendario": date.fromisoformat(p["inicio_operacion"]).year + a - 1, "ventas": ventas, "clientes": clientes, "costo_ventas": costo,
                      "participacion_veridy": particip, "costos_fijos": fijos, "depreciacion": dep, "interes": interes, "uai": uai,
                      "impuesto": imp, "utilidad": util, "amortizacion": cred[a - 1]["amortizacion"], "flujo": flujo,
                      "margen_operativo": ventas - costo - particip - fijos})
    inv = inversion_total_clp()
    flujos = [-float(inv)] + [x["flujo"] for x in anios]
    t = p["tasa_descuento"]
    acum, rec = -float(inv), None
    for i, x in enumerate(anios, 1):
        acum += x["flujo"] / (1 + t) ** i
        x["flujo_descontado"] = x["flujo"] / (1 + t) ** i
        if rec is None and acum >= 0:
            rec = i
    v = van(flujos, t)
    return {"anios": anios, "inversion": inv, "van": v, "tir": tir(flujos), "indice_rentabilidad": (v + inv) / inv, "recuperacion_anio": rec,
            "tasa_descuento": t}
