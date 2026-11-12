"""Informe de gestión de Kerna: reúne datos reales (Log Analytics + instantánea de evaluación) en un modelo único
que consumen la página HTML y las exportaciones XLSX, CSV y PDF. Donde falta un dato se declara, no se inventa."""
from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import cache, consultas, evaluaciones, finanzas

DATOS = Path(__file__).parent / "datos"
RANGOS = (7, 30, 90)
META_RECALL = 0.80
META_P95_MS = 15000
# Precios de la API de Anthropic (USD por millón de tokens), único lugar donde se definen.
PRECIOS_FECHA = "2026-11-03"
PRECIOS_FUENTE = "tabla de precios de la API de Anthropic (anthropic.com/pricing), cacheada al 2026-11-03"
PRECIOS_CLAUDE = {  # modelo: (entrada, salida, entrada sobre 100K por prompt, salida sobre 100K)
    "Claude Haiku 5.5": (0.10, 0.50, 0.50, 2.50),
    "Claude Sonnet 5.5": (2.00, 10.00, None, None),
}
EQUIVALENCIA = {"gpt-5-nano": "Claude Haiku 5.5", "gpt-5-mini": "Claude Sonnet 5.5"}  # modelo usado: equivalente Claude
POR_DEFECTO = "Claude Haiku 5.5"  # modelos sin equivalencia (p. ej. Gemini de respaldo)
UMBRAL_PROMPT = 100_000
PROYECCION = (100, 1000)  # denuncias por mes
FUENTE_FIN = "Informe de Kerna, capítulo 25 (Tablas 107 a 115), parámetros en datos/parametros_financieros.json"
LF_LA = "Log Analytics (AppTraces del núcleo)"
CONSULTAS_INFORME = {
    "casos": "front_casos_por_dia", "modos": "solicitudes_por_modo", "tokens": "tokens_por_solicitud",
    "latencia": "front_latencia", "etapas": "latencia_por_etapa", "disponibilidad": "disponibilidad_efectiva",
    "leyes": "front_articulos_por_ley", "valoraciones": "front_valoraciones", "errores": "errores_por_proveedor",
    "revision": "informe_revision_manual", "reintentos": "front_reintentos", "por_modelo": "front_tokens_por_modelo",
}
MODOS = ("oficial", "respaldo", "local", "manual")
NOMBRE_19628 = "Ley 19.628 (datos personales), reformada por la Ley 21.719"


def nombre_ley(ley) -> str:
    """Nombre legible de una norma: la 19.628 se presenta siempre con su reforma, la Ley 21.719."""
    t = str(ley or "")
    return NOMBRE_19628 if ("19.628" in t or "19628" in t) else t


LEY_CORTA = {"19.628": "Ley 19.628 · datos personales", "19628": "Ley 19.628 · datos personales", "20.393": "Ley 20.393 · personas jurídicas", "20393": "Ley 20.393 · personas jurídicas",
             "21.643": "Ley 21.643 · Ley Karin", "21643": "Ley 21.643 · Ley Karin"}


def ley_corta(ley) -> str:
    """Etiqueta corta para gráficos («Ley 21.643 · Ley Karin»); el nombre completo va en el tooltip."""
    t = str(ley or "")
    for k, v in LEY_CORTA.items():
        if k in t:
            return v
    return t if len(t) <= 34 else t[:33] + "…"


def estado_kpi(etiqueta: str, valor, ctx: dict) -> str | None:
    """Semáforo de una cifra del informe frente a las metas reales: "ok", "warn", "bad", "na" (sin dato) o None (cifra sin meta)."""
    e = etiqueta.lower()
    casos = ctx.get("casos") or 0
    def tres(v, ok, warn):
        return "ok" if v >= ok else ("warn" if v >= warn else "bad")
    def cuenta(v):  # casos que no salieron por el camino normal: peso sobre el total
        pc = 100 * v / casos if casos else 0
        return "bad" if pc >= 10 else ("warn" if v else "ok")
    if valor is None:
        return "na"
    if e.startswith("% con sugerencia") or e.startswith("disponibilidad efectiva"):
        return None if not casos else tres(valor, 90, 70)
    if e.startswith("% de sugerencias valoradas"):
        return tres(valor, 70, 50)
    if e.startswith("modo oficial"):
        return None if not casos else tres(100 * valor / casos, 90, 70)
    if e.startswith(("modo respaldo", "modo local")):
        return "warn" if valor else "ok"
    if e.startswith(("revisión manual", "casos en revisión manual", "casos fuera del modo oficial")):
        return cuenta(valor)
    if e.startswith("recall@5 por artículo") or e.startswith("recall por ley"):
        meta = ctx.get("meta_recall") or META_RECALL
        return tres(valor, meta, meta - .10)
    if e.startswith("latencia p50"):
        return "ok" if valor <= META_P95_MS else "warn"
    if e.startswith("latencia p95"):
        return "ok" if valor <= META_P95_MS else ("warn" if valor <= 2 * META_P95_MS else "bad")
    if e.startswith("eventos de falla"):
        return "warn" if valor else "ok"
    if e.startswith("pruebas automáticas") and isinstance(valor, str) and "/" in valor:
        a, b = valor.split("/", 1)
        return "ok" if a == b else "bad"
    if e.startswith("utilidad después de impuestos"):
        return "ok" if valor > 0 else ("bad" if valor < 0 else "na")
    if e.startswith("margen operativo en porcentaje"):
        return tres(valor, 60, 30)
    return None


