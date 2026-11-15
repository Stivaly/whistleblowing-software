"""Modelo de vista del Resumen y de Negocio: convierte los datos reales del backend en lo que pintan las plantillas.

Nada se inventa aquí: cada cifra viene de consultas.metricas (Log Analytics), evaluaciones (recall medido), proveedores,
reintentos o negocio/finanzas. Donde falta un dato el estado es «na» (sin datos). Las metas salen de la configuración
existente (informe.META_RECALL y informe.META_P95_MS). Los umbrales de color están nombrados abajo.

El resultado lleva, además de la estructura, mapas planos `t` (textos), `s` (estados), `w`/`l` (anchos y posiciones en %),
`rot`, `d` (trazados SVG) e `ico` (íconos) con las MISMAS claves que las plantillas marcan con data-t, data-s, etc.:
el navegador solo vuelve a pedir /api/metricas y reemplaza esos valores, sin recargar la página.
"""
from __future__ import annotations

import math
import time

from . import formato as f
from . import informe as inf
from . import graficos
from . import negocio as neg_mod

# Umbrales de color (no son datos: son criterios de lectura, explicados en los tooltips).
META_RECALL = inf.META_RECALL
META_P95_S = inf.META_P95_MS / 1000
SUG_OK, SUG_WARN = 90, 70          # % de denuncias con sugerencia
RECALL_ALERTA = 0.10               # por debajo de la meta menos este margen: problema
MANUAL_PROBLEMA_PCT = 10           # % de casos en revisión manual que se considera problema
# Íconos de estado de la identidad Núcleo (identidad-v3, tono entre paréntesis): bien = lista (verde), atención = contingencia-modelo (ámbar),
# mal = cadena-agotada (rojo), sin datos = sin-info (neutro), en proceso = generando (azul). Los específicos están en ICONO_X.
ICONO = {"ok": "e-lista", "warn": "e-contingencia-modelo", "bad": "e-cadena-agotada", "na": "e-sin-info", "pro": "e-generando"}
ICONO_X = {"revision": "e-revision-citas", "tiempo": "e-revision-tiempo", "busqueda": "e-contingencia-busqueda", "sin_conexion": "e-sin-conexion",
           "sin_normativa": "e-sin-normativa", "nucleo": "e-nucleo-no-disponible", "conector": "e-conector-en-proceso", "valorada": "e-valorada"}
ESTADO_TXT = {"ok": "Bien", "warn": "Atención", "bad": "Problema", "na": "Sin datos"}
PROV_ESTADO = {"operativo": "ok", "degradado": "warn", "caido": "bad", "sin_informacion": "na"}
PROV_TXT = {"operativo": "Operativo", "degradado": "Degradado", "caido": "Caído", "sin_informacion": "Sin información"}
GRAVEDAD = {"ok": 0, "na": 0, "warn": 1, "bad": 2}
ETAPAS = {"anonimizacion": "Anonimizar", "clasificacion": "Clasificar el caso", "recuperacion": "Buscar en la ley",
          "generacion": "Redactar sugerencia", "validacion": "Verificar citas"}
DIAS_SEM = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
FRANJAS = ["0-3 h", "3-6 h", "6-9 h", "9-12 h", "12-15 h", "15-18 h", "18-21 h", "21-24 h"]


def peor(*estados) -> str:
    v = [e for e in estados if e in GRAVEDAD]
    return max(v, key=lambda e: GRAVEDAD[e]) if v else "na"


def pct(a, b) -> int:
    return round(100 * a / b) if b else 0


