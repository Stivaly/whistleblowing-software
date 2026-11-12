"""
Medición del agente evaluador LLM (nucleo/kerna_nucleo/evaluador.py) sobre los N primeros del retriever.

Base: voyage-4-large (normativa_cl, producción), vectores de consulta guardados (sin volver a vectorizar), filtro
vigente=true, mapeo `concordancia`. Se recuperan N candidatos, el evaluador los reordena (aplican por confianza, el
resto en el orden del retriever) y se miden las mismas métricas de recall_retriever.py. Diferencia contra la base con
bootstrap pareado (semilla 20261110). Las respuestas del LLM se guardan en datos/evaluador_cache.json (excluido de
git; contiene texto de denuncias públicas del dataset) para no repetir llamadas.

Uso (desde kerna/, con GEMINI_API_KEY, QDRANT_* y VOYAGE_API_KEY en el entorno):
  set -a; . pipeline_bcn/.env; set +a
  PYTHONPATH=nucleo:comun python3 evaluacion/medir_evaluador.py --variante 1 --candidatos 30 \
      --cadena gemini-3.5-flash,gemini-3.5-flash-lite
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "nucleo"))
sys.path.insert(0, str(AQUI.parent / "comun"))
import recall_retriever as rr  # noqa: E402
from kerna_nucleo.enrutador import Enrutador, Nivel, Resultado  # noqa: E402
from kerna_nucleo.evaluador import Evaluador  # noqa: E402
from kerna_nucleo.evaluador_ids import EvaluadorIds, VARIANTES as VARIANTES_IDS, segmentar_articulo, segmentar_hechos, usuario_lote  # noqa: E402
from kerna_nucleo.proveedores.azure_openai import ClienteAzureOpenAI  # noqa: E402
from kerna_nucleo.proveedores.gemini import ClienteGemini  # noqa: E402
from kerna_comun import anonimizador  # noqa: E402

TOPE = {"usd": None, "gastado": 0.0, "pe": 0.0, "ps": 0.0}
LIBRO = AQUI / "registro" / "gasto_evaluador_ids.json"   # gasto acumulado de la tarea (tope duro)
TOPE_TAREA_USD = 4.0
N_DESARROLLO = 40
DIAG: list[dict] = []
CACHE = AQUI / "datos" / "evaluador_cache.json"
COLECCION, PROVEEDOR, MODELO = "normativa_cl", "voyage", "voyage-4-large"


def textos_fragmentos(coleccion: str) -> dict[str, dict]:
    out, offset = {}, None
    while True:
        body = {"filter": rr._FILTRO_VIGENTE, "limit": 256, "with_vector": False,
                "with_payload": ["fragmento_id", "texto", "norma", "tipo_numero", "articulo", "jerarquia"]}
        if offset is not None:
            body["offset"] = offset
        r = rr.qdrant(f"/collections/{coleccion}/points/scroll", body, method="POST")["result"]
        out.update({p["payload"]["fragmento_id"]: p["payload"] for p in r["points"]})
        offset = r.get("next_page_offset")
        if offset is None:
            return out


def gasto_acumulado() -> float:
    return json.loads(LIBRO.read_text())["usd"] if LIBRO.exists() else 0.0


def sumar_libro(usd: float) -> None:
    LIBRO.write_text(json.dumps({"usd": round(gasto_acumulado() + usd, 6), "tope_tarea_usd": TOPE_TAREA_USD}))


def dividir(casos: list[dict], corpus: set, mapeo: str) -> dict[str, list[int]]:
    """Casos evaluables por artículo (ley distinta de «ninguna» y con candidatos mapeables) divididos de forma fija
    con la semilla 20261110: N_DESARROLLO para desarrollo y el resto para prueba (índices en el dataset)."""
    ev = sorted(i for i, c in enumerate(casos) if c["ley_principal"] != "ninguna"
                and rr.normalizar_candidatos(c["articulos_candidatos"], corpus, mapeo)[0])
    mez = ev[:]
    random.Random(rr.SEMILLA).shuffle(mez)
    return {"desarrollo": sorted(mez[:N_DESARROLLO]), "prueba": sorted(mez[N_DESARROLLO:]), "todos": ev}


class Generador:
    """Envuelve el enrutador con una caché en disco (clave = cadena + prompts) y cuenta tokens."""

    def __init__(self, enrutador: Enrutador, cadena: str):
        self.enr, self.cadena = enrutador, cadena
        self.cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        self.llamadas = self.aciertos = 0
        self.ms: list[float] = []
        self.por_modelo: dict[str, int] = {}

    async def __call__(self, sistema, usuario, esquema, validar, inicio):
        esfuerzo = os.environ.get("KERNA_AZURE_OPENAI_ESFUERZO", "low")
        estricto = isinstance(esquema, dict) and esquema.get("additionalProperties") is False
        k = hashlib.sha256((f"{self.cadena}|{sistema}|{usuario}" + (f"|esfuerzo={esfuerzo}" if esfuerzo != "low" else "") + (f"|{json.dumps(esquema, sort_keys=True)}" if estricto else "")).encode()).hexdigest()
        if k in self.cache:
            self.aciertos += 1
            c = self.cache[k]
            self.por_modelo[c["modelo"]] = self.por_modelo.get(c["modelo"], 0) + 1
            return Resultado(validar(c["d"] if "d" in c else c["datos"]), "cache", "gemini", c["modelo"], c["te"], c["ts"])
        if TOPE["usd"] is not None and TOPE["gastado"] >= TOPE["usd"]:
            raise SystemExit(f"tope de gasto alcanzado: {TOPE['gastado']:.3f} USD")
        t0 = time.monotonic()
        r = await self.enr.generar(sistema, usuario, esquema, validar, time.time())
        self.ms.append((time.monotonic() - t0) * 1000)
        print(f"llamada {r.modelo} {self.ms[-1] / 1000:.0f}s tokens {r.tokens_entrada}/{r.tokens_salida}", flush=True)
        self.llamadas += 1
        TOPE["gastado"] += r.tokens_entrada / 1e6 * TOPE["pe"] + r.tokens_salida / 1e6 * TOPE["ps"]
        self.por_modelo[r.modelo] = self.por_modelo.get(r.modelo, 0) + 1
        self.cache[k] = {("d" if estricto else "datos"): (r.datos if estricto else {"resultados": r.datos}), "modelo": r.modelo, "te": r.tokens_entrada,
                         "ts": r.tokens_salida}
        CACHE.write_text(json.dumps(self.cache, ensure_ascii=False))
        sumar_libro(r.tokens_entrada / 1e6 * TOPE["pe"] + r.tokens_salida / 1e6 * TOPE["ps"])
        return r


async def correr(args, casos, textos, base_tops, frag, gen, corpus):
    clase = EvaluadorIds if args.variante.startswith("3") else Evaluador
    ev = clase(gen, variante=args.variante, lote=args.lote, salida=rr.TOP_BUSQUEDA)
    sem = asyncio.Semaphore(args.concurrencia)
    stats = {"usado": 0, "fallido": 0, "ninguno": 0, "desc_id": 0, "desc_cita": 0, "aplican": 0, "te": 0, "ts": 0,
             "relacionados": 0, "rellenados": 0, "con_perfil": 0, "latencia_caso_ms": []}

    async def uno(caso, texto, top):
        # Solo los casos con candidatos mapeables entran en las métricas por artículo: el resto no se envía al LLM.
        if caso["ley_principal"] == "ninguna" or not rr.normalizar_candidatos(
                caso["articulos_candidatos"], corpus, args.mapeo)[0]:
            return top[:rr.TOP_BUSQUEDA]
        cand = [dict(frag[t["fragmento_id"]], score=t["score"], id_norma=t["id_norma"]) for t in top]
        async with sem:
            r = await ev.evaluar(texto, cand, time.time())
        if getattr(r, "evaluaciones", None) is not None and not isinstance(next(iter(r.evaluaciones.values()), {}).get("aplica", 0), bool):
            cands = rr.normalizar_candidatos(caso["articulos_candidatos"], corpus, args.mapeo)[0]
            DIAG.append({"id": caso["id"], "n_por_puntaje": [sum(v["puntaje"] == k for v in r.evaluaciones.values()) for k in range(4)],
                         "gold": [{"rank_retriever": i + 1, "puntaje": r.evaluaciones.get(t["fragmento_id"], {}).get("puntaje", 0)}
                                  for i, t in enumerate(top) if rr.articulo_de(t["fragmento_id"]) in cands],
                         "gold_en_top5": any(rr.articulo_de(f["fragmento_id"]) in cands for f in r.fragmentos[:5])})
        stats["usado"] += r.usado
        stats["fallido"] += r.motivo == "evaluador_fallido"
        stats["ninguno"] += r.motivo == "ninguno_aplica"
        stats["desc_id"] += r.descartados_id
        stats["desc_cita"] += r.descartados_cita
        stats["aplican"] += r.aplican
        stats["relacionados"] += getattr(r, "relacionados", 0)
        stats["rellenados"] += getattr(r, "rellenados", 0)
        stats["con_perfil"] += getattr(r, "perfil", False)
        if getattr(r, "latencia_ms", 0):
            stats["latencia_caso_ms"].append(r.latencia_ms)
        stats["te"] += r.tokens_entrada
        stats["ts"] += r.tokens_salida
        return [{"fragmento_id": f["fragmento_id"], "id_norma": f["id_norma"], "score": f.get("confianza_evaluador", 0)}
                for f in r.fragmentos]

    return await asyncio.gather(*[uno(c, t, top) for c, t, top in zip(casos, textos, base_tops)]), stats


def estimar(args, casos, textos, base_tops, frag) -> dict:
    """Estimación previa (conservadora: ignora la caché): ~3,3 caracteres por token de entrada y `--salida-estimada`
    tokens de salida por llamada (más una extracción de ~3.000 tokens de entrada y ~1.500 de salida por caso)."""
    entrada = salida = llamadas = 0
    for t, top in zip(textos, base_tops):
        cand = [frag[x["fragmento_id"]] for x in top]
        hechos = segmentar_hechos(t)
        segs = [segmentar_articulo(f.get("texto") or "") or [f.get("texto") or ""] for f in cand]
        entrada += len(usuario_lote(hechos, "", cand, segs)) / 3.3 + 3500
        salida += args.salida_estimada + 1500
        llamadas += 2
    usd = entrada / 1e6 * (args.usd_millon_entrada or 0) + salida / 1e6 * (args.usd_millon_salida or 0)
    print(f"estimación: {len(casos)} casos, {llamadas} llamadas, ~{entrada:,.0f} tokens de entrada, ~{salida:,.0f} de salida, "
          f"~{usd:.3f} USD (acumulado {gasto_acumulado():.3f} de {TOPE_TAREA_USD})")
    return {"entrada": entrada, "salida": salida, "usd": usd}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--variante", choices=["1", "2", *VARIANTES_IDS], default="1")
    ap.add_argument("--subconjunto", choices=["desarrollo", "prueba", "todos"], default="todos",
                    help="división fija de los casos evaluables (semilla 20261110): 40 desarrollo / 21 prueba")
    ap.add_argument("--max-salida", type=int, default=16000, help="max_completion_tokens por llamada (Azure OpenAI)")
    ap.add_argument("--sin-registro", action="store_true", help="no escribe en el registro JSONL ni en la tabla")
    ap.add_argument("--estimar", action="store_true", help="solo estima tokens y USD de la corrida y sale")
    ap.add_argument("--salida-estimada", type=int, default=5000, help="tokens de salida supuestos por llamada")
    ap.add_argument("--candidatos", type=int, default=30)
    ap.add_argument("--lote", type=int, default=0, help="candidatos por llamada (0 = todos en una)")
    ap.add_argument("--cadena", default="gemini-3.5-flash,gemini-3.5-flash-lite")
    ap.add_argument("--proveedor", choices=["gemini", "azure-openai"], default="gemini",
                    help="azure-openai: despliegues del recurso oai-kerna (AZURE_OPENAI_ENDPOINT/KEY en el entorno)")
    ap.add_argument("--sin-anonimizar", action="store_true",
                    help="NO pasar el texto por el anonimizador (por defecto sí, como en producción)")
    ap.add_argument("--tope-usd", type=float, default=None, help="aborta si la estimación previa lo supera")
    ap.add_argument("--esperas", default="", help="esperas ante 429/5xx por nivel, en s (vacío = pasa al siguiente modelo)")
    ap.add_argument("--concurrencia", type=int, default=3)
    ap.add_argument("--campo", default="texto_original", choices=["texto_original", "resumen_parafraseado"])
    ap.add_argument("--mapeo", choices=rr.MAPEOS, default="concordancia")
    ap.add_argument("--usd-millon-entrada", type=float, default=None, help="precio de lista (no verificado si se omite)")
    ap.add_argument("--usd-millon-salida", type=float, default=None)
    args = ap.parse_args(argv)
    TOPE.update(usd=args.tope_usd, pe=args.usd_millon_entrada or 0.0, ps=args.usd_millon_salida or 0.0)
    inicio = time.monotonic()
    crudo = rr.DATASET.read_bytes()
    casos = json.loads(crudo)["casos"]
    corpus = rr.articulos_vigentes(COLECCION)
    division = dividir(casos, corpus, args.mapeo)
    LIBRO.parent.mkdir(exist_ok=True)
    (AQUI / "registro" / "division_evaluador.json").write_text(json.dumps(
        {"semilla": rr.SEMILLA, **{k: [casos[i]["id"] for i in v] for k, v in division.items()}}, ensure_ascii=False))
    casos = [casos[i] for i in division[args.subconjunto]]
    textos = [rr.texto_consulta(c, args.campo) for c in casos]
    if not args.sin_anonimizar:
        textos = [anonimizador.anonimizar(t).texto for t in textos]
    vectores = rr.embeber(textos, rr.ruta_cache(PROVEEDOR, MODELO), None, MODELO, rr.embed_sync.DIMS)
    base_tops = rr.buscar(vectores, k=args.candidatos, coleccion=COLECCION)
    frag = textos_fragmentos(COLECCION)
    if args.variante.startswith("3"):
        est = estimar(args, casos, textos, base_tops, frag)
        if args.estimar or est["usd"] + gasto_acumulado() > TOPE_TAREA_USD:
            return 0 if args.estimar else sys.exit(f"estimación {est['usd']:.3f} USD + acumulado {gasto_acumulado():.3f} "
                                                   f"supera el tope de la tarea ({TOPE_TAREA_USD} USD)")
    niveles = [Nivel("oficial" if i == 0 else "respaldo", args.proveedor, m) for i, m in enumerate(args.cadena.split(","))]
    if args.proveedor == "azure-openai":
        cli = ClienteAzureOpenAI(os.environ["AZURE_OPENAI_ENDPOINT"], os.environ["AZURE_OPENAI_KEY"], timeout=300.0,
                                 esfuerzo=os.environ.get("KERNA_AZURE_OPENAI_ESFUERZO", "low"), max_salida=args.max_salida)
    else:
        cli = ClienteGemini(os.environ["GEMINI_API_KEY"], timeout=180.0)
    enr = Enrutador(niveles, cli, plazo_global=1800.0, umbral_fallas=10**6,
                    corte=180.0, esperas=tuple(float(x) for x in args.esperas.split(",") if x))
    gen = Generador(enr, args.cadena)
    tops_ev, st = asyncio.run(correr(args, casos, textos, base_tops, frag, gen, corpus))
    res_base = rr.evaluar(casos, [t[:rr.TOP_BUSQUEDA] for t in base_tops], corpus, args.mapeo)
    res_ev = rr.evaluar(casos, tops_ev, corpus, args.mapeo)

    def serie(res, k):
        return [d["metricas"][k] for d in res["detalle"] if d.get("metricas")]

    pareado = {k: rr.bootstrap_pareado(serie(res_ev, k), serie(res_base, k)) for k in ("recall5", "hit8", "ndcg10", "mrr")}
    res30 = rr.evaluar(casos, base_tops, corpus, args.mapeo)
    e30 = [d for d in res30["detalle"] if d.get("metricas")]
    hitN = sum(any(rr.articulo_de(t) in set(d["candidatos"]) for t in d["top"]) for d in e30) / len(e30)
    n = max(1, len(serie(res_ev, "recall5")))
    costo = None
    if args.usd_millon_entrada is not None and args.usd_millon_salida is not None:
        costo = st["te"] / 1e6 * args.usd_millon_entrada + st["ts"] / 1e6 * args.usd_millon_salida
    extra = {"evaluador": {"variante_prompt": args.variante, "subconjunto": args.subconjunto, "casos_evaluados": len(casos),
                           "gasto_acumulado_tarea_usd": gasto_acumulado(), "candidatos": args.candidatos, "lote": args.lote or args.candidatos,
                           "cadena": args.cadena, "esfuerzo_razonamiento": os.environ.get("KERNA_AZURE_OPENAI_ESFUERZO", "low"), "proveedor": args.proveedor, "anonimizado": not args.sin_anonimizar, "base": MODELO, "hit_en_candidatos": hitN, "estadisticas": st,
                           "tokens_por_consulta": {"entrada": st["te"] / n, "salida": st["ts"] / n},
                           "respuestas_por_modelo": gen.por_modelo, "llamadas_nuevas": gen.llamadas, "respuestas_de_cache": gen.aciertos,
                           "latencia_caso_ms": {"mediana": rr.percentil(st["latencia_caso_ms"], 50), "p95": rr.percentil(st["latencia_caso_ms"], 95),
                                                "casos_con_llamada_nueva": len(st["latencia_caso_ms"])},
                           "latencia_llamada_ms": {"mediana": rr.percentil(gen.ms, 50), "p95": rr.percentil(gen.ms, 95)},
                           "costo_usd": costo, "base_sin_evaluador": res_base["metricas_articulo"].get("global"),
                           "diferencia_pareada_vs_base": pareado, "semilla": rr.SEMILLA}}
    rr.imprimir(res_ev, args.campo)
    b, g = res_base["metricas_articulo"]["global"], res_ev["metricas_articulo"]["global"]
    print("base", {k: round(b[k], 3) for k in ("recall5", "hit8", "ndcg10", "mrr")},
          "evaluador", {k: round(g[k], 3) for k in ("recall5", "hit8", "ndcg10", "mrr")}, "hit@N", round(hitN, 3))
    print(json.dumps(extra["evaluador"], indent=1, default=str))
    if DIAG:
        g = [x for x in DIAG if x["gold"]]
        dist = {k: sum(y["puntaje"] == k for x in g for y in x["gold"]) for k in range(4)}
        print("diagnóstico: casos con gold en candidatos", len(g), "| puntaje de los artículos gold", dist,
              "| medias de candidatos con puntaje 0/1/2/3:", [round(sum(x["n_por_puntaje"][k] for x in DIAG) / len(DIAG), 1) for k in range(4)],
              "| gold en top5:", sum(x["gold_en_top5"] for x in g))
        extra["evaluador"]["diagnostico"] = {"gold_por_puntaje": dist, "casos_con_gold": len(g)}
    if args.sin_registro:
        return 0
    if st["fallido"] > 0.1 * max(1, len(casos)):
        print(f"NO SE REGISTRA: {st['fallido']} de {len(casos)} casos fallidos (cuota 429 u otra falla); repetir con --esperas",
              file=sys.stderr)
        return 1
    rr.registrar(res_ev, campo=args.campo, dataset=crudo, articulos_corpus=len(corpus), casos=len(casos),
                 duracion_s=time.monotonic() - inicio,
                 parametros={"modelo": MODELO, "proveedor": PROVEEDOR, "coleccion": COLECCION, "mapeo": args.mapeo,
                             "modelo_consulta": MODELO, "evaluador": args.cadena, "candidatos": args.candidatos,
                             "proveedor_llm": args.proveedor, "subconjunto": args.subconjunto, "anonimizado": not args.sin_anonimizar},
                 extra=extra, comando="medir_evaluador.py " + " ".join(argv if argv is not None else sys.argv[1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