def periodo(dias: int | None = None, desde: str | None = None, hasta: str | None = None, ahora: datetime | None = None):
    """(inicio, fin) en UTC. Fechas AAAA-MM-DD inclusivas; si no, los últimos `dias` (7, 30 o 90)."""
    ahora = ahora or datetime.now(timezone.utc)
    try:
        if desde:
            ini = datetime.fromisoformat(desde).replace(tzinfo=timezone.utc)
            fin = datetime.fromisoformat(hasta).replace(tzinfo=timezone.utc) + timedelta(days=1) if hasta else ahora
            fin = min(fin, ahora)
            if ini < fin and (fin - ini).days <= 366:
                return ini, fin
    except ValueError:
        pass
    d = dias if dias in RANGOS else 30
    return ahora - timedelta(days=d), ahora


def kql_rango(nombre: str, ini: datetime) -> str:
    t = (consultas.DIR_KQL / f"{CONSULTAS_INFORME[nombre]}.kql").read_text(encoding="utf-8")
    return t.replace("ago(7d)", "datetime(%s)" % ini.strftime("%Y-%m-%dT%H:%M:%SZ"))


def _filas_rango(texto: str, ini: datetime, fin: datetime) -> list[dict]:
    from azure.monitor.query import LogsQueryStatus
    r = consultas._logs().query_workspace(os.environ["LOG_ANALYTICS_WORKSPACE_ID"], texto, timespan=(ini, fin))
    if r.status != LogsQueryStatus.SUCCESS:
        raise RuntimeError("consulta parcial")
    return [{c: (v.isoformat() if hasattr(v, "isoformat") else v) for c, v in zip(t.columns, f)} for t in r.tables for f in t.rows]


