"""
Medición del reranker (Voyage rerank-2.5 / rerank-2.5-lite por API, o bge-reranker-v2-m3 abierto que corre en el
job de Azure) sobre los 30 primeros del retriever.

Base: voyage-4-large (normativa_cl, producción) o voyage-law-2 (normativa_cl_eval_voyage-law-2), con los vectores
de consulta guardados (sin volver a vectorizar). Se recuperan los 30 más cercanos con filtro vigente=true, se
reordenan con el reranker (consulta = texto del caso, documento = `texto` del fragmento, como en el núcleo) y se
miden con las mismas métricas de recall_retriever.py (mapeo `concordancia`, recall@5 por artículo, nDCG@10, MRR).
La diferencia contra la base sin reranker usa bootstrap pareado con la semilla 20261110.

Uso (desde kerna/, con VOYAGE_API_KEY y QDRANT_* en el entorno):
  python3 evaluacion/medir_rerank.py --base voyage-4-large --reranker rerank-2.5 [--campo texto_original]

bge-reranker-v2-m3 no corre en este equipo: en dos pasos,
  python3 evaluacion/medir_rerank.py --base voyage-4-large --reranker bge-reranker-v2-m3 --accion preparar
      (escribe job_embeddings/datos/rerank_candidatos.json; reconstruir la imagen del job y lanzarlo con
       MODELOS=bge-reranker-v2-m3, ver job_embeddings/README.md; el job deja su orden en Qdrant)
  python3 evaluacion/medir_rerank.py --base voyage-4-large --reranker bge-reranker-v2-m3   (lee ese resultado)
Las respuestas del reranker se guardan en datos/rerank_<...>.json (excluido de git) para repetir sin pagar.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import recall_retriever as rr  # noqa: E402

CANDIDATOS = 30
SALIDA_TOP = 10
URL = "https://api.voyageai.com/v1/rerank"
PRECIOS_RERANK = {"rerank-2.5": 0.05, "rerank-2.5-lite": 0.02,    # USD por millón de tokens (precio de lista de Voyage)
                  "bge-reranker-v2-m3": 0.0}                       # abierto: sin costo por token (cómputo del contenedor)
ABIERTOS = {"bge-reranker-v2-m3"}
CANDIDATOS_JOB = AQUI / "job_embeddings" / "datos" / "rerank_candidatos.json"
BASES = {"voyage-4-large": ("normativa_cl", "voyage", "voyage-4-large"),
         "voyage-law-2": ("normativa_cl_eval_voyage-law-2", "voyage", "voyage-law-2")}


def textos_fragmentos(coleccion: str) -> dict[str, str]:
    out, offset = {}, None
    while True:
        body = {"filter": rr._FILTRO_VIGENTE, "limit": 256, "with_payload": ["fragmento_id", "texto"], "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        r = rr.qdrant(f"/collections/{coleccion}/points/scroll", body, method="POST")["result"]
        out.update({p["payload"]["fragmento_id"]: p["payload"].get("texto", "") for p in r["points"]})
        offset = r.get("next_page_offset")
        if offset is None:
            return out


def llamar_rerank(consulta: str, docs: list[str], modelo: str, clave: str, intentos: int = 8) -> dict:
    cuerpo = json.dumps({"model": modelo, "query": consulta, "documents": docs, "top_k": SALIDA_TOP,
                         "truncation": True}).encode()
    for i in range(intentos):
        t0 = time.monotonic()
        req = urllib.request.Request(URL, cuerpo, {"Authorization": f"Bearer {clave}", "Content-Type": "application/json"})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60))
            return {"ms": (time.monotonic() - t0) * 1000, "tokens": d["usage"]["total_tokens"],
                    "orden": [[x["index"], x["relevance_score"]] for x in d["data"]]}
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or i == intentos - 1:
                raise
            time.sleep(min(60, 5 * (i + 1)))
        except OSError:
            if i == intentos - 1:
                raise
            time.sleep(5 * (i + 1))


def preparar_candidatos(casos, textos, base_tops, frag, reranker, base) -> int:
    """Escribe los candidatos (texto de cada fragmento) que el job de Azure reordenará; no ejecuta ningún modelo."""
    sel = [{"id": c["id"], "consulta": t, "ids": [x["fragmento_id"] for x in top],
            "docs": [frag[x["fragmento_id"]] for x in top]}
           for c, t, top in zip(casos, textos, base_tops) if c["ley_principal"] != "ninguna"]
    CANDIDATOS_JOB.parent.mkdir(exist_ok=True)
    CANDIDATOS_JOB.write_text(json.dumps({"reranker": reranker, "base": base, "casos": sel}, ensure_ascii=False))
    print(f"{len(sel)} casos x {CANDIDATOS} candidatos -> {CANDIDATOS_JOB}")
    return 0


def leer_resultado_job(reranker: str, base: str) -> dict:
    """Orden y tiempo que dejó el job en Qdrant: {caso_id: {"ms", "tokens", "orden"}}."""
    col, out, offset = f"normativa_cl_eval_rerank_{reranker}_{base}", {}, None
    while True:
        body = {"limit": 256, "with_payload": True, "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        r = rr.qdrant(f"/collections/{col}/points/scroll", body, method="POST")["result"]
        out.update({p["payload"]["caso_id"]: {"ms": p["payload"]["ms"], "tokens": 0, "orden": p["payload"]["orden"]}
                    for p in r["points"]})
        offset = r.get("next_page_offset")
        if offset is None:
            return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", choices=list(BASES), required=True)
    ap.add_argument("--reranker", choices=list(PRECIOS_RERANK), required=True)
    ap.add_argument("--accion", choices=["medir", "preparar"], default="medir")
    ap.add_argument("--campo", default="texto_original", choices=["texto_original", "resumen_parafraseado"])
    ap.add_argument("--mapeo", choices=rr.MAPEOS, default="concordancia")
    args = ap.parse_args(argv)
    coleccion, proveedor, modelo = BASES[args.base]
    abierto = args.reranker in ABIERTOS
    clave = "" if abierto else os.environ["VOYAGE_API_KEY"]
    inicio = time.monotonic()
    crudo = rr.DATASET.read_bytes()
    casos = json.loads(crudo)["casos"]
    corpus = rr.articulos_vigentes(coleccion)
    textos = [rr.texto_consulta(c, args.campo) for c in casos]
    vectores = rr.embeber(textos, rr.ruta_cache(proveedor, modelo), None, modelo, rr.embed_sync.DIMS)
    base_tops = rr.buscar(vectores, k=CANDIDATOS, coleccion=coleccion)
    frag = textos_fragmentos(coleccion)
    if args.accion == "preparar":
        if not abierto:
            ap.error("--accion preparar es solo para rerankers abiertos")
        return preparar_candidatos(casos, textos, base_tops, frag, args.reranker, args.base)
    cache_path = AQUI / "datos" / f"rerank_{args.base}_{args.reranker}_{args.campo}.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    if abierto and not cache:
        cache = leer_resultado_job(args.reranker, args.base)
        cache_path.write_text(json.dumps(cache))
    tops_rr = []
    for caso, texto, top in zip(casos, textos, base_tops):
        if caso["ley_principal"] != "ninguna" and caso["id"] not in cache and not abierto:
            cache[caso["id"]] = llamar_rerank(texto, [frag[t["fragmento_id"]] for t in top], args.reranker, clave)
            cache_path.write_text(json.dumps(cache))
            time.sleep(0.5)
        if caso["id"] in cache:
            tops_rr.append([dict(top[i], score=s) for i, s in cache[caso["id"]]["orden"]])
        else:
            tops_rr.append(top[:SALIDA_TOP])
    res_base = rr.evaluar(casos, [t[:SALIDA_TOP] for t in base_tops], corpus, args.mapeo)
    res_rr = rr.evaluar(casos, tops_rr, corpus, args.mapeo)

    def serie(res, k):
        return [d["metricas"][k] for d in res["detalle"] if d.get("metricas")]

    pareado = {k: rr.bootstrap_pareado(serie(res_rr, k), serie(res_base, k)) for k in ("recall5", "hit8", "ndcg10", "mrr")}
    usados = [v for v in cache.values()]
    ms = [v["ms"] for v in usados]
    tokens = sum(v["tokens"] for v in usados)
    # Hit@30 de la base: techo del reranker.
    res30 = rr.evaluar(casos, base_tops, corpus, args.mapeo)
    ev = [d for d in res30["detalle"] if d.get("metricas")]
    hit30 = sum(any(rr.articulo_de(t) in set(d["candidatos"]) for t in d["top"]) for d in ev) / len(ev)
    extra = {"reranker": {"modelo": args.reranker, "candidatos": CANDIDATOS, "base": args.base,
                          "latencia_rerank": {"p95_ms": rr.percentil(ms, 95), "mediana_ms": rr.percentil(ms, 50),
                                              "muestras": len(ms)},
                          "tokens": {"total": tokens, "por_consulta": tokens / len(ms) if ms else None},
                          "ejecucion": "job de Azure, CPU" if abierto else "API",
                          "costo_usd": tokens / 1e6 * PRECIOS_RERANK[args.reranker],
                          "usd_por_millon_tokens": PRECIOS_RERANK[args.reranker],
                          "base_sin_reranker": res_base["metricas_articulo"].get("global"),
                          "hit_en_30": hit30,
                          "diferencia_pareada_vs_base": pareado, "semilla": rr.SEMILLA}}
    imprimir = rr.imprimir
    imprimir(res_rr, args.campo)
    print(json.dumps({k: extra["reranker"][k] for k in ("latencia_rerank", "tokens", "costo_usd", "hit_en_30",
                                                         "diferencia_pareada_vs_base")}, indent=1))
    b, g = res_base["metricas_articulo"]["global"], res_rr["metricas_articulo"]["global"]
    print("base", {k: round(b[k], 3) for k in ("recall5", "hit8", "ndcg10", "mrr")},
          "rerank", {k: round(g[k], 3) for k in ("recall5", "hit8", "ndcg10", "mrr")})
    rr.registrar(res_rr, campo=args.campo, dataset=crudo, articulos_corpus=len(corpus), casos=len(casos),
                 duracion_s=time.monotonic() - inicio,
                 parametros={"modelo": modelo, "proveedor": proveedor, "coleccion": coleccion, "mapeo": args.mapeo,
                             "modelo_consulta": modelo, "reranker": args.reranker, "candidatos": CANDIDATOS},
                 extra=extra, comando="medir_rerank.py " + " ".join(argv if argv is not None else sys.argv[1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