def _n(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


class Mapas:
    """Mapas planos que el navegador usa para actualizar el Resumen."""

    def __init__(self):
        self.t, self.s, self.w, self.l, self.rot, self.d, self.ico, self.x = {}, {}, {}, {}, {}, {}, {}, {}

    def dic(self) -> dict:
        return {"t": self.t, "s": self.s, "w": self.w, "l": self.l, "rot": self.rot, "d": self.d, "ico": self.ico, "x": self.x}


def zonas(zs):
    return [{"a": a, "b": b, "e": e, "d": graficos.g_arc(a, b)} for a, b, e in zs]


def costo_modelos(filas: list[dict]) -> dict | None:
    """Costo en USD a precios de la API de Anthropic con el equivalente Claude de cada modelo usado (misma regla que el informe)."""
    tot, n = {}, 0
    for r in filas:
        cl = inf.EQUIVALENCIA.get(str(r.get("modelo")), inf.POR_DEFECTO)
        pe, ps, pe2, ps2 = inf.PRECIOS_CLAUDE[cl]
        c, ent, sal = int(_n(r.get("solicitudes"))), _n(r.get("tokens_entrada_total")), _n(r.get("tokens_salida_total"))
        prom = _n(r.get("tokens_entrada_prom")) or (ent / c if c else 0)
        alto = pe2 is not None and prom > inf.UMBRAL_PROMPT
        usd = ent * (pe2 if alto else pe) / 1e6 + sal * (ps2 if alto else ps) / 1e6
        real = str(r.get("modelo") or "sin nombre")
        d = tot.setdefault(real, {"modelo": real, "ref": cl, "casos": 0, "usd": 0.0})  # el modelo real; el equivalente Claude es solo precio de referencia
        d["casos"] += c
        d["usd"] += usd
        n += c
    if not n:
        return None
    lista = sorted(tot.values(), key=lambda x: -x["usd"])
    total = sum(x["usd"] for x in lista)
    return {"total": total, "por_caso": total / n, "casos": n, "modelos": lista}


def heat(filas: list[dict]) -> dict | None:
    """Denuncias por día de la semana (lunes a domingo) y franja de 3 horas."""
    if not filas:
        return None
    m = [[0] * 8 for _ in range(7)]
    for r in filas:
        try:
            dia = (int(_n(r["dow"])) - 1) % 7  # Kusto: 0 = domingo
            m[dia][int(_n(r["hora"])) // 3] += int(_n(r["casos"]))
        except (KeyError, ValueError, IndexError):
            continue
    datos = [[j, i, m[i][j]] for i in range(7) for j in range(8)]
    mx = max(x[2] for x in datos)
    return {"datos": datos, "max": max(mx, 1), "dias": DIAS_SEM, "franjas": FRANJAS} if mx else None


def etapas_lista(filas: list[dict]) -> list[dict]:
    out = [{"id": str(r["etapa"]), "n": ETAPAS.get(str(r["etapa"]), str(r["etapa"]).capitalize()), "ms": _n(r["p50_ms"])} for r in filas if r.get("etapa")]
    orden = list(ETAPAS)
    out.sort(key=lambda x: orden.index(x["id"]) if x["id"] in orden else 99)
    tot = sum(x["ms"] for x in out) or 1
    mx = max((x["ms"] for x in out), default=1) or 1
    for x in out:
        share = x["ms"] / tot
        x["e"] = "bad" if share >= 0.5 else ("warn" if share >= 0.25 else "ok")
        x["s"] = "< 0,1" if 0 < x["ms"] < 50 else f.segundos(x["ms"])
        x["ancho"] = round(100 * x["ms"] / mx, 1)
    return out


def resumen(m: dict, ev: dict | None = None, prov: dict | None = None, rei: dict | None = None, costo: dict | None = None,
            etapas: list[dict] | None = None, horarios: dict | None = None, dias: int = 7, ahora: float | None = None, conector: dict | None = None) -> dict:
    """`conector`: estado real del conector (reintentos.con_estado_real): «revisión manual» y «sin sugerencia» cuentan casos distintos que existen hoy en Veridy."""
    mp = Mapas()
    tot = m["total_casos"]
    con_sug = sum(c["con_sugerencia"] for c in m["casos_por_dia"])
    modos = m["modos"]
    real = conector if conector and conector.get("fuente") == "conector" else None
    if real:
        tot, con_sug = real["casos"], real["con_sugerencia"]  # casos que existen hoy en Veridy, no eventos de telemetría
    sug_pct = pct(con_sug, tot)
    if real:
        modos = {**modos, "manual": real["manual"]}
    ntot = sum(modos.values())
    recall = (ev or {}).get("recall") if ev else None
    meta_rec = (recall or {}).get("meta") or META_RECALL
    rec_glob = None
    if recall and recall.get("por_ley"):
        g = next((x for x in recall["por_ley"] if x["ley"] == "Global"), recall["por_ley"][0])
        rec_glob = g.get("recall5")
    p50, p95 = m["latencia"]["p50_ms"], m["latencia"]["p95_ms"]
    p95_s, p50_s = p95 / 1000, p50 / 1000
    k = []

    # --- Denuncias
    e_c = "ok" if tot else "na"
    serie = [c["casos"] for c in m["casos_por_dia"]]
    k.append({"k": "casos", "i": "inbox", "l": "Denuncias", "form": "spark", "e": e_c, "p": "", "u": "", "num": tot, "v": f.miles(tot),
              "et": "Normal" if tot else "Sin denuncias en el período", "tr": "", "te": "na", "ta": "minus", "s": serie,
              "x": (f"{f.miles(tot)} casos en Veridy; {f.miles(con_sug)} con sugerencia." if real else f"{f.miles(tot)} casos procesados en {dias} días; {f.miles(con_sug)} terminaron con sugerencia.") if tot else "No hay denuncias en el período."})
    # --- Acierto
    if rec_glob is not None:
        e_a = "ok" if rec_glob >= meta_rec else ("warn" if rec_glob >= meta_rec - RECALL_ALERTA else "bad")
        va = f.dec_corto(rec_glob * 100, 1)
        et_a = "Cumple la meta" if e_a == "ok" else "Bajo la meta"
        x_a = (f"Cuando existe un artículo correcto, Kerna lo incluye entre sus 5 primeras sugerencias el {va} % de las veces. "
               f"Meta: {f.dec_corto(meta_rec * 100, 1)} %. Medido el {f.fecha_corta(recall.get('fecha'))} en el {SET_PANEL.lower()}.")
    else:
        e_a, va, et_a, x_a = "na", "—", "Sin datos", "Todavía no hay una medición de calidad guardada."
    z_a = [(0, meta_rec - RECALL_ALERTA, "bad"), (meta_rec - RECALL_ALERTA, meta_rec, "warn"), (meta_rec, 1, "ok")]
    k.append({"k": "calidad", "i": "target", "l": "Sugerencias acertadas", "form": "gauge", "e": e_a, "p": "", "u": "%" if rec_glob is not None else "", "num": None if rec_glob is None else round(rec_glob * 100, 1),
              "v": va, "f": rec_glob or 0, "zm": meta_rec, "zl": f.dec_corto(meta_rec * 100, 0), "z": zonas(z_a), "et": et_a, "tr": "", "te": "na", "ta": "minus", "x": x_a,
              "tick": graficos.g_tick(meta_rec)})
    # --- Respuesta (9 de cada 10 casos frente a la meta)
    if m["latencia"]["por_dia"]:
        e_r = "ok" if p95_s <= META_P95_S else ("warn" if p95_s <= 2 * META_P95_S else "bad")
        mx_r = 3 * META_P95_S
        z_r = [(0, META_P95_S, "ok"), (META_P95_S, 2 * META_P95_S, "warn"), (2 * META_P95_S, mx_r, "bad")]
        k.append({"k": "tiempo", "i": "timer", "l": "Tiempo de respuesta", "form": "bullet", "e": e_r, "p": "", "u": "s", "num": round(p95_s, 1), "v": f.segundos(p95),
                  "max": mx_r, "meta": META_P95_S, "metaT": f"meta {f.dec_corto(META_P95_S, 0)} s", "z": [{"a": a, "b": b, "e": e} for a, b, e in z_r],
                  "mx_txt": f"{f.dec_corto(mx_r, 0)} s", "pos": min(100, p95_s / mx_r * 100), "pos_meta": META_P95_S / mx_r * 100,
                  "et": "Dentro de la meta" if e_r == "ok" else "Sobre la meta", "tr": "", "te": "na", "ta": "minus",
                  "x": f"9 de cada 10 casos reciben su sugerencia en menos de {f.segundos(p95)} s (el peor día del período). La mitad, en {f.segundos(p50)} s. Meta: {f.dec_corto(META_P95_S, 0)} s."})
    else:
        e_r = "na"
        k.append({"k": "tiempo", "i": "timer", "l": "Tiempo de respuesta", "form": "bullet", "e": "na", "p": "", "u": "", "num": None, "v": "—", "max": 3 * META_P95_S,
                  "meta": META_P95_S, "metaT": f"meta {f.dec_corto(META_P95_S, 0)} s", "z": [{"a": 0, "b": 1, "e": "na"}], "mx_txt": "", "pos": 0, "pos_meta": 33.3,
                  "et": "Sin datos", "tr": "", "te": "na", "ta": "minus", "x": "No hay solicitudes medidas en el período."})
    # --- Costo
    if costo:
        refs = sorted({x["ref"] for x in costo["modelos"]})
        k.append({"k": "costo_k", "i": "coins", "l": "Costo del período", "form": "costo", "e": "na", "p": "US$", "u": "", "num": round(costo["total"], 2), "v": f.usd(costo["total"]),
                  "et": "", "tr": "", "te": "na", "ta": "minus", "s": serie, "por_caso": f.usd(costo["por_caso"], 3),
                  "stack": [{"n": x["modelo"], "usd": f.usd(x["usd"]), "w": round(100 * x["usd"] / costo["total"], 1) if costo["total"] else 0} for x in costo["modelos"][:4]],  # sin meta de costo en la configuración: sin estado
                  "x": f"Costo por denuncia: US$ {f.usd(costo['por_caso'], 4)}. " + " · ".join(f"{x['modelo']} US$ {f.usd(x['usd'])}" for x in costo["modelos"]) + ". Precio de referencia: " + ", ".join(refs) + "."})
    else:
        k.append({"k": "costo_k", "i": "coins", "l": "Costo del período", "form": "spark", "e": "na", "p": "", "u": "", "num": None, "v": "—", "et": "Sin datos", "tr": "", "te": "na",
                  "ta": "minus", "s": serie, "x": "No hay tokens medidos en el período."})
    for x in k:
        key = x["k"]
        mp.t[f"k.{key}.v"] = x["v"]
        mp.t[f"k.{key}.et"] = x["et"]
        mp.t[f"k.{key}.u"] = x["u"]
        mp.t[f"k.{key}.p"] = x["p"]
        mp.s[f"k.{key}"] = x["e"]
        mp.ico[f"k.{key}"] = ICONO[x["e"]]
        mp.x[f"k.{key}"] = x["x"]
        if x["form"] == "spark" and len(x["s"]) < 4:  # con menos de 4 días una línea no dice nada: se muestran los días como filas
            x["form"] = "dias" if x["k"] == "casos" and x["s"] else "none"
            if x["form"] == "dias":
                mx = max(x["s"]) or 1
                x["dias_l"] = [{"d": f.fecha_corta(c["dia"]), "n": f.miles(c["casos"]), "w": round(100 * c["casos"] / mx)} for c in m["casos_por_dia"]]
        if x["form"] == "spark":
            x["d_l"], x["d_a"] = graficos.spark(x["s"]), graficos.spark_area(x["s"])
            mp.d[f"k.{key}.l"], mp.d[f"k.{key}.a"] = x["d_l"], x["d_a"]
        if x["form"] == "gauge":
            mp.rot[f"k.{key}"] = (x["f"] - .5) * 180
        if x["form"] == "bullet":
            mp.l[f"k.{key}.m"] = x["pos"]

    # --- Modos y sugerencia
    filas_modo = []
    for clave, txt, est in (("oficial", "Modelo principal", "ok"), ("respaldo", "Modelo de respaldo", "warn"), ("local", "Modelo local (sin costo)", "warn"), ("manual", "Revisión manual", "bad")):
        n = modos.get(clave, 0)
        filas_modo.append({"k": clave, "t": txt, "e": est, "n": n, "p": pct(n, ntot)})
        mp.t[f"modo.{clave}.n"], mp.t[f"modo.{clave}.p"] = f.miles(n), f"{pct(n, ntot)} %"
        mp.w[f"modo.{clave}"] = pct(n, ntot)
    e_sug = "na" if not tot else ("ok" if sug_pct >= SUG_OK else ("warn" if sug_pct >= SUG_WARN else "bad"))
    mp.t["sug.v"], mp.s["sug"] = str(sug_pct), e_sug

    # --- Rapidez
    rap = {"p50": f.segundos(p50), "p95": f.segundos(p95), "meta": f.dec_corto(META_P95_S, 0), "hay": bool(m["latencia"]["por_dia"]),
           "e50": "na" if not m["latencia"]["por_dia"] else ("ok" if p50_s <= META_P95_S else "warn"), "e95": e_r}
    mp.t["rap.p50"], mp.t["rap.p95"] = rap["p50"], rap["p95"]
    mp.s["rap.p50"], mp.s["rap.p95"] = rap["e50"], rap["e95"]
    et = etapas or []
    for x in et:
        mp.t[f"et.{x['id']}"], mp.w[f"et.{x['id']}"], mp.s[f"et.{x['id']}"] = f"{x['s']} s", x["ancho"], x["e"]

    # --- Aciertos por ley, valoraciones, leyes
    aciertos = []
    if recall:
        for x in recall["por_ley"]:
            if x["ley"] == "Global" or x.get("recall5") is None:
                continue
            v = x["recall5"]
            e = "ok" if v >= meta_rec else ("warn" if v >= meta_rec - RECALL_ALERTA else "bad")
            aciertos.append({"n": inf.ley_corta(x["ley"]), "full": inf.nombre_ley(x["ley"]), "v": f.dec_corto(v * 100, 1), "w": round(v * 100, 1), "e": e, "casos": x.get("casos_articulo")})
    val = m["valoraciones"]
    nval = sum(val.values())
    vals = [{"t": t, "n": val[c], "p": pct(val[c], nval), "e": e} for c, t, e in (("util", "Útil", "ok"), ("no_util", "No útil", "bad"), ("ninguno_aplica", "Ninguno aplica", "warn"))]
    sin_ley = sum(x["articulos"] for x in m["leyes"] if x["norma"] == "Sin ley registrada")
    leyes = sorted((x for x in m["leyes"] if x["norma"] != "Sin ley registrada"), key=lambda x: -x["articulos"])[:6]
    mx_ley = max((x["articulos"] for x in leyes), default=1) or 1
    leyes_v = [{"n": inf.ley_corta(x["norma"]), "full": inf.nombre_ley(x["norma"]), "norma": x["norma"], "v": x["articulos"], "w": round(100 * x["articulos"] / mx_ley)} for x in leyes]

    # --- Proveedores
    provs = []
    if prov:
        for p in prov["proveedores"]:
            e = PROV_ESTADO.get(p["estado"], "na")
            provs.append({**p, "e": e, "txt": PROV_TXT.get(p["estado"], "Sin información")})
            mp.s[f"prov.{p['id']}"], mp.ico[f"prov.{p['id']}"] = e, (ICONO_X["sin_conexion"] if p["estado"] == "sin_informacion" else ICONO[e])
            mp.t[f"prov.{p['id']}.t"] = PROV_TXT.get(p["estado"], "Sin información")
            mp.x[f"prov.{p['id']}"] = p["mensaje"]

    # --- Salud y estado general
    e_mod = "na" if not ntot else ("bad" if pct(modos.get("manual", 0), ntot) >= MANUAL_PROBLEMA_PCT else ("warn" if (modos.get("manual", 0) or modos.get("respaldo", 0) or modos.get("local", 0)) else "ok"))
    d_mod = ("Aún no hay casos en el período." if not ntot else
             f"En {dias} días, {pct(modos.get('oficial', 0), ntot)} de cada 100 casos los resolvió el modelo principal; {modos.get('respaldo', 0) + modos.get('local', 0)} con respaldo y {modos.get('manual', 0)} pasaron a revisión manual.")
    nrei = rei["r"]["reintentables"] if rei else None
    e_ven = "na" if nrei is None else ("warn" if nrei else "ok")
    d_ven = "Sin datos del conector." if nrei is None else (f"{nrei} {'caso espera' if nrei == 1 else 'casos esperan'} reintento." if nrei else "Sin casos en espera.")
    vo = next((p for p in provs if p["id"] == "voyage"), None)
    e_bus, d_bus = (vo["e"], vo["mensaje"]) if vo else ("na", "Sin información del proveedor.")
    salud = [{"k": "modelo", "n": "Modelos de IA", "i": "bot", "e": e_mod, "d": d_mod}, {"k": "conector", "n": "Enlace con Veridy", "i": "plug", "e": e_ven, "d": d_ven},
             {"k": "busqueda", "n": "Búsqueda de leyes", "i": "search", "e": e_bus, "d": d_bus}, {"k": "calidad", "n": "Calidad", "i": "target", "e": e_a, "d": et_a + ("" if rec_glob is None else f": {f.dec_corto(rec_glob * 100, 1)} % de acierto.")}]
    for s in salud:
        mp.t[f"sal.{s['k']}.t"] = ESTADO_TXT[s["e"]]
        mp.s[f"sal.{s['k']}"], mp.ico[f"sal.{s['k']}"], mp.x[f"sal.{s['k']}"] = s["e"], ICONO[s["e"]], s["d"]
    e_prov = PROV_ESTADO.get(prov["general"]["estado"], "na") if prov else "na"
    e_gen = peor(e_prov, e_a, e_r, e_sug, e_ven, e_mod)
    n_mejorar = sum(1 for e in (e_prov, e_a, e_r, e_sug, e_ven, e_mod) if e in ("warn", "bad"))
    titulo = {"ok": "Sí", "warn": "Atención", "bad": "Problema", "na": "Sin datos"}[e_gen]
    if e_gen == "ok":
        sub = "Todo funciona y está dentro de las metas."
    elif e_gen == "na":
        sub = "Aún no hay datos suficientes para opinar."
    else:
        sub = "Funciona, con 1 cosa por mejorar." if n_mejorar == 1 else f"Funciona, con {n_mejorar} cosas por mejorar."
    if prov and e_prov != "ok" and prov["general"]["estado"] == "caido":
        sub = "Atención: proveedor caído. " + prov["general"]["detalle"]
    elif prov and e_prov != "ok":
        sub = prov["general"]["texto"] + " " + prov["general"]["detalle"]
    mp.t["eg.t"], mp.t["eg.s"], mp.s["eg"], mp.ico["eg"] = titulo, sub, e_gen, ICONO[e_gen]

    # --- Costo por modelo
    costo_v = None
    if costo:
        costo_v = {"total": f.usd(costo["total"]), "por_caso": f.usd(costo["por_caso"], 4),
                   "ref": ", ".join(sorted({x["ref"] for x in costo["modelos"]})),
                   "modelos": [{"n": x["modelo"], "usd": f.usd(x["usd"]), "w": round(100 * x["usd"] / costo["total"], 1) if costo["total"] else 0} for x in costo["modelos"]]}
        mp.t["costo.total"], mp.t["costo.caso"] = costo_v["total"], costo_v["por_caso"]
        for i, x in enumerate(costo_v["modelos"]):
            mp.t[f"costo.m{i}"], mp.w[f"costo.m{i}"] = x["usd"], x["w"]

    # --- Gráficos (datos para ECharts)
    dias_fmt = [f.fecha_corta(c["dia"]) for c in m["casos_por_dia"]]
    graf = {
        "casos": {"labels": dias_fmt, "con": [c["con_sugerencia"] for c in m["casos_por_dia"]], "sin": [c["casos"] - c["con_sugerencia"] for c in m["casos_por_dia"]]},
        "lat": {"labels": [f.fecha_corta(x["dia"]) for x in m["latencia"]["por_dia"]], "p50": [round(x["p50_ms"] / 1000, 1) for x in m["latencia"]["por_dia"]],
                "p95": [round(x["p95_ms"] / 1000, 1) for x in m["latencia"]["por_dia"]], "meta": META_P95_S},
        "heat": horarios,
        "dias": dias,
    }
    return {"dias": dias, "generado": int(ahora or time.time()), "kpis": k, "eg": {"e": e_gen, "t": titulo, "s": sub}, "salud": salud, "modos": filas_modo,
            "sug_pct": sug_pct, "sug_real": bool(real), "e_sug": e_sug, "total": tot, "rapidez": rap, "etapas": et, "aciertos": aciertos, "meta_recall": f.dec_corto(meta_rec * 100, 1),
            "valoraciones": vals, "n_val": nval, "leyes": leyes_v, "sin_ley": sin_ley, "proveedores": provs, "costo": costo_v, "graficos": graf, "con_recall": rec_glob is not None,
            "mapas": mp.dic()}


# ---------------------------------------------------------------------------------------------------------------------
def negocio(n: dict) -> dict:
    """Vista de Negocio con los números de negocio.construir (todo en UF)."""
    t, a, p = n["totales"], n["adopcion"], n["proyeccion"]
    cls = n["clientes"]
    activos = [c for c in cls if c["riesgo"] in ("ok", "warn")]
    riesgo = [c for c in cls if c["riesgo"] == "bad"]
    sin_dato = [c for c in cls if c["riesgo"] == "na"]
    mo = t["margen_operativo_pct"]
    e_mar = "ok" if mo >= 60 else ("warn" if mo >= 30 else "bad")
    e_val = "na" if not t["denuncias"] else ("ok" if a["valoradas_pct"] >= 50 else ("warn" if a["valoradas_pct"] >= 30 else "bad"))
    e_gen = "bad" if t["utilidad"] < 0 else ("warn" if riesgo or e_val in ("bad", "warn") or e_mar != "ok" else "ok")
    puntos = [{"e": "bad", "n": c["nombre"], "t": f"{c['dias_sin_uso']} días sin uso" if c["dias_sin_uso"] is not None else "Sin uso en el período"} for c in riesgo]
    if e_val in ("bad", "warn"):
        puntos.append({"e": e_val, "n": "Sugerencias valoradas", "t": "Muy pocas" if e_val == "bad" else "Pocas"})
    if e_mar != "ok":
        puntos.append({"e": e_mar, "n": "Margen operativo", "t": f"{f.dec_corto(mo, 0)} %"})
    nv = len(puntos)
    sub = {"ok": "Cada denuncia deja margen y los clientes usan el plan.", "warn": f"Hay {nv} {'punto' if nv == 1 else 'puntos'} a vigilar.", "bad": "La utilidad del período es negativa."}[e_gen]
    ico = ICONO
    k = [
        {"k": "neg_clientes_k", "i": "building-2", "l": "Clientes activos", "form": "none", "e": "warn" if riesgo else ("na" if sin_dato else "ok"), "v": str(len(activos)), "u": f"de {len(cls)}",
         "dots": [{"e": c["riesgo"], "n": f"{c['nombre']}: " + ("sin datos de uso" if c["riesgo"] == "na" else (f"hace {c['dias_sin_uso']} días" if c["dias_sin_uso"] is not None else "sin uso"))} for c in cls],
         "et": f"{len(riesgo)} en riesgo" if riesgo else (f"{len(sin_dato)} sin datos de uso" if sin_dato else "Todos usan Kerna"),
         "x": f"{len(activos)} de {len(cls)} clientes usaron Kerna en los últimos {neg_mod.DIAS_RIESGO} días. Solo se mide el uso de Veridy; de los demás clientes se conocen el plan y la tarifa. Cada círculo es un cliente."},
        {"k": "neg_denuncias_k", "i": "inbox", "l": "Denuncias recibidas", "form": "spark", "e": "ok" if t["denuncias"] else "na", "v": f.miles(t["denuncias"]), "u": f"en {n['dias']} días", "s": n["serie_total"],
         "et": "Con actividad" if t["denuncias"] else "Sin denuncias", "x": f"Se procesaron {f.miles(t['denuncias'])} denuncias entre todos los clientes en {n['dias']} días."},
        {"k": "neg_ingreso", "i": "wallet", "l": "Ingreso del período", "form": "none", "e": "ok" if t["ingreso"] > 0 else "na", "v": f.uf(t["ingreso"]), "u": "UF", "et": "Tarifa anual por los días",
         "x": f"Ingreso del período en UF: la tarifa anual de cada cliente, proporcional a los {n['dias']} días. Incluye las tarifas de los {len(cls)} clientes con contrato. 1 UF = {f.miles(n['uf_clp'])} pesos."},
        {"k": "neg_costo", "i": "coins", "l": "Costo de atención", "form": "none", "e": "ok", "v": f.uf(t["costo_servir"]), "u": "UF", "et": f"{f.uf(t['costo_ia'], 3)} UF de IA",
         "x": "Lo que cuesta atender a los clientes: inteligencia artificial (con tope por plan), infraestructura y soporte."},
        {"k": "neg_margen", "i": "piggy-bank", "l": "Ganancia sobre el ingreso", "form": "gauge", "e": e_mar, "v": f.dec_corto(mo, 0), "u": "%", "f": max(0, min(1, mo / 100)), "zm": .6, "zl": "60",
         "z": zonas([(0, .3, "bad"), (.3, .6, "warn"), (.6, 1, "ok")]), "tick": graficos.g_tick(.6), "et": "Alto" if e_mar == "ok" else ("Medio" if e_mar == "warn" else "Bajo"),
         "x": f"Lo que queda del ingreso ({f.uf(t['ingreso'])} UF) después de servir, pagar la parte de Veridy ({f.uf(t['participacion_veridy'])} UF) y los costos fijos ({f.uf(t['costos_fijos'])} UF): {f.uf(t['margen_operativo'])} UF."},
        {"k": "neg_utilidad", "i": "landmark", "l": "Utilidad del período", "form": "none", "e": "ok" if t["utilidad"] > 0 else ("bad" if t["utilidad"] < 0 else "na"), "v": f.uf(t["utilidad"]), "u": "UF",
         "et": f"{f.dec_corto(t['margen_neto_pct'], 0)} % del ingreso", "x": "Después de depreciación, interés del crédito e impuesto de primera categoría."},
        {"k": "neg_adopcion_k", "i": "thumbs-up", "l": "Sugerencias calificadas", "form": "bullet", "e": e_val, "v": f.dec_corto(a["valoradas_pct"], 0), "u": "%", "max": 100, "meta": 50, "metaT": "meta 50 %",
         "z": [{"a": 0, "b": 30, "e": "bad"}, {"a": 30, "b": 50, "e": "warn"}, {"a": 50, "b": 100, "e": "ok"}], "mx_txt": "100 %", "pos": min(100, a["valoradas_pct"]), "pos_meta": 50,
         "et": "Bien" if e_val == "ok" else ("Pocas" if e_val == "warn" else "Muy pocas"),
         "x": f"{f.miles(a['valoradas'])} sugerencias fueron valoradas por una persona; {f.dec_corto(a['utiles_pct'], 0)} % de ellas resultaron útiles. Esperado: 50 % o más."},
        {"k": "neg_sug", "i": "sparkles", "l": "Denuncias con sugerencia", "form": "none", "e": "ok" if a["con_sugerencia_pct"] >= SUG_OK else ("warn" if a["con_sugerencia_pct"] >= SUG_WARN else "bad"), "v": f.dec_corto(a["con_sugerencia_pct"], 1), "u": "%",
         "et": "Dentro de lo esperado" if a["con_sugerencia_pct"] >= SUG_OK else "Bajo lo esperado", "x": "De cada 100 denuncias, cuántas terminaron con una sugerencia lista."},
    ]
    for x in k:
        if x["form"] == "spark" and len(x["s"]) >= 4:
            x["d_l"], x["d_a"] = graficos.spark(x["s"]), graficos.spark_area(x["s"])
        elif x["form"] == "spark":
            x["form"] = "none"
        x.setdefault("p", "")
        x.setdefault("tr", "")
    clientes = []
    for c in cls:
        e_u = "na" if c["sin_uso"] else (c["estado_uso"] if c["riesgo"] != "bad" else "warn")
        nota = ("Sin datos de uso: solo se mide el uso de Veridy" if c["sin_uso"] else "Usó el plan al comienzo y luego se detuvo" if c["riesgo"] == "bad" and c["tot"] else "No registra denuncias en el período" if c["riesgo"] == "bad" else
                "Superó el plan: ofrecer un plan mayor" if c["uso_plan"] > 110 else "Cerca del límite del plan" if c["uso_plan"] > 90 else "Usa muy poco de lo contratado" if c["uso_plan"] < 30 else "Uso sano del plan")
        clientes.append({**c, "e_uso": e_u, "nota": nota, "spark": graficos.spark(c["serie"]),
                         "ult": "sin datos" if c["sin_uso"] else (("hace " + (f"{c['dias_sin_uso']} días" if c["dias_sin_uso"] else "menos de un día")) if c["ultimo_uso"] else "sin uso"),
                         "w_uso": min(100, c["uso_plan"] or 0)})
    embudo = [{"n": "Con sugerencia", "v": a["con_sugerencia_pct"], "e": "ok" if a["con_sugerencia_pct"] >= SUG_OK else "warn"},
              {"n": "Valoradas por auditores", "v": a["valoradas_pct"], "e": e_val},
              {"n": "Valoradas como útiles", "v": a["utiles_pct"], "e": "na" if not a["valoradas"] else ("ok" if a["utiles_pct"] >= 70 else "warn")}]
    nt = max(t["ingreso"], 1e-9)
    resultado = [("Ingreso del período", t["ingreso"], "ok", 100), ("Costo de servir", -t["costo_servir"], "na", 100 * t["costo_servir"] / nt),
                 ("Parte de Veridy", -t["participacion_veridy"], "na", 100 * t["participacion_veridy"] / nt), ("Costos fijos", -t["costos_fijos"], "na", 100 * t["costos_fijos"] / nt),
                 ("Margen operativo", t["margen_operativo"], "ok" if t["margen_operativo"] > 0 else "bad", 100 * abs(t["margen_operativo"]) / nt),
                 ("Depreciación e interés del crédito", -(t["depreciacion"] + t["interes"]), "na", 100 * (t["depreciacion"] + t["interes"]) / nt),
                 ("Impuesto", -t["impuesto"], "na", 100 * t["impuesto"] / nt), ("Utilidad después de impuestos", t["utilidad"], "ok" if t["utilidad"] > 0 else "bad", 100 * abs(t["utilidad"]) / nt)]
    resultado = [{"n": r[0], "v": f.uf(r[1]), "e": r[2], "w": round(min(100, r[3]), 1)} for r in resultado]
    anios = [{**x, "label": f"Año {x['anio']} ({x['calendario']})"} for x in p["anios"]]
    graf = {"clientes": {"labels": [f.fecha_corta(d) for d in n["dias_serie"]], "series": [{"n": c["nombre"], "d": c["serie"]} for c in cls if not c["sin_uso"]]},
            "proy": {"labels": [str(x["calendario"]) for x in p["anios"]], "ventas": [x["ventas"] for x in p["anios"]], "costos": [round(x["ventas"] - x["margen_operativo"], 2) for x in p["anios"]],
                     "utilidad": [x["utilidad"] for x in p["anios"]]}}
    return {"eg": {"e": e_gen, "t": {"ok": "Saludable", "warn": "Atención", "bad": "Problema"}[e_gen], "s": sub, "puntos": puntos}, "kpis": k, "clientes": clientes, "embudo": embudo,
            "resultado": resultado, "anios": anios, "graficos": graf, "n_uso": sum(1 for c in cls if not c["sin_uso"]),
            "con_uso": [c for c in clientes if not c["sin_uso"]], "sin_uso": [c for c in clientes if c["sin_uso"]], "dias": n["dias"], "veridy_pct": p["participacion_veridy_pct"]}



# ---------------------------------------------------------------------------------------------------------------------
import re as _re

_ISO = _re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ].*)?$")