def _cargar(nombre: str):
    p = DATOS / nombre
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _n(v, d=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _pct(a, b):
    return round(100.0 * a / b, 1) if b else None


def construir(ini: datetime, fin: datetime, ejecutar=None, evaluacion=None, negocio=None) -> dict:
    """`negocio`: resultado de negocio.construir (clientes y costos en UF) para la sección de rentabilidad; si falta, se declara."""
    """`ejecutar(texto, ini, fin)` y los datos de evaluación se inyectan en las pruebas."""
    ejecutar = ejecutar or _filas_rango
    crudo, fallos = {}, {}
    tareas = {n: (lambda n=n: ejecutar(kql_rango(n, ini), ini, fin)) for n in CONSULTAS_INFORME}
    if evaluacion is None:  # calidad en vivo desde la tabla `evaluaciones`, a la vez que las consultas
        tareas["_evaluacion"] = evaluaciones.cargar
    res = cache.paralelo(tareas)  # las consultas son independientes: se lanzan juntas
    if evaluacion is None:
        r = res.pop("_evaluacion")
        evaluacion, fallos["evaluaciones"] = (None, type(r).__name__) if isinstance(r, Exception) else (r, None)
        if fallos["evaluaciones"] is None:
            del fallos["evaluaciones"]
    for n in CONSULTAS_INFORME:
        r = res[n]
        if isinstance(r, Exception):  # sin identidad, rol o consulta: se declara, no se oculta ni se filtra detalle
            crudo[n], fallos[n] = [], type(r).__name__
        else:
            crudo[n] = r
    corte = fin.strftime("%Y-%m-%d %H:%M UTC")
    per = f"{ini:%Y-%m-%d} a {(fin - timedelta(seconds=1)):%Y-%m-%d}"
    sin = lambda n, tema: f"Sin datos de {tema}: la consulta a Log Analytics falló ({fallos[n]})." if n in fallos else None  # noqa: E731

    # ---- 1. Resumen -------------------------------------------------------------------------------------------
    casos = sum(int(_n(f["casos"])) for f in crudo["casos"])
    con_sug = sum(int(_n(f["con_sugerencia"])) for f in crudo["casos"])
    modos = {m: 0 for m in MODOS}
    for f in crudo["modos"]:
        m = str(f.get("modo")) if str(f.get("modo")) in modos else "manual"
        modos[m] += int(_n(f["solicitudes"]))
    val_dis = sum(int(_n(f["validas"])) for f in crudo["disponibilidad"])
    con_dis = sum(int(_n(f["con_sugerencia"])) for f in crudo["disponibilidad"])
    val = {"util": 0, "no_util": 0, "ninguno_aplica": 0}
    for f in crudo["valoraciones"]:
        if f.get("valoracion") in val:
            val[f["valoracion"]] += int(_n(f["total"]))
    total_val = sum(val.values())
    resumen = {
        "id": "resumen", "titulo": "Resumen ejecutivo",
        "justificacion": "Responde en una página cuánto trabajó Kerna, con qué resultado y en qué modo; es lo primero que lee un tutor o auditor.",
        "kpis": [
            {"etiqueta": "Casos procesados", "valor": casos, "unidad": "casos", "fuente": LF_LA + ", evento solicitud_terminada"},
            {"etiqueta": "Casos con sugerencia (estado completada)", "valor": con_sug, "unidad": "casos", "fuente": LF_LA},
            {"etiqueta": "% con sugerencia", "valor": _pct(con_sug, casos), "unidad": "%", "fuente": "con sugerencia / casos procesados"},
            {"etiqueta": "% de sugerencias valoradas útiles", "valor": _pct(val["util"], total_val) if total_val else None, "unidad": "%", "fuente": LF_LA + ", eventos feedback y clasificacion_auditor"},
            {"etiqueta": "Disponibilidad efectiva", "valor": _pct(con_dis, val_dis), "unidad": "%", "fuente": "con sugerencia / solicitudes válidas (excluye sin_normativa_aplicable)"},
            {"etiqueta": "Modo oficial", "valor": modos["oficial"], "unidad": "casos", "fuente": LF_LA},
            {"etiqueta": "Modo respaldo", "valor": modos["respaldo"], "unidad": "casos", "fuente": LF_LA},
            {"etiqueta": "Modo local (gemma)", "valor": modos["local"], "unidad": "casos", "fuente": LF_LA},
            {"etiqueta": "Revisión manual", "valor": modos["manual"], "unidad": "casos", "fuente": LF_LA},
        ],
        "tablas": [{"id": "casos_dia", "titulo": "Casos por día", "cols": ["Día", "Casos", "Con sugerencia"],
                    "filas": [[str(f["dia"])[:10], int(_n(f["casos"])), int(_n(f["con_sugerencia"]))] for f in crudo["casos"]], "fuente": LF_LA}],
        "graficos": [{"tipo": "v", "titulo": "Casos procesados por día", "items": [(str(f["dia"])[5:10], int(_n(f["casos"]))) for f in crudo["casos"]]},
                     {"tipo": "h", "titulo": "Casos por modo", "items": [("oficial", modos["oficial"]), ("respaldo", modos["respaldo"]), ("local", modos["local"]), ("revisión manual", modos["manual"])]}],
        "notas": [x for x in (sin("casos", "casos"), sin("modos", "modos"), sin("disponibilidad", "disponibilidad"), sin("valoraciones", "valoraciones")) if x],
    }
    if not casos and not fallos:
        resumen["notas"].append("No hay casos procesados en el período.")

    # ---- 2. Calidad -------------------------------------------------------------------------------------------
    cal = {"id": "calidad", "titulo": "Calidad", "kpis": [], "tablas": [], "graficos": [], "notas": [],
           "justificacion": "Dice si las sugerencias son correctas: recall@5 por artículo frente a la meta de 0,80, anonimización por tipo de dato y valoración de auditores. Es la evidencia central del KPI del proyecto."}
    cal["kpis"].append({"etiqueta": "Valoraciones: útil", "valor": val["util"], "unidad": "valoraciones", "fuente": LF_LA})
    cal["kpis"].append({"etiqueta": "Valoraciones: no útil", "valor": val["no_util"], "unidad": "valoraciones", "fuente": LF_LA})
    cal["kpis"].append({"etiqueta": "Valoraciones: ninguno aplica", "valor": val["ninguno_aplica"], "unidad": "valoraciones", "fuente": LF_LA})
    if evaluacion and evaluacion.get("recall"):
        r = evaluacion["recall"]
        fte = f"{r['fuente']} (medición {r['fecha'][:16].replace('T', ' ')} UTC, commit {r.get('commit')})"
        glob = next((x for x in r["por_ley"] if x["ley"] == "Global"), None)
        if glob:
            cal["kpis"].append({"etiqueta": "Recall@5 por artículo (global)", "valor": round(glob["recall5"], 3), "unidad": "ratio", "fuente": fte})
            cal["kpis"].append({"etiqueta": "Meta de recall@5", "valor": r["meta"], "unidad": "ratio", "fuente": fte})
            cal["kpis"].append({"etiqueta": "Recall por ley (global)", "valor": round(glob["recall_ley"], 3), "unidad": "ratio", "fuente": fte})
        cal["tablas"].append({"id": "recall_ley", "titulo": f"Recall@5 por ley ({r['configuracion']}; {r['dataset_casos']} casos del dataset público)",
                              "cols": ["Ley", "Casos", "Casos a nivel artículo", "Recall por ley", "Recall@5 artículo", "IC95 inf.", "IC95 sup.", "Meta", "Cumple meta"],
                              "filas": [[nombre_ley(x["ley"]), x["casos"], x["casos_articulo"], round(x["recall_ley"], 3), round(x["recall5"], 3),
                                         round(x["ic95_inf"], 3) if x["ic95_inf"] is not None else None, round(x["ic95_sup"], 3) if x["ic95_sup"] is not None else None,
                                         r["meta"], "sí" if x["recall5"] >= r["meta"] else "no"] for x in r["por_ley"]], "fuente": fte})
        cal["graficos"].append({"tipo": "h", "titulo": f"Recall@5 por artículo (meta {str(r['meta']).replace('.', ',')})", "items": [(nombre_ley(x["ley"]), round(x["recall5"], 3)) for x in r["por_ley"]], "fmt": "ratio", "meta": r["meta"]})
        serie = evaluacion.get("serie", [])[-10:]
        if serie:
            cal["tablas"].append({"id": "recall_serie", "titulo": "Últimas 10 mediciones de recall@5 por artículo (global)", "cols": ["Fecha (UTC)", "Configuración", "Recall@5"],
                                  "filas": [[s["fecha"], s["configuracion"], round(s["recall5"], 3)] for s in serie], "fuente": r["fuente"]})
        cal["notas"].append("El recall se mide sobre el dataset público de evaluación, no sobre denuncias reales; las cifras no cambian con el período elegido.")
    else:
        cal["notas"].append(f"Sin datos de evaluación: la tabla `evaluaciones` no respondió ({fallos['evaluaciones']})." if "evaluaciones" in fallos
                            else "Sin datos de evaluación: la tabla `evaluaciones` está vacía.")
    if evaluacion and evaluacion.get("anonimizador"):
        a = evaluacion["anonimizador"]
        cal["tablas"].append({"id": "anonimizador", "titulo": f"Anonimizador por reglas: recall por tipo de dato ({a['casos']} casos, medición {a['fecha']})",
                              "cols": ["Tipo", "Casos con el dato", "Casos detectados", "Recall por caso"],
                              "filas": [[t["tipo"], t["casos_con_dato"], t["casos_detectados"], t["recall_por_caso"]] for t in a["tipos"]], "fuente": a["fuente"]})
        cal["tablas"].append({"id": "anon_apariciones", "titulo": "Anonimizador: apariciones ocultas", "cols": ["Tipo", "Apariciones", "Ocultas"],
                              "filas": [[t["tipo"], t["total"], t["ocultas"]] for t in a["apariciones"]], "fuente": a["fuente"]})
    else:
        cal["notas"].append("Sin datos del anonimizador en la tabla `evaluaciones`.")
    if evaluacion and evaluacion.get("pruebas"):
        p = evaluacion["pruebas"]
        for capa, v in p["capas"].items():
            cal["kpis"].append({"etiqueta": f"Pruebas automáticas ({capa}): pasadas/total", "valor": f"{v['pasadas']}/{v['total']}", "unidad": "pruebas", "fuente": f"{p['fuente']} ({p['fecha']}, commit {p['commit']})"})
    if not total_val:
        cal["notas"].append("No hay valoraciones de auditores en el período.")
    cal["notas"] += [x for x in (sin("valoraciones", "valoraciones"),) if x]

    # ---- 3. Desempeño -----------------------------------------------------------------------------------------
    lat = crudo["latencia"]
    tot_l = sum(int(_n(f["solicitudes"])) for f in lat)
    p50 = sum(_n(f["p50_ms"]) * int(_n(f["solicitudes"])) for f in lat) / tot_l if tot_l else None
    p95 = max((_n(f["p95_ms"]) for f in lat), default=None) if lat else None
    desemp = {"id": "desempeno", "titulo": "Desempeño",
              "justificacion": "Mide el tiempo de respuesta frente al requisito PR-30 (P95 de 15 s) y la etapa que lo consume.",
              "kpis": [{"etiqueta": "Latencia P50 (ponderada por día)", "valor": round(p50) if p50 is not None else None, "unidad": "ms", "fuente": LF_LA + ", duracion_ms de solicitud_terminada"},
                       {"etiqueta": "Latencia P95 (máximo diario)", "valor": round(p95) if p95 is not None else None, "unidad": "ms", "fuente": LF_LA + "; los percentiles diarios no se combinan exactamente"},
                       {"etiqueta": "Meta PR-30: P95", "valor": META_P95_MS, "unidad": "ms", "fuente": "requisito PR-30 (pendientes/kerna-pendientes.md)"},
                       {"etiqueta": "Cumple PR-30", "valor": None if p95 is None else ("sí" if p95 <= META_P95_MS else "no"), "unidad": "", "fuente": "P95 máximo diario frente a la meta"}],
              "tablas": [{"id": "lat_dia", "titulo": "Latencia por día", "cols": ["Día", "Solicitudes", "P50 (ms)", "P95 (ms)"],
                          "filas": [[str(f["dia"])[:10], int(_n(f["solicitudes"])), round(_n(f["p50_ms"])), round(_n(f["p95_ms"]))] for f in lat], "fuente": LF_LA},
                         {"id": "lat_etapa", "titulo": "Latencia por etapa", "cols": ["Etapa", "Solicitudes", "P50 (ms)", "P95 (ms)", "Máx. (ms)"],
                          "filas": [[str(f["etapa"]), int(_n(f["solicitudes"])), round(_n(f["p50_ms"])), round(_n(f["p95_ms"])), round(_n(f["max_ms"]))] for f in crudo["etapas"]], "fuente": LF_LA + ", eventos de clase etapa"}],
              "graficos": [{"tipo": "h", "titulo": "P95 por etapa (ms)", "items": [(str(f["etapa"]), round(_n(f["p95_ms"]))) for f in crudo["etapas"]]}],
              "notas": [x for x in (sin("latencia", "latencia"), sin("etapas", "etapas")) if x]}
    conm = sum(modos[m] for m in ("respaldo", "local", "manual"))
    desemp["kpis"].append({"etiqueta": "Casos fuera del modo oficial", "valor": conm, "unidad": "casos", "fuente": LF_LA})
    rt = crudo["reintentos"]
    reint = [r for r in rt if r.get("evento") == "conector_reintento"]
    desemp["kpis"].append({"etiqueta": "Reintentos del conector enviados", "valor": sum(int(_n(r["eventos"])) for r in reint) if "reintentos" not in fallos else None, "unidad": "reintentos", "fuente": LF_LA + ", evento conector_reintento"})
    desemp["kpis"].append({"etiqueta": "Casos reprocesados por el conector", "valor": sum(int(_n(r["eventos"])) for r in rt if r.get("evento") == "conector_reproceso") if "reintentos" not in fallos else None, "unidad": "casos", "fuente": LF_LA + ", evento conector_reproceso"})
    desemp["kpis"].append({"etiqueta": "Casos compartidos con el auditor", "valor": sum(int(_n(r["eventos"])) for r in rt if r.get("evento") == "conector_caso_compartido") if "reintentos" not in fallos else None, "unidad": "casos", "fuente": LF_LA + ", evento conector_caso_compartido"})
    desemp["tablas"].append({"id": "reintentos", "titulo": "Reintentos del conector por n.º de intento y motivo", "cols": ["Intento", "Motivo", "Reintentos", "Casos distintos"],
                             "filas": [[r.get("intento") or "-", r.get("motivo") or "-", int(_n(r["eventos"])), int(_n(r["casos"]))] for r in reint], "fuente": LF_LA + ", evento conector_reintento"})
    desemp["notas"] += [x for x in (sin("reintentos", "reintentos del conector"),) if x]
    if not rt and "reintentos" not in fallos:
        desemp["notas"].append("Sin eventos del conector en el período: el conector solo envía a Log Analytics desde la imagen y el grupo que incluyen la telemetría de Azure.")
    ev = (evaluacion or {}).get("evaluador")
    if ev and ev.get("latencia_llamada_ms"):
        desemp["kpis"].append({"etiqueta": f"Latencia de llamada del evaluador {ev.get('cadena')} (mediana, medición offline)", "valor": round(ev["latencia_llamada_ms"]["mediana"]), "unidad": "ms", "fuente": "kerna/evaluacion/registro/recall_retriever.jsonl"})

    # ---- 4. Costo y consumo ----------------------------------------------------------------------------------
    te = sum(_n(f["tokens_entrada_total"]) for f in crudo["tokens"])
    ts = sum(_n(f["tokens_salida_total"]) for f in crudo["tokens"])
    nsol = sum(int(_n(f["solicitudes"])) for f in crudo["tokens"])

    anio_op = finanzas.anio_operacion(fin.date())
    desglose = {}  # modelo Claude -> [solicitudes, entrada, salida, USD, modelos usados]
    sin_equiv = []
    for f in crudo["por_modelo"]:
        usado = str(f["modelo"])
        cl = EQUIVALENCIA.get(usado)
        if cl is None:
            cl = POR_DEFECTO
            sin_equiv.append(usado)
        pe, ps, pe2, ps2 = PRECIOS_CLAUDE[cl]
        n, ent, sal = int(_n(f["solicitudes"])), _n(f["tokens_entrada_total"]), _n(f["tokens_salida_total"])
        prom = _n(f.get("tokens_entrada_prom")) or (ent / n if n else 0)
        alto = pe2 is not None and prom > UMBRAL_PROMPT
        usd = ent * (pe2 if alto else pe) / 1e6 + sal * (ps2 if alto else ps) / 1e6
        d = desglose.setdefault(cl, [0, 0, 0, 0.0, []])
        d[0] += n; d[1] += int(ent); d[2] += int(sal); d[3] += usd
        if usado not in d[4]:
            d[4].append(usado)
    nmod = sum(d[0] for d in desglose.values())
    hay = bool(nmod)
    total = sum(d[3] for d in desglose.values())
    por_caso = total / nmod if hay else None
    desg = [[cl, ", ".join(d[4]), d[0], d[1], d[2], round(d[3], 4)] for cl, d in desglose.items()]
    costo = {"id": "costo", "titulo": "Costo y consumo",
             "justificacion": "Muestra el costo del período a precios de la API de Anthropic, según los tokens medidos por modelo y su equivalente Claude.",
             "kpis": [{"etiqueta": "Solicitudes con tokens medidos", "valor": nsol, "unidad": "solicitudes", "fuente": LF_LA},
                      {"etiqueta": "Tokens de entrada", "valor": int(te), "unidad": "tokens", "fuente": LF_LA + ", tokens_entrada de solicitud_terminada"},
                      {"etiqueta": "Tokens de salida", "valor": int(ts), "unidad": "tokens", "fuente": LF_LA},
                      {"etiqueta": "Costo del período", "valor": round(total, 4) if hay else None, "unidad": "USD", "fuente": "tokens por modelo x precios de la API de Anthropic"},
                      {"etiqueta": "Costo por denuncia", "valor": round(por_caso, 6) if hay else None, "unidad": "USD", "fuente": "costo del período / solicitudes"}]
             + [{"etiqueta": f"Costo de IA del período en UF", "valor": round(finanzas.usd_a_uf(total, anio_op), 4) if hay else None, "unidad": "UF", "fuente": f"USD convertidos con dólar a {finanzas.parametros()['usd_clp']} y UF a {round(finanzas.uf_del_anio(anio_op))} pesos"}]
             + [{"etiqueta": f"Costo de IA mensual proyectado, {format(k, ',d').replace(',', '.')} denuncias", "valor": round(por_caso * k, 2) if hay else None, "unidad": "USD", "fuente": "costo por denuncia x volumen mensual (solo IA)"} for k in PROYECCION]
             + [{"etiqueta": f"Costo total mensual proyectado, {format(k, ',d').replace(',', '.')} denuncias", "valor": round(finanzas.usd_a_uf(por_caso * k, anio_op) + finanzas.a_uf(finanzas.total_fijos_clp(anio_op) / 12, anio_op), 2) if hay else None, "unidad": "UF",
                 "fuente": "IA del volumen + costos fijos mensuales del capítulo 25 (Tabla 111); sin el costo de servir por cliente"} for k in PROYECCION],
             "tablas": [{"id": "costo_modelo", "titulo": "Costo por modelo (precios USD por millón de tokens: Haiku 5.5 0,10/0,50; Sonnet 5.5 2,00/10,00)",
                         "cols": ["Modelo Claude", "Modelo usado", "Solicitudes", "Tokens entrada", "Tokens salida", "Costo (USD)"],
                         "filas": desg, "fuente": f"{PRECIOS_FUENTE}; tokens medidos en {LF_LA}"},
                        {"id": "tokens_modo", "titulo": "Tokens por modo", "cols": ["Modo", "Solicitudes", "Tokens entrada", "Tokens salida", "Entrada prom.", "Salida prom."],
                         "filas": [[str(f["modo"]), int(_n(f["solicitudes"])), int(_n(f["tokens_entrada_total"])), int(_n(f["tokens_salida_total"])), round(_n(f["tokens_entrada_prom"])), round(_n(f["tokens_salida_prom"]))] for f in crudo["tokens"]], "fuente": LF_LA},
                        {"id": "tokens_modelo", "titulo": "Consumo por modelo exacto", "cols": ["Modelo", "Solicitudes", "Tokens entrada", "Tokens salida"],
                         "filas": [[str(f["modelo"]), int(_n(f["solicitudes"])), int(_n(f["tokens_entrada_total"])), int(_n(f["tokens_salida_total"]))] for f in crudo["por_modelo"]], "fuente": LF_LA + ", modelo de solicitud_terminada"}],
             "graficos": [{"tipo": "h", "titulo": "Costo del período por modelo (USD)", "items": [(r[0], r[5]) for r in desg], "fmt": "usd"},
                          {"tipo": "h", "titulo": "Tokens totales por modo", "items": [(str(f["modo"]), int(_n(f["tokens_entrada_total"]) + _n(f["tokens_salida_total"]))) for f in crudo["tokens"]]}],
             "notas": [x for x in (sin("tokens", "tokens"), sin("por_modelo", "consumo por modelo")) if x]}
    costo["notas"] += [f"Fuente de precios: {PRECIOS_FUENTE}. Equivalencias: gpt-5-nano = Claude Haiku 5.5; gpt-5-mini = Claude Sonnet 5.5. Haiku 5.5 usa 0,50/2,50 USD/M si el prompt supera 100K tokens."]
    if not hay:
        costo["notas"].append("Sin solicitudes con modelo registrado en el período: el costo se calcula cuando el núcleo emite el modelo en solicitud_terminada.")
    if sin_equiv:
        costo["notas"].append("Sin equivalencia fija, valorizados como Claude Haiku 5.5: " + ", ".join(sorted(set(sin_equiv))) + ".")
    pe = (evaluacion or {}).get("precios_embeddings") or {}
    if pe:
        desc = [k for k, v in pe.items() if v is None]
        costo["notas"].append("Embeddings: sin precio verificado para " + (", ".join(desc[:4]) or "ninguno") + "; Anthropic no ofrece embeddings y su costo queda fuera.")

    # ---- 5. Cobertura normativa ------------------------------------------------------------------------------
    ley_rows = [[nombre_ley(f["norma"]) or "(sin nombre)", int(_n(f["articulos"]))] for f in crudo["leyes"]]
    cob = {"id": "cobertura", "titulo": "Cobertura normativa",
           "justificacion": "Indica qué normas conoce Kerna y cuáles sugiere realmente; permite detectar leyes del corpus que nunca se usan.",
           "kpis": [{"etiqueta": "Artículos vigentes en el corpus", "valor": (evaluacion or {}).get("corpus_articulos"), "unidad": "artículos", "fuente": "kerna/evaluacion/registro/recall_retriever.jsonl (colección normativa_cl, vigente=true)"},
                    {"etiqueta": "Artículos sugeridos en el período", "valor": sum(r[1] for r in ley_rows), "unidad": "artículos", "fuente": LF_LA + ", evento articulo_sugerido"}],
           "tablas": [{"id": "leyes", "titulo": "Artículos sugeridos por ley", "cols": ["Norma", "Artículos sugeridos"], "filas": ley_rows, "fuente": LF_LA}],
           "graficos": [{"tipo": "h", "titulo": "Artículos sugeridos por ley", "items": [tuple(r) for r in ley_rows]}],
           "notas": [x for x in (sin("leyes", "artículos por ley"),) if x]}
    cob["notas"].append("Leyes cubiertas por el corpus y el dataset de evaluación: 21.643 (Ley Karin), 19.628 (datos personales, reformada por la Ley 21.719, texto vigente desde el 1 de diciembre de 2026) y 20.393 (responsabilidad penal de personas jurídicas).")
    if not ley_rows:
        cob["notas"].append("Sin sugerencias por ley en el período: el evento articulo_sugerido solo existe desde que el núcleo desplegado lo emite.")

    # ---- 6. Incidentes ---------------------------------------------------------------------------------------
    err = [[str(f["evento"]), str(f["proveedor"]), str(f["modelo"]), str(f["codigo"]), int(_n(f["eventos"]))] for f in crudo["errores"]]
    rev = [[str(f["motivo"]), int(_n(f["casos"]))] for f in crudo["revision"]]
    inc = {"id": "incidentes", "titulo": "Incidentes",
           "justificacion": "Registra caídas de modelos, límites de cuota y casos que requirieron revisión humana: la parte operativa que explica las demás cifras.",
           "kpis": [{"etiqueta": "Casos en revisión manual", "valor": sum(r[1] for r in rev) if "revision" not in fallos else None, "unidad": "casos", "fuente": LF_LA + ", solicitud_terminada con estado revision_manual"},
                    {"etiqueta": "Eventos de falla de proveedor o modelo", "valor": sum(r[4] for r in err) if "errores" not in fallos else None, "unidad": "eventos", "fuente": LF_LA + ", nivel_fallido, recuperación fallida, cortocircuito"}],
           "tablas": [{"id": "fallas", "titulo": "Fallas por evento, proveedor, modelo y código", "cols": ["Evento", "Proveedor", "Modelo", "Código", "Eventos"], "filas": err, "fuente": LF_LA},
                      {"id": "revision", "titulo": "Casos en revisión manual por motivo", "cols": ["Motivo", "Casos"], "filas": rev, "fuente": LF_LA}],
           "graficos": [{"tipo": "h", "titulo": "Revisión manual por motivo", "items": [tuple(r) for r in rev]}],
           "notas": [x for x in (sin("errores", "fallas"), sin("revision", "revisión manual")) if x]}
    inc["notas"].append("Reintentos del conector sobre casos en revisión manual (hasta 3, uno al día, por falla de modelos): el conector los registra en su propio log, no en Log Analytics; sin cifras en este informe.")

    # ---- 7. Rentabilidad (costos reales del capítulo 25) -----------------------------------------------------
    rent = _rentabilidad(negocio)
    return {"meta": {"titulo": "Informe de gestión de Kerna AI", "periodo": per, "desde": ini.isoformat(timespec="seconds"), "hasta": fin.isoformat(timespec="seconds"),
                     "corte": corte, "evaluacion_generada": (evaluacion or {}).get("generado")},
            "secciones": [resumen, cal, desemp, costo, rent, cob, inc]}


def _rentabilidad(n: dict | None) -> dict:
    """Sección de rentabilidad en UF con todos los costos del capítulo 25: costo de servir, parte de Veridy, costos fijos,
    depreciación, interés e impuesto, más la proyección a cinco años con los supuestos del capítulo."""
    sec = {"id": "rentabilidad", "titulo": "Rentabilidad",
           "justificacion": "Muestra cuánto gana Kerna después de todos sus costos (IA, infraestructura y soporte por cliente, parte de Veridy, costos fijos, crédito e impuesto) y qué se espera en los próximos cinco años.",
           "kpis": [], "tablas": [], "graficos": [], "notas": []}
    if not n:
        sec["notas"].append("Sin datos de clientes: las tablas de negocio no respondieron o están vacías; la rentabilidad se calcula cuando hay clientes y uso registrados.")
        return sec
    t, p, f = n["totales"], n["proyeccion"], FUENTE_FIN
    per = f"{n['dias']} días hasta {n['hasta']}"
    fte = f"tablas clientes y usodiario del núcleo; costos según {f}"
    for et, k, u in (("Ingreso del período", "ingreso", "UF"), ("Costo de IA (con tope de cuota del plan)", "costo_ia", "UF"), ("Costo de servir a los clientes", "costo_servir", "UF"),
                     ("Margen después de servir", "margen_bruto", "UF"), ("Parte de Veridy", "participacion_veridy", "UF"), ("Costos fijos del período", "costos_fijos", "UF"),
                     ("Margen operativo", "margen_operativo", "UF"), ("Depreciación", "depreciacion", "UF"), ("Interés del crédito", "interes", "UF"),
                     ("Impuesto de primera categoría", "impuesto", "UF"), ("Utilidad después de impuestos", "utilidad", "UF")):
        sec["kpis"].append({"etiqueta": f"{et} ({per})", "valor": t[k], "unidad": u, "fuente": fte})
    for et, k in (("Margen después de servir", "margen_bruto_pct"), ("Margen operativo", "margen_operativo_pct"), ("Margen neto", "margen_neto_pct")):
        sec["kpis"].append({"etiqueta": f"{et} en porcentaje del ingreso", "valor": t[k], "unidad": "%", "fuente": fte})
    sec["tablas"].append({"id": "rent_clientes", "titulo": "Rentabilidad por cliente (UF, período)", "cols": ["Cliente", "Plan", "Tarifa al año", "Ingreso", "Costo de IA", "Costo de servir", "Margen", "Margen %"],
                          "filas": [[c["nombre"], c["plan_tipo"], c["tarifa_uf_anual"], c["ingreso"], c["costo_ia"], c["costo_servir"], c["margen"], c["margen_pct"]] for c in n["clientes"]], "fuente": fte})
    sec["tablas"].append({"id": "rent_proyeccion", "titulo": "Proyección a cinco años (UF)", "cols": ["Año", "Clientes", "Ingresos (UF)", "Costo de servir", "Parte de Veridy", "Costos fijos", "Margen operativo", "Utilidad después de impuestos", "Caja del año"],
                          "filas": [[f"{a['anio']} ({a['calendario']})", a["clientes"], a["ventas"], a["costo_ventas"], a["participacion_veridy"], a["costos_fijos"], a["margen_operativo"], a["utilidad"], a["flujo"]] for a in p["anios"]],
                          "fuente": f})
    sec["kpis"] += [{"etiqueta": "Valor actual neto de la proyección", "valor": p["van"], "unidad": "UF", "fuente": f},
                    {"etiqueta": "Retorno anual del proyecto", "valor": p["tir_pct"], "unidad": "%", "fuente": f},
                    {"etiqueta": "Índice de rentabilidad", "valor": p["indice_rentabilidad"], "unidad": "ratio", "fuente": f},
                    {"etiqueta": "Año en que se recupera la inversión", "valor": p["recuperacion_anio"], "unidad": "año", "fuente": f}]
    sec["graficos"].append({"tipo": "h", "titulo": "Utilidad después de impuestos por año (UF)", "items": [(f"Año {a['anio']}", a["utilidad"]) for a in p["anios"]]})
    sec["notas"] += [f"Valores en UF: 1 UF = {round(n['uf_clp'])} pesos y dólar a {n['usd_clp']} pesos. El costo de IA se mide en dólares y se limita a la cuota mensual del plan (3.000, 7.000 y 15.000 pesos); sobre ella las consultas pasan al modo local.",
                     f"Proyección con los supuestos del capítulo 25: clientes de 5 a 17, reajuste de {p['inflacion_pct']} % anual, parte de Veridy de {p['participacion_veridy_pct']} %, crédito de 36 cuotas, impuesto según la Ley 21.850 y descuento de {p['tasa_descuento_pct']} %; el año 1 es {p['inicio_operacion'][:4]}.",
                     "Los costos fijos, la depreciación y el interés se prorratean por los días del período."]
    return sec


def filas_largas(inf: dict) -> list[list]:
    """Formato largo: sección, métrica, valor, unidad, fuente, fecha de corte. Las tablas se aplanan (una fila por celda numérica o de texto)."""
    corte, out = inf["meta"]["corte"], []
    for s in inf["secciones"]:
        for k in s["kpis"]:
            out.append([s["titulo"], k["etiqueta"], "sin datos" if k["valor"] is None else k["valor"], k["unidad"], k["fuente"], corte])
        for t in s["tablas"]:
            for f in t["filas"]:
                for c, v in zip(t["cols"][1:], f[1:]):
                    out.append([s["titulo"], f"{t['titulo']} | {f[0]} | {c}", "sin datos" if v is None else v, "", t["fuente"], corte])
        for n in s["notas"]:
            out.append([s["titulo"], "Nota", n, "", "", corte])
    return out