def _celda(v, col: str = "") -> dict:
    """Celda de tabla legible: milisegundos a segundos, miles con punto, decimales con coma, fechas «11 nov», sí/no como chips."""
    if v is None:
        return {"t": "—", "n": True, "na": True}
    if col.endswith("(ms)") and isinstance(v, (int, float)) and not isinstance(v, bool):
        return {"t": f.segundos(v), "n": True}
    if isinstance(v, bool):
        return {"t": "sí" if v else "no", "n": False}
    if col in inf.COLS_PCT and isinstance(v, (int, float)):
        return {"t": f.dec_corto(100 * v, 1) + " %", "n": True}
    if isinstance(v, float):
        return {"t": f.dec_corto(v, 3), "n": True}
    if isinstance(v, int):
        return {"t": f.miles(v), "n": True}
    t = str(v)
    if _ISO.match(t) and col.lower().startswith(("día", "dia")):
        return {"t": f.fecha_corta(t), "n": False}
    return {"t": t, "n": False, "chip": "ok" if t == "sí" else "bad" if t == "no" else None}


def _fmt_g(v, fmt) -> str:
    return f.dec_corto(100 * v, 1) + " %" if fmt == "ratio" else (f.dec_corto(v, 4) if fmt == "usd" else f.miles(v))


def _meta_pos(g: dict):
    if not g.get("meta"):
        return None
    return round(100 * g["meta"] / (max([abs(v) for _, v in g["items"]] + [g["meta"]]) or 1), 1)


def _barras(g: dict) -> list[dict]:
    """Barras horizontales del informe: etiqueta corta (nombre completo en `full`), ancho en % y estado frente a la meta."""
    items = list(g["items"])
    mx = max([abs(v) for _, v in items] + [g.get("meta") or 0]) or 1
    out = []
    for et, v in items:
        e = "na"
        if g.get("meta"):
            e = "ok" if v >= g["meta"] else ("warn" if v >= g["meta"] - RECALL_ALERTA else "bad")
        full = inf.nombre_ley(et)
        out.append({"n": inf.ley_corta(et), "full": full, "v": _fmt_g(v, g.get("fmt")), "w": round(100 * abs(v) / mx, 1), "e": e})
    return out


def _tarjeta(k: str, i: str, l: str, v, u: str, e: str, x: str, **extra) -> dict:
    return {"k": k, "i": i, "l": l, "form": "none", "e": e, "p": "", "u": u, "v": "—" if v is None else v, "et": ESTADO_TXT[e], "tr": "", "te": "na", "ta": "minus", "x": x, **extra}


def informe_ejecutivo(inf_: dict) -> dict:
    """Panel del resumen ejecutivo: medidores con meta, modos en una barra apilada y casos por día."""
    sec = {s["id"]: s for s in inf_["secciones"]}
    kp = {}
    for s in inf_["secciones"]:
        for k in s["kpis"]:
            kp.setdefault(k["etiqueta"], k["valor"])
    casos = kp.get("Casos procesados") or 0
    ctx = {"casos": casos}
    est = lambda et: inf.estado_kpi(et, kp.get(et), ctx) or "na"  # noqa: E731
    dias = next((t["filas"] for t in sec["resumen"]["tablas"] if t["id"] == "casos_dia"), [])
    serie = [r[1] for r in dias]
    cards = []
    e_c = "ok" if casos else "na"
    cards.append(_tarjeta("casos", "inbox", "Denuncias", f.miles(casos), "", e_c, f"{f.miles(casos)} casos en Veridy.", form="spark", s=serie,
                          d_l=graficos.spark(serie), d_a=graficos.spark_area(serie), et="Normal" if casos else "Sin denuncias"))
    p_sug = kp.get("% con sugerencia")
    e_s = est("% con sugerencia")
    cards.append(_tarjeta("neg_sug", "sparkles", "Denuncias con sugerencia", None if not casos else f.dec_corto(p_sug, 1), "%", e_s if casos else "na", "De cada 100 denuncias, cuántas terminaron con una sugerencia lista. Meta: 90 % o más.",
                          form="gauge", f=(p_sug or 0) / 100, zm=.9, zl="90", z=zonas([(0, .7, "bad"), (.7, .9, "warn"), (.9, 1, "ok")]), tick=graficos.g_tick(.9),
                          et={"ok": "Dentro de lo esperado", "warn": "Bajo lo esperado", "bad": "Muy bajo", "na": "Sin datos"}[e_s if casos else "na"]))
    rc = kp.get("Recall@5 por artículo (global)")
    meta_r = kp.get("Meta de recall@5") or META_RECALL
    e_r = est("Recall@5 por artículo (global)")
    cards.append(_tarjeta("calidad", "target", "Acierto", None if rc is None else f.dec_corto(100 * rc, 1), "%" if rc is not None else "", e_r, f"Cuando existe un artículo correcto, Kerna lo incluye entre sus 5 primeras sugerencias con esta frecuencia. Meta: {f.dec_corto(100 * meta_r, 0)} %.",
                          sub=SET_PANEL if rc is not None else "", form="gauge", f=rc or 0, zm=meta_r, zl=f.dec_corto(100 * meta_r, 0), z=zonas([(0, meta_r - RECALL_ALERTA, "bad"), (meta_r - RECALL_ALERTA, meta_r, "warn"), (meta_r, 1, "ok")]),
                          tick=graficos.g_tick(meta_r), et={"ok": "Cumple la meta", "warn": "Cerca de la meta", "bad": "Bajo la meta", "na": "Sin datos"}[e_r]))
    pv = kp.get("% de sugerencias valoradas útiles")
    e_v = est("% de sugerencias valoradas útiles")
    cards.append(_tarjeta("valoraciones", "thumbs-up", "Sugerencias útiles", None if pv is None else f.dec_corto(pv, 0), "%" if pv is not None else "", e_v, "De las sugerencias valoradas por auditores, cuántas resultaron útiles. Esperado: 70 % o más.",
                          form="bullet" if pv is not None else "none", max=100, meta=70, metaT="meta 70 %", z=[{"a": 0, "b": 50, "e": "bad"}, {"a": 50, "b": 70, "e": "warn"}, {"a": 70, "b": 100, "e": "ok"}], mx_txt="100 %", pos=min(100, pv or 0), pos_meta=70,
                          et={"ok": "Bien", "warn": "Atención", "bad": "Bajo", "na": "Sin valoraciones"}[e_v]))
    p95 = kp.get("Latencia P95 (máximo diario)")
    e_p = est("Latencia P95 (máximo diario)")
    mx = 3 * META_P95_S
    cards.append(_tarjeta("tiempo", "timer", "Respuesta", None if p95 is None else f.segundos(p95), "s" if p95 is not None else "", e_p, f"9 de cada 10 casos reciben su sugerencia en menos de este tiempo (el peor día). Meta: {f.dec_corto(META_P95_S, 0)} s.",
                          form="bullet", max=mx, meta=META_P95_S, metaT=f"meta {f.dec_corto(META_P95_S, 0)} s", z=[{"a": 0, "b": META_P95_S, "e": "ok"}, {"a": META_P95_S, "b": 2 * META_P95_S, "e": "warn"}, {"a": 2 * META_P95_S, "b": mx, "e": "bad"}],
                          mx_txt=f"{f.dec_corto(mx, 0)} s", pos=min(100, (p95 or 0) / 1000 / mx * 100), pos_meta=META_P95_S / mx * 100, et={"ok": "Dentro de la meta", "warn": "Sobre la meta", "bad": "Muy sobre la meta", "na": "Sin datos"}[e_p]))
    ctotal = kp.get("Costo del período")
    cards.append(_tarjeta("costo_k", "coins", "Costo", None if ctotal is None else f.usd(ctotal), "", "na" if ctotal is None else "ok",
                          "Lo que cuesta atender las denuncias del período, según los tokens de cada modelo y su precio." if ctotal is not None else "No hay tokens medidos en el período.", et="Sin alertas" if ctotal is not None else "Sin datos", p="US$" if ctotal is not None else ""))
    n_modos = [("oficial", "Modelo principal", "ok", kp.get("Modo oficial") or 0), ("respaldo", "Modelo de respaldo", "warn", kp.get("Modo respaldo") or 0),
               ("local", "Modelo local", "warn", kp.get("Modo local (gemma)") or 0), ("manual", "Revisión manual", "bad", kp.get("Revisión manual") or 0)]
    tot = sum(n for *_, n in n_modos)
    modos = [{"k": k, "t": t, "e": e, "n": n, "p": pct(n, tot), "w": round(100 * n / tot, 1) if tot else 0, "est": est("Revisión manual") if k == "manual" else ("ok" if k == "oficial" else est("Modo respaldo"))} for k, t, e, n in n_modos]
    return {"tarjetas": cards, "modos": modos, "n_modos": tot, "dias": [{"d": f.fecha_corta(str(r[0])), "c": f.miles(r[1]), "s": f.miles(r[2])} for r in dias]}


def informe(inf_: dict) -> list[dict]:
    """Secciones del informe listas para la plantilla (copia: las descargas XLSX, CSV y PDF no cambian)."""
    out = []
    kp_all = {k["etiqueta"]: k["valor"] for s in inf_["secciones"] for k in s.get("kpis", [])}
    ctx = {"casos": kp_all.get("Casos procesados") or 0, "meta_recall": kp_all.get("Meta de recall@5")}
    for s in inf_["secciones"]:
        kp = []
        for k in s.get("kpis", []):
            v, u = k["valor"], k["unidad"]
            if v is None:
                txt = "—"
            elif u == "ms" and isinstance(v, (int, float)):
                txt, u = f.segundos(v), "s"
            elif isinstance(v, float) and u == "ratio" and inf.es_kpi_pct(k["etiqueta"]):
                txt, u = f.dec_corto(100 * v, 1), "%"
            elif isinstance(v, float) and u == "ratio":
                txt = f.dec_corto(v, 3)
            elif isinstance(v, float):
                txt = f.dec_corto(v, 4)
            elif isinstance(v, int) and not isinstance(v, bool):
                txt = f.miles(v)
            else:
                txt = str(v)
            e = inf.estado_kpi(k["etiqueta"], v, ctx)
            if txt in ("sí", "no"):
                e = "ok" if txt == "sí" else "bad"
            kp.append({"etiqueta": _re.sub(r" \(\d+ días hasta [\d-]+\)", "", k["etiqueta"]).replace("(ms)", "").replace("  ", " "), "v": txt, "u": u if v is not None and u not in ("casos", "ratio", "valoraciones", "pruebas") else "", "fuente": k["fuente"], "e": e})
        gr = []
        for g in s.get("graficos", []):
            if g["titulo"] in ("Casos por modo", "Casos procesados por día"):  # los resume el panel ejecutivo
                continue
            ms = g["titulo"].endswith("(ms)")
            g2 = {**g, "items": [(a, round(b / 1000, 1) if ms else b) for a, b in g["items"]], "titulo": g["titulo"].replace("(ms)", "(segundos)") if ms else g["titulo"]}
            if not any(v for _, v in g2["items"]):
                continue
            if g.get("fmt") == "ratio" and g.get("meta") is not None:  # la meta se muestra como 80 %, no como 0,8
                g2["titulo"] = _re.sub(r"\(meta [\d,.]+\)", f"(meta {f.dec_corto(100 * g['meta'], 0)} %)", g2["titulo"])
            gr.append({"titulo": g2["titulo"], "barras": _barras(g2), "meta": g.get("meta"), "meta_pos": _meta_pos(g2)})
        tb = []
        for t in s.get("tablas", []):
            if t["titulo"] in ("Casos por día", "Casos en revisión manual por motivo", "Artículos sugeridos por ley"):  # ya están en el panel o en el gráfico de la sección
                continue
            if not t["filas"]:  # sin filas no hay nada que mostrar: la nota de la sección lo explica
                continue
            filas = [[_celda(v, c) for v, c in zip(fila, t["cols"])] for fila in t["filas"]]
            cols = [c.replace("(ms)", "(s)") for c in t["cols"]]
            nums = [bool(filas) and all(r[i]["n"] for r in filas) for i in range(len(cols))]
            largo = len(filas) > 12 and len(cols) <= 3
            n = -(-len(filas) // 3) if largo else 0
            tb.append({"titulo": t["titulo"].replace("(ms)", "(s)"), "cols": cols, "nums": nums, "fuente": t["fuente"], "filas": filas, "trozos": [filas[i:i + n] for i in range(0, len(filas), n)] if largo else None})
        out.append({"id": s["id"], "titulo": s["titulo"], "justificacion": "", "kpis": kp, "graficos": gr, "tablas": tb, "notas": s.get("notas", [])})
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# Informe de gestión en pantalla (v2): KPI con estado y tendencia, veredicto de una línea, pestañas con gráficos compactos.
# Las tablas no van en el cuerpo: están en la pestaña «Datos» (plantilla informe_datos.html) y en XLSX/CSV.
# ---------------------------------------------------------------------------------------------------------------------------------
TIPOS_DATO = {"DIRECCION": "Dirección", "GENERO": "Género", "UBICACION": "Ubicación", "N_CAUSA": "N.º de causa", "EMPRESA_INSTITUCION": "Empresa o institución",
              "CORREO": "Correo", "RUT": "RUT", "CARGO": "Cargo", "EDAD": "Edad", "FINANCIERO": "Dato financiero", "NACIONALIDAD": "Nacionalidad", "PERSONA": "Nombre de persona", "SALUD": "Salud"}
PESTANAS = [  # id, título, ícono utilitario, glosario, KPI de la pestaña (etiqueta del informe, rótulo claro)
    ("resumen", "Resumen", "layout-dashboard", "inf_resumen", [("Disponibilidad efectiva", "Casos con sugerencia sobre los válidos"), ("% de sugerencias valoradas útiles", "Sugerencias útiles"), ("Revisión manual", "En revisión manual")]),
    ("calidad", "Calidad", "target", "inf_calidad", [("Recall@5 por artículo (global)", "Acierto con el artículo exacto"), ("Recall por ley (global)", "Acierto con la ley"), ("Pruebas automáticas (unitarias): pasadas/total", "Pruebas automáticas pasadas")]),
    ("desempeno", "Rapidez", "timer", "inf_desempeno", [("Latencia P50 (ponderada por día)", "Tiempo típico de un caso"), ("Latencia P95 (máximo diario)", "9 de 10 casos, peor día"), ("Casos fuera del modo oficial", "Con respaldo o manual")]),
    ("costo", "Costos", "coins", "inf_costo", [("Costo del período", "Costo del período"), ("Costo por denuncia", "Costo por denuncia"), ("Costo total mensual proyectado, 1.000 denuncias", "Costo por 1.000 denuncias")]),
    ("rentabilidad", "Rentabilidad", "wallet", "inf_rent", [("Ingreso del período", "Ingreso del período"), ("Margen operativo", "Ganancia sobre el ingreso"), ("Utilidad después de impuestos", "Utilidad del período"), ("Retorno anual del proyecto", "Rentabilidad anual")]),
    ("incidentes", "Incidentes", "triangle-alert", "inf_incid", [("Casos en revisión manual", "En revisión manual"), ("Eventos de falla de proveedor o modelo", "Fallas de proveedores")]),
]


def _tendencia(serie: list[float], menos_es_mejor: bool | None, unidad: str = "%", pts: bool = False) -> dict:
    """Mitad final frente a mitad inicial de una serie: texto, estado de la tendencia y flecha."""
    s = [float(x) for x in serie if x is not None]
    if len(s) < 4:
        return {"tr": "", "te": "na", "ta": "minus"}
    m = len(s) // 2
    a, b = sum(s[:m]) / m, sum(s[m:]) / (len(s) - m)
    d = (b - a) if pts else ((100 * (b - a) / a) if a else 0)
    if abs(d) < (0.5 if pts else 3):
        return {"tr": "estable", "te": "na", "ta": "minus"}
    sube = d > 0
    te = "na" if menos_es_mejor is None else ("ok" if sube != menos_es_mejor else "bad")
    return {"tr": ("+" if sube else "−") + ("más de 200" if abs(d) > 200 and not pts else f.dec_corto(abs(d), 0 if abs(d) >= 10 else 1)) + (" pts" if pts else " %"), "te": te, "ta": "trending-up" if sube else "trending-down"}


def _tabla(inf_: dict, id_: str) -> dict | None:
    return next((t for s in inf_["secciones"] for t in s["tablas"] if t["id"] == id_), None)


def _pct_stat(v, u) -> float | None:
    """Porcentaje (0 a 100) de una cifra del informe para dibujar su anillo: «49,2» con «%» o «333/333»; None si no es una proporción."""
    try:
        t = str(v).strip()
        if "/" in t:
            a, b = (float(x.replace(".", "").replace(",", ".")) for x in t.split("/", 1))
            return 100 * a / b if b else None
        if str(u).strip() == "%":
            return float(t.replace(".", "").replace(",", "."))
    except ValueError:
        return None
    return None


def informe_v2(inf_: dict) -> dict:
    ej = informe_ejecutivo(inf_)
    cd = _tabla(inf_, "casos_dia")
    ld = _tabla(inf_, "lat_dia")
    rs = _tabla(inf_, "recall_serie")
    s_casos = [r[1] for r in cd["filas"]] if cd else []
    s_sug = [100 * r[2] / r[1] for r in cd["filas"] if r[1]] if cd else []
    s_p95 = [r[3] / 1000 for r in ld["filas"]] if ld else []
    s_rec = [100 * r[2] for r in sorted(rs["filas"], key=lambda r: str(r[0]))] if rs and rs["filas"] else []
    extra = {
        "casos": (s_casos, None, False, "Cantidad de denuncias de Veridy"), "neg_sug": (s_sug, False, True, "meta 90 % o más"),
        "calidad": (s_rec, False, True, f"meta {f.dec_corto(100 * META_RECALL, 0)} % o más"), "valoraciones": ([], None, False, "meta 70 % o más"),
        "tiempo": (s_p95, True, False, f"meta {f.dec_corto(META_P95_S, 0)} s o menos"), "costo_k": ([], None, False, "según tokens y precios"),
    }
    nombres = {"casos": "Denuncias recibidas", "neg_sug": "Denuncias con sugerencia", "calidad": "Sugerencias acertadas", "valoraciones": "Sugerencias útiles", "tiempo": "Tiempo de respuesta", "costo_k": "Costo del período"}
    cards = []
    for c in ej["tarjetas"]:
        serie, menos, pts, meta = extra[c["k"]]
        tr = _tendencia(serie, menos, pts=pts) if serie else {"tr": "", "te": "na", "ta": "minus"}
        d = {"d_l": graficos.spark(serie), "d_a": graficos.spark_area(serie)} if len(serie) >= 4 else {}
        cards.append({"k": c["k"], "i": c["i"], "l": nombres[c["k"]], "v": c["v"], "u": c["u"], "p": c["p"], "e": "na" if c["k"] == "costo_k" else c["e"], "et": "" if c["k"] == "costo_k" else c["et"], "meta": meta, "x": c["x"], "sub": c.get("sub", ""), **tr, **d, **{k2: c[k2] for k2 in ("form", "z", "f", "zm", "zl", "max", "pos", "pos_meta", "metaT") if k2 in c}})
    mal = [c for c in cards if c["e"] == "bad"]
    atencion = [c for c in cards if c["e"] == "warn"]
    con_meta = [c for c in cards if c["e"] != "na" and c["k"] not in ("casos", "costo_k")]
    n_ok = sum(1 for c in con_meta if c["e"] == "ok")
    corto = {"neg_sug": "sugerencia", "calidad": "acierto", "valoraciones": "sugerencias útiles", "tiempo": "respuesta"}
    fuera = [corto.get(c["k"], c["l"].lower()) for c in con_meta if c["e"] != "ok"]
    falta = ""
    if not con_meta:
        e_v, ico, frase = "na", "sin-info", "Sin datos en el período"
    elif not fuera:
        e_v, ico, frase = "ok", "lista", f"{n_ok} de {len(con_meta)} metas cumplidas"
    else:
        e_v = "bad" if n_ok == 0 else "warn"
        ico = "cadena-agotada" if n_ok == 0 else "contingencia-modelo"
        lista = ", ".join(fuera[:-1]) + (" y " if len(fuera) > 1 else "") + fuera[-1]
        frase = f"{n_ok} de {len(con_meta)} metas cumplidas"
        falta = ("Bajo la meta: " if n_ok == 0 or e_v == "bad" else "Por mejorar: ") + lista
    veredicto = {"e": e_v, "ico": ico, "t": frase, "n": falta}

    kp = {k["etiqueta"]: k for s in vistas_informe_cache(inf_) for k in s["kpis"]}
    vis = informe_vis(inf_, kp)
    pestanas = []
    for id_, titulo, ico, g, items in PESTANAS:
        if id_ == "resumen":
            continue
        stats = []
        for et, rot in items[:3]:
            k = kp.get(et)
            if k:
                stats.append({"l": rot, "v": k["v"], "u": k["u"], "e": k["e"] or "n", "pct": _pct_stat(k["v"], k["u"])})
        pestanas.append({"id": id_, "t": titulo, "i": ico, "g": g, "stats": stats, "vis": vis.get(id_)})
    kbs = [_kb(c) for c in cards]
    charts = informe_charts(inf_)
    return {"cards": cards, "kb": kbs, "veredicto": veredicto, "pestanas": pestanas, "charts": {k: v for k, v in charts.items() if k == "rentabilidad"}, "hay_proy": bool(charts.get("rentabilidad"))}


def _corto_n(v: float) -> str:
    return f.dec_corto(v / 1e6, 1) + " M" if v >= 1e6 else (f.dec_corto(v / 1e3, 0) + " mil" if v >= 1e4 else f.miles(round(v)))


def _ley_n(n: str) -> str:
    """Etiqueta de ley en dos partes («Ley 21.643 · Ley Karin»): en móvil la segunda baja a otra línea."""
    a, _, b = str(n).partition(" · ")
    return f'<span class="ly-n">{_e(a)}' + (f'<em> · </em><span>{_e(b)}</span>' if b else "") + "</span>"


def informe_vis(inf_: dict, kp: dict) -> dict:
    """Una visualización protagonista por pestaña del informe, con el lenguaje orbital (HTML o SVG del servidor)."""
    out: dict = {}
    sin = lambda t: _M(f'<p class="vac">{graficos.icono("e-sin-info", px=18, mini=True)}<span>{_e(t)}</span> <b>—</b></p>')  # noqa: E731
    rl = _tabla(inf_, "recall_ley")
    if rl and rl["filas"]:
        li = []
        meta = (rl["filas"][0][7] or META_RECALL)
        for r in rl["filas"]:
            v = r[4]
            e = "ok" if v >= (r[7] or META_RECALL) else ("warn" if v >= (r[7] or META_RECALL) - RECALL_ALERTA else "bad")
            li.append(f'<li class="ly s-{e}" title="{_e(inf.nombre_ley(r[0]))}">{_o.ley_icono(inf.nombre_ley(r[0]), 32) or _M('<span class="lx" data-l="global" style="--s:32px" aria-hidden="true">' + str(graficos.icono("acierto", px=32)) + "</span>")}{_o.anillo(100 * v, e, 100 * meta, 64, f.dec_corto(100 * v, 1) + "%")}{_ley_n(inf.ley_corta(r[0]))}</li>')
        out["calidad"] = _M(f'<p class="mk">Acierto por ley<span class="mk-r">meta {f.dec_corto(100 * meta, 0)} %</span></p><ul class="ly-l">{"".join(li)}</ul>')
    else:
        out["calidad"] = sin("Sin medición de calidad")
    le = _tabla(inf_, "lat_etapa")
    if le and le["filas"]:
        mx = max(r[3] for r in le["filas"])
        sat = [{"n": ETAPA_CORTA.get(str(r[0]), str(r[0]).capitalize()), "v": r[3], "txt": f.segundos(r[3]) + " s", "c": _o.COLOR_ETAPA.get(str(r[0]), "azul"), "hot": r[3] == mx} for r in le["filas"]]
        out["desempeno"] = _M(f'<p class="mk">El camino de una denuncia<span class="mk-r">9 de 10 casos · meta {f.dec_corto(META_P95_S, 0)} s</span></p>{_o.camino(sat)}')
    else:
        out["desempeno"] = sin("Sin tiempos por etapa")
    tl = _tabla(inf_, "tokens_modelo")
    if tl and tl["filas"]:
        anillos = [{"n": str(r[0]), "v": r[2] + r[3], "txt": _corto_n(r[2] + r[3]), "c": _o.CICLO[i % len(_o.CICLO)]} for i, r in enumerate(tl["filas"][:4])]
        ck = kp.get("Costo del período")
        out["costo"] = _M(f'<p class="mk">Costo por modelo<span class="mk-r">arco = parte de los tokens</span></p><div class="pr-d">{_o.diagrama_orbital(anillos, ("US$ " + ck["v"]) if ck else "—", "costo del período")}</div>')
    else:
        out["costo"] = sin("Sin tokens medidos")
    fl = _tabla(inf_, "fallas")
    rv = _tabla(inf_, "revision")
    if fl and fl["filas"]:
        agg: dict[str, int] = {}
        for r in fl["filas"]:
            agg[str(r[1])] = agg.get(str(r[1]), 0) + int(r[4])
        nom = {"generacion": "Redacción", "recuperacion": "Búsqueda", "voyage": "Voyage AI", "gemini": "Gemini", "local": "Modelo local", "azure": "Azure OpenAI"}
        it = sorted(agg.items(), key=lambda x: -x[1])
        sat = [{"n": nom.get(a, a.capitalize()), "v": b, "txt": f.miles(b), "c": _o.CICLO[i % len(_o.CICLO)], "hot": i == 0} for i, (a, b) in enumerate(it)]
        h = f'<p class="mk">Fallas por proveedor<span class="mk-r">tamaño = eventos</span></p>{_o.camino(sat)}'
    else:
        h = f'<p class="vac">{graficos.icono("e-lista", px=24, mini=True)}<span>Sin fallas de proveedor en el período</span></p>'
    if rv and rv["filas"]:
        h += '<ul class="ch-l">' + "".join(f'<li>{graficos.icono(motivo_ico(str(r[0]).replace("_", " "), False), px=20, mini=True)}<span>{_e(str(r[0]).replace("_", " ").capitalize())}</span><b>{f.miles(r[1])}</b></li>' for r in rv["filas"][:5]) + "</ul>"
    out["incidentes"] = _M(h)
    return out


def vistas_informe_cache(inf_: dict) -> list[dict]:
    return informe(inf_)


def informe_charts(inf_: dict) -> dict:
    """Especificaciones de gráficos por pestaña, en datos simples; kerna.js las convierte en ECharts (canvas) al abrir la pestaña."""
    T = lambda i: _tabla(inf_, i)  # noqa: E731
    out: dict[str, list] = {p[0]: [] for p in PESTANAS}
    cd = T("casos_dia")
    if cd and any(r[1] for r in cd["filas"]):
        out["resumen"].append({"id": "g-casos", "t": "Denuncias por día", "g": "casos_dia", "kind": "bar", "stack": True, "cats": [f.fecha_corta(str(r[0])) for r in cd["filas"]],
                               "series": [{"n": "Con sugerencia", "d": [r[2] for r in cd["filas"]], "c": "ok"}, {"n": "Sin sugerencia", "d": [r[1] - r[2] for r in cd["filas"]], "c": "bad"}]})
    ej = informe_ejecutivo(inf_)
    if ej["n_modos"]:
        col = {"oficial": "pro", "respaldo": "warn", "local": "na", "manual": "bad"}
        out["resumen"].append({"id": "g-modos", "t": "Cómo se resolvieron", "g": "modos", "kind": "donut", "unit": "", "cn": "casos", "items": [{"n": m["t"], "v": m["n"], "c": col[m["k"]]} for m in ej["modos"] if m["n"]]})
    rl = T("recall_ley")
    if rl and rl["filas"]:
        out["calidad"].append({"id": "g-recall", "t": "Acierto por ley", "g": "acierto_ley", "kind": "bar", "h": True, "unit": " %", "meta": {"v": round(100 * (rl["filas"][0][7] or META_RECALL)), "t": "Meta"},
                               "cats": [inf.ley_corta(r[0]) for r in rl["filas"]], "full": [inf.nombre_ley(r[0]) for r in rl["filas"]],
                               "series": [{"n": "Acierto", "d": [round(100 * r[4], 1) for r in rl["filas"]], "cs": ["ok" if r[4] >= (r[7] or META_RECALL) else ("warn" if r[4] >= (r[7] or META_RECALL) - RECALL_ALERTA else "bad") for r in rl["filas"]]}]})
    rs = T("recall_serie")
    if rs and len(rs["filas"]) > 1:
        fr = sorted(rs["filas"], key=lambda r: str(r[0]))
        un_dia = len({str(r[0])[:10] for r in fr}) == 1  # misma fecha: solo la hora en el eje, la fecha va en el título
        out["calidad"].append({"id": "g-serie", "t": "Acierto por medición" + (f" ({f.fecha_corta(str(fr[0][0])[:10])})" if un_dia else ""), "g": "inf_serie", "kind": "line", "unit": " %", "meta": {"v": round(100 * META_RECALL), "t": "Meta"},
                               "cats": [(str(r[0])[11:16] if un_dia else f.fecha_corta(str(r[0])[:10]) + " " + str(r[0])[11:16]) for r in fr], "series": [{"n": "Acierto", "d": [round(100 * r[2], 1) for r in fr], "c": "pro", "area": True}]})
    an = T("anonimizador")
    if an and an["filas"]:
        out["calidad"].append({"id": "g-anon", "t": "Datos personales ocultados", "g": "inf_anon", "kind": "bar", "h": True, "unit": " %", "cats": [TIPOS_DATO.get(str(r[0]).upper(), str(r[0]).replace("_", " ").capitalize()) for r in an["filas"]],
                               "series": [{"n": "Ocultados", "d": [round(100 * r[3]) for r in an["filas"]], "cs": ["ok" if r[3] >= .9 else ("warn" if r[3] >= .6 else "bad") for r in an["filas"]]}]})
    ld = T("lat_dia")
    if ld and ld["filas"]:
        out["desempeno"].append({"id": "g-lat", "t": "Tiempo de respuesta por día", "g": "latencia", "kind": "line" if len(ld["filas"]) >= 4 else "bar", "unit": " s", "meta": {"v": META_P95_S, "t": "Meta"}, "cats": [f.fecha_corta(str(r[0])) for r in ld["filas"]],
                                 "series": [{"n": "9 de cada 10 casos", "d": [round(r[3] / 1000, 1) for r in ld["filas"]], "c": "na", "area": True}, {"n": "Caso típico", "d": [round(r[2] / 1000, 1) for r in ld["filas"]], "c": "pro", "area": True}]})  # con menos de 4 días, barras agrupadas
    le = T("lat_etapa")
    if le and le["filas"]:
        out["desempeno"].append({"id": "g-etapa", "t": "¿Dónde se va el tiempo?", "g": "etapas", "kind": "bar", "h": True, "unit": " s", "cats": [ETAPAS.get(str(r[0]), str(r[0]).capitalize()) for r in le["filas"]],
                                 "series": [{"n": "9 de cada 10 casos", "d": [round(r[3] / 1000, 1) for r in le["filas"]], "c": "pro"}]})
    tm = T("tokens_modo")
    if tm and tm["filas"]:
        out["costo"].append({"id": "g-tokmodo", "t": "Tokens por modo", "g": "inf_tokens", "kind": "donut", "unit": "", "cn": "tokens", "items": [{"n": str(r[0]).capitalize(), "v": r[2] + r[3], "c": {"oficial": "pro", "respaldo": "warn", "local": "na", "manual": "bad"}.get(str(r[0]), "na")} for r in tm["filas"]]})
    tl = T("tokens_modelo")
    if tl and tl["filas"]:
        out["costo"].append({"id": "g-tokmod", "t": "Tokens por modelo", "g": "inf_tokens", "kind": "bar", "h": True, "stack": True, "unit": "", "cats": [str(r[0]) for r in tl["filas"]],
                             "series": [{"n": "Entrada", "d": [r[2] for r in tl["filas"]], "c": "pro"}, {"n": "Salida", "d": [r[3] for r in tl["filas"]], "c": "na"}]})
    rp = T("rent_proyeccion")
    if rp and rp["filas"]:
        out["rentabilidad"].append({"id": "g-proy", "t": "Utilidad por año (proyección)", "g": "proyeccion", "kind": "bar", "unit": " UF", "cats": [str(r[0]).split(" ")[0] and "Año " + str(r[0]).split(" ")[0] for r in rp["filas"]],
                                    "series": [{"n": "Utilidad después de impuestos", "d": [r[7] for r in rp["filas"]], "cs": ["ok" if r[7] > 0 else "bad" for r in rp["filas"]]}]})
    rc = T("rent_clientes")
    if rc and rc["filas"]:
        out["rentabilidad"].append({"id": "g-cli", "t": "Margen por cliente", "g": "inf_rent", "kind": "bar", "h": True, "stack": True, "unit": " UF", "cats": [str(r[0]) for r in rc["filas"]],
                                    "series": [{"n": "Costo de servir", "d": [r[5] for r in rc["filas"]], "c": "na"}, {"n": "Margen", "d": [r[6] for r in rc["filas"]], "c": "ok"}]})
    rv = T("revision")
    if rv and rv["filas"]:
        out["incidentes"].append({"id": "g-rev", "t": "Revisión manual en el período: motivos", "g": "inf_incid", "kind": "bar", "h": True, "unit": "", "cats": [str(r[0]).replace("_", " ").capitalize() for r in rv["filas"]],
                                  "series": [{"n": "Casos", "d": [r[1] for r in rv["filas"]], "c": "bad"}]})
    fl = T("fallas")
    if fl and fl["filas"]:
        agg: dict[str, int] = {}
        for r in fl["filas"]:
            agg[str(r[1])] = agg.get(str(r[1]), 0) + int(r[4])
        it = sorted(agg.items(), key=lambda x: -x[1])
        out["incidentes"].append({"id": "g-fallas", "t": "Fallas por proveedor", "g": "inf_incid", "kind": "bar", "h": True, "unit": "", "cats": [{"generacion": "Redacción", "recuperacion": "Búsqueda", "voyage": "Voyage AI", "gemini": "Gemini", "local": "Modelo local"}.get(a, a.capitalize()) for a, _ in it], "series": [{"n": "Eventos", "d": [b for _, b in it], "c": "warn"}]})
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# Presentación v6 (dirección de diseño: kerna/front/diseno-v2/direccion-diseno.md): frases titulares, diagramas orbitales y bandas de KPI.
# Todo se arma con reglas a partir de los datos; no interviene ningún modelo.
# ---------------------------------------------------------------------------------------------------------------------------------
from markupsafe import Markup as _M, escape as _e
from . import orbital as _o

MODO_CORTO = {"oficial": "Principal", "respaldo": "Respaldo", "local": "Modelo local", "manual": "Revisión manual"}
MODO_PERIODO = {**MODO_CORTO, "manual": "Revisión manual"}  # el Resumen cuenta lo ocurrido en el período, no lo que sigue pendiente
ETAPA_CORTA = {"anonimizacion": "Anonimizar", "clasificacion": "Clasificar", "recuperacion": "Buscar en la ley", "generacion": "Redactar", "validacion": "Verificar citas"}
ICONO_KPI = {"casos": "denuncias", "calidad": "acierto", "tiempo": "tiempo", "costo_k": "costo", "neg_sug": "e-lista", "valoraciones": "e-valorada", "valoradas": "e-valorada",
             "neg_margen": "margen", "neg_costo": "costo", "neg_adopcion_k": "e-valorada", "neg_ingreso": "ingresos", "neg_utilidad": "utilidad"}


def motivo_ico(texto: str, se_reintenta: bool) -> str:
    """Ilustración de estado del motivo de un caso en espera."""
    t = str(texto).lower()
    if "no estaban disponibles" in t or "no disponible" in t:
        return "e-nucleo-no-disponible"
    if "tard" in t or "plazo" in t or "tiempo" in t:
        return "e-revision-tiempo"
    if "cita" in t:
        return "e-revision-citas"
    return "e-contingencia-modelo" if se_reintenta else "e-cadena-agotada"


def _em(e: str, txt: str) -> _M:
    return _M(f'<em class="s-{e}">{_e(txt)}</em>')


def _barra(k: dict) -> dict | None:
    """Barra bala de 120 px de un indicador: zonas por estado, posición del valor y marca de la meta."""
    if k["form"] == "gauge" and k.get("z"):
        return {"z": [{"w": round(100 * (z["b"] - z["a"]), 1), "e": z["e"]} for z in k["z"]], "pos": round(100 * k["f"], 1), "meta": round(100 * k["zm"], 1), "t": f"meta {k['zl']} %"}
    if k["form"] == "bullet" and k.get("z"):
        mx = k["max"] or 1
        return {"z": [{"w": round(100 * (z["b"] - z["a"]) / mx, 1), "e": z["e"]} for z in k["z"]], "pos": round(k["pos"], 1), "meta": round(k["pos_meta"], 1), "t": k["metaT"]}
    return None


SET_PANEL = "Set desarrollo"  # rótulo del set que mide la banda de calidad (evaluaciones.SET)


def _kb(k: dict, sub: str = "") -> dict:
    return {"k": k["k"], "ic": ICONO_KPI.get(k["k"], k.get("i", "resumen")), "l": k["l"], "v": k["v"], "u": k.get("u", ""), "p": k.get("p", ""), "e": k["e"], "et": k.get("et", ""),
            "bar": _barra(k), "sub": sub or k.get("sub", ""), "x": k.get("x", "")}


def presentacion_resumen(V: dict, rei: dict | None, dias: int) -> dict:
    tot = V["total"]
    nrei = rei["r"]["reintentables"] if rei else 0
    prov_mal = [p for p in V["proveedores"] if p["e"] == "bad"]
    if not tot:
        frase = _M(f"Sin denuncias en estos {dias} días.")
    else:
        pa = [_M(f"{_em(V['e_sug'], str(V['sug_pct']) + ' %')} recibió sugerencia." if V.get("sug_real") else f"En {dias} días, {_em(V['e_sug'], str(V['sug_pct']) + ' %')} recibió sugerencia.")]
        if rei:
            if nrei:
                pa.append(_M(f"{_em('warn', f.miles(nrei))} {'caso espera' if nrei == 1 else 'casos esperan'} reintento."))
        if prov_mal:
            pa.append(_M(f"{_em('bad', prov_mal[0]['nombre'])} está caído."))
        if V["eg"]["e"] == "ok":
            pa.append(_M("Todo dentro de las metas."))
        frase = _M(" ".join(pa))
    colores = {"oficial": "verde", "respaldo": "amarillo", "local": "cian", "manual": "coral"}
    anillos = [{"n": MODO_PERIODO[m["k"]], "v": m["n"], "txt": f.miles(m["n"]), "c": colores[m["k"]]} for m in V["modos"] if m["n"]]
    diag = _o.diagrama_orbital(anillos, f.miles(tot), "denuncias", f"{f.miles(tot)} denuncias en {dias} días por modo") if tot else None
    kb = []
    kp = {k["k"]: k for k in V["kpis"]}
    for key in ("calidad", "tiempo"):
        kb.append(_kb(kp[key], sub=SET_PANEL if key == "calidad" and V.get("con_recall") else ""))
    c = kp["costo_k"]
    kb.append(_kb(c, sub=(f"US$ {V['costo']['por_caso']} por denuncia" if V.get("costo") else "")))
    vv = {x["t"]: x for x in V["valoraciones"]}
    n_val = V["n_val"]
    util = vv.get("Útil", {}).get("p")
    e_v = "na" if not n_val else ("ok" if util >= 70 else ("warn" if util >= 50 else "bad"))
    kb.append({"k": "valoradas", "g": "valoraciones", "ic": "e-valorada", "l": "Sugerencias útiles", "v": "—" if not n_val else str(util), "u": "" if not n_val else "%", "p": "", "e": e_v,
               "et": "Sin valoraciones" if not n_val else {"ok": "Bien", "warn": "Atención", "bad": "Bajo"}[e_v], "bar": None if not n_val else {"z": [{"w": 50, "e": "bad"}, {"w": 20, "e": "warn"}, {"w": 30, "e": "ok"}], "pos": util, "meta": 70, "t": "meta 70 %"},
               "sub": f"{f.miles(n_val)} valoradas por auditores" if n_val else "", "x": "De las sugerencias valoradas por auditores, cuántas resultaron útiles. Esperado: 70 % o más."})
    et = V["etapas"]
    mx_ms = max((x["ms"] for x in et), default=0)
    sat = [{"n": ETAPA_CORTA.get(x["id"], x["n"]), "v": x["ms"], "txt": (x["s"] + " s"), "c": _o.COLOR_ETAPA.get(x["id"], "azul"), "hot": x["e"] == "bad" and x["ms"] == mx_ms} for x in et]
    camino = _o.camino(sat) if sat else None
    r = V["rapidez"]
    resumen_t = f"típico {r['p50']}\u00a0s · 9 de 10 bajo {r['p95']}\u00a0s · meta {r['meta']}\u00a0s" if r["hay"] else ""
    return {"frase": frase, "diag": diag, "kb": kb, "camino": camino, "camino_t": resumen_t, "hay_heat": bool(V["graficos"].get("heat")) and len(V["graficos"]["casos"]["labels"]) >= 7,
            "hay_leyes": bool(V["aciertos"]), "dias_con_datos": len(V["graficos"]["casos"]["labels"])}


def cascada_negocio(t: dict, signo=None) -> dict:
    """Cascada del ingreso a la utilidad: barras con altura mínima visible (1,5 % del recorrido), valor como etiqueta y niveles para los conectores."""
    signo = signo or (lambda x: ("−" if x < 0 else "") + f.uf(abs(x)))
    pasos = [("Ingreso", t["ingreso"], "ing"), ("Atender clientes", -t["costo_servir"], "des"), ("Parte de Veridy", -t["participacion_veridy"], "des"), ("Costos fijos", -t["costos_fijos"], "des"),
             ("Crédito y equipos", -(t["depreciacion"] + t["interes"]), "des"), ("Impuesto", -t["impuesto"], "des")]
    labels, vals, bp, sp_, bn, sn, cols, niv, run = [], [], [], [], [], [], [], [], 0.0
    pisos = []  # (índice, está sobre el cero): barras demasiado bajas para verse
    for nom, v, tipo in pasos:
        a, b = (0.0, v) if tipo == "ing" else (run, run + v)
        run = b
        lo, hi = min(a, b), max(a, b)
        bp.append(round(max(lo, 0), 3)); sp_.append(round(max(hi, 0) - max(lo, 0), 3)); bn.append(round(min(hi, 0), 3)); sn.append(round(min(lo, 0) - min(hi, 0), 3))
        cols.append("ok" if tipo == "ing" else "coral"); labels.append(nom); vals.append(signo(v)); niv.append(round(run, 3))
    lo, hi = min(run, 0), max(run, 0)
    bp.append(0); sp_.append(round(hi, 3)); bn.append(0); sn.append(round(lo, 3)); cols.append("ok" if run >= 0 else "bad")
    labels.append("Utilidad"); vals.append(signo(t["utilidad"]))
    # altura mínima visible (2 px de unos 200): 1,5 % del recorrido total del gráfico
    tope = max(bp[i] + sp_[i] for i in range(len(sp_))) if sp_ else 0
    fondo = min(bn[i] + sn[i] for i in range(len(sn))) if sn else 0
    piso = round(max(tope - min(fondo, 0), 0.01) * 0.015, 3)
    for i in range(len(sp_)):
        if abs(sp_[i]) < piso and abs(sn[i]) < piso:
            if (bn[i] + sn[i]) < 0:
                sn[i] = -piso
            else:
                sp_[i] = piso
    return {"labels": labels, "vals": vals, "bp": bp, "sp": sp_, "bn": bn, "sn": sn, "cols": cols, "niv": niv}


def presentacion_negocio(V: dict, n: dict) -> dict:
    t, p = n["totales"], n["proyeccion"]
    signo = lambda x: ("−" if x < 0 else "") + f.uf(abs(x))  # noqa: E731
    e_u = "ok" if t["utilidad"] > 0 else ("bad" if t["utilidad"] < 0 else "na")
    frase = _M(f"En {n['dias']} días: {_em('ok', signo(t['ingreso']) + ' UF')} de ingreso y {_em(e_u, signo(t['utilidad']) + ' UF')} de utilidad.")
    cascada = cascada_negocio(t, signo)
    kp = {k["k"]: k for k in V["kpis"]}
    kb = [_kb(kp["neg_margen"]), _kb(kp["neg_costo"]), _kb(kp["neg_sug"]), _kb(kp["neg_adopcion_k"])]
    chips = [("p_van", "Ganancia a 5 años", f.uf(p["van"], 0), "UF"), ("p_tir", "Rentabilidad anual", f.dec_corto(p["tir_pct"], 1), "%"),
             ("p_ind", "Retorno por UF invertida", f.dec(p["indice_rentabilidad"], 2), "UF"), ("p_rec", "Inversión recuperada en", f"Año {p['recuperacion_anio']}", "")]
    cls = V["con_uso"]
    nc, ns = len(cls), len(V["sin_uso"])
    dona_c = _o.dona([{"n": "Con uso", "v": nc, "txt": str(nc), "c": "verde"}, {"n": "Sin uso", "v": ns, "txt": str(ns), "c": "amarillo"}],
                     str(nc + ns), "clientes" if nc + ns != 1 else "cliente", "Clientes con y sin uso") if nc + ns else None
    an = p["anios"][-1] if p.get("anios") else None
    dona_p = None
    if an and an["ventas"] > 0:
        util = max(0.0, min(an["utilidad"], an["ventas"]))
        pu = round(100 * util / an["ventas"])
        dona_p = _o.dona([{"n": "Utilidad", "v": util, "txt": f"{pu} %", "c": "azul"}, {"n": "Costos e impuestos", "v": an["ventas"] - util, "txt": f"{100 - pu} %", "c": "coral"}],
                         f"{pu} %", "de utilidad", f"Reparto del ingreso de {an.get('calendario', '')}")
    return {"frase": frase, "cascada": cascada, "kb": kb, "chips": chips, "n_con": nc, "n_sin": ns, "e_gen": V["eg"]["e"], "dona_c": dona_c, "dona_p": dona_p,
            "anio_p": str(an.get("calendario", "")) if an else ""}


def visuales_pdf(inf_: dict) -> dict:
    """Datos de las visuales orbitales del PDF (los mismos de la vista, sin HTML): diagrama del período, camino de una denuncia, anillos por ley,
    costo por modelo, fallas, cascada y proyección. Las que no tienen datos no aparecen."""
    out: dict = {}
    ej = informe_ejecutivo(inf_)
    colores = {"oficial": "verde", "respaldo": "amarillo", "local": "cian", "manual": "coral"}
    if ej["n_modos"]:
        out["periodo"] = {"anillos": [{"n": MODO_CORTO[m["k"]], "v": m["n"], "txt": f.miles(m["n"]), "c": colores[m["k"]], "sub": f"{m['p']} % de los casos"} for m in ej["modos"] if m["n"]],
                          "total": ej["tarjetas"][0]["v"], "unidad": "denuncias"}
    rl = _tabla(inf_, "recall_ley")
    if rl and rl["filas"]:
        meta = rl["filas"][0][7] or META_RECALL
        out["leyes"] = {"meta": 100 * meta, "items": [{"n": inf.ley_corta(r[0]), "pct": 100 * r[4], "txt": f.dec_corto(100 * r[4], 1) + "%",
                                                       "e": "ok" if r[4] >= (r[7] or META_RECALL) else ("warn" if r[4] >= (r[7] or META_RECALL) - RECALL_ALERTA else "bad")} for r in rl["filas"]]}
    le = _tabla(inf_, "lat_etapa")
    if le and le["filas"]:
        mx = max(r[3] for r in le["filas"])
        out["etapas"] = [{"n": ETAPA_CORTA.get(str(r[0]), str(r[0]).capitalize()), "v": r[3], "txt": f.segundos(r[3]) + " s", "c": _o.COLOR_ETAPA.get(str(r[0]), "azul"), "hot": r[3] == mx} for r in le["filas"]]
    kp = {k["etiqueta"]: k for s in informe(inf_) for k in s["kpis"]}
    tl = _tabla(inf_, "tokens_modelo")
    if tl and tl["filas"]:
        ck = kp.get("Costo del período")
        out["tokens"] = {"anillos": [{"n": str(r[0]), "v": r[2] + r[3], "txt": _corto_n(r[2] + r[3]), "c": _o.CICLO[i % len(_o.CICLO)]} for i, r in enumerate(tl["filas"][:4])],
                         "total": ("US$ " + ck["v"]) if ck else "—", "unidad": "costo del período"}
    fl = _tabla(inf_, "fallas")
    if fl and fl["filas"]:
        agg: dict[str, int] = {}
        for r in fl["filas"]:
            agg[str(r[1])] = agg.get(str(r[1]), 0) + int(r[4])
        nom = {"generacion": "Redacción", "recuperacion": "Búsqueda", "voyage": "Voyage AI", "gemini": "Gemini", "local": "Modelo local", "azure": "Azure OpenAI"}
        out["fallas"] = [{"n": nom.get(a, a.capitalize()), "v": b, "txt": f.miles(b), "c": _o.CICLO[i % len(_o.CICLO)], "hot": i == 0} for i, (a, b) in enumerate(sorted(agg.items(), key=lambda x: -x[1]))]
    rv = _tabla(inf_, "revision")
    if rv and rv["filas"]:
        out["motivos"] = [(str(r[0]).replace("_", " ").capitalize(), f.miles(r[1])) for r in rv["filas"][:5]]
    rent = next((s for s in inf_["secciones"] if s["id"] == "rentabilidad"), None)
    if rent and rent["kpis"]:
        def kv(pref):
            return next((k["valor"] for k in rent["kpis"] if k["etiqueta"].startswith(pref)), None)
        t = {"ingreso": kv("Ingreso del período"), "costo_servir": kv("Costo de servir"), "participacion_veridy": kv("Parte de Veridy"), "costos_fijos": kv("Costos fijos"),
             "depreciacion": kv("Depreciación"), "interes": kv("Interés del crédito"), "impuesto": kv("Impuesto"), "utilidad": kv("Utilidad después de impuestos")}
        if all(isinstance(v, (int, float)) for v in t.values()):
            out["cascada"] = cascada_negocio(t)
    rp = _tabla(inf_, "rent_proyeccion")
    if rp and rp["filas"]:
        out["proyeccion"] = [{"a": str(r[0]).split("(")[-1].rstrip(")") if "(" in str(r[0]) else str(r[0]), "cl": r[1], "ventas": r[2], "costos": round(r[2] - r[6], 2), "utilidad": r[7]} for r in rp["filas"]]
    return out
