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
from kerna_nucleo.proveedores.gemini import ClienteGemini  # noqa: E402

CACHE = AQUI / "datos" / "evaluador_cache.json"
COLECCION, PROVEEDOR, MODELO = "normativa_cl", "voyage", "voyage-4-large"


def textos_fragmentos(coleccion: str) -> dict[str, dict]:
    out, offset = {}, None
    while True:
        body = {"filter": rr._FILTRO_VIGENTE, "limit": 256, "with_vector": False,
                "with_payload": ["fragmento_id", "texto", "norma", "tipo_numero", "articulo"]}
        if offset is not None:
            body["offset"] = offset
        r = rr.qdrant(f"/collections/{coleccion}/points/scroll", body, method="POST")["result"]
        out.update({p["payload"]["fragmento_id"]: p["payload"] for p in r["points"]})
        offset = r.get("next_page_offset")
        if offset is None:
            return out


class Generador:
    """Envuelve el enrutador con una caché en disco (clave = cadena + prompts) y cuenta tokens."""

    def __init__(self, enrutador: Enrutador, cadena: str):
        self.enr, self.cadena = enrutador, cadena
        self.cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        self.llamadas = self.aciertos = 0
        self.ms: list[float] = []
        self.por_modelo: dict[str, int] = {}

    async def __call__(self, sistema, usuario, esquema, validar, inicio):
        k = hashlib.sha256(f"{sistema}|{usuario}".encode()).hexdigest()
        if k in self.cache:
            self.aciertos += 1
            c = self.cache[k]
            self.por_modelo[c["modelo"]] = self.por_modelo.get(c["modelo"], 0) + 1
            return Resultado(validar(c["datos"]), "cache", "gemini", c["modelo"], c["te"], c["ts"])
        t0 = time.monotonic()
        r = await self.enr.generar(sistema, usuario, esquema, validar, time.time())
        self.ms.append((time.monotonic() - t0) * 1000)
        print(f"llamada {r.modelo} {self.ms[-1] / 1000:.0f}s tokens {r.tokens_entrada}/{r.tokens_salida}", flush=True)
        self.llamadas += 1
        self.por_modelo[r.modelo] = self.por_modelo.get(r.modelo, 0) + 1
        self.cache[k] = {"datos": {"resultados": r.datos}, "modelo": r.modelo, "te": r.tokens_entrada,
                         "ts": r.tokens_salida}
        CACHE.write_text(json.dumps(self.cache, ensure_ascii=False))
        return r


async def correr(args, casos, textos, base_tops, frag, gen, corpus):
    ev = Evaluador(gen, variante=args.variante, lote=args.lote, salida=rr.TOP_BUSQUEDA)
    sem = asyncio.Semaphore(args.concurrencia)
    stats = {"usado": 0, "fallido": 0, "ninguno": 0, "desc_id": 0, "desc_cita": 0, "aplican": 0, "te": 0, "ts": 0}

    async def uno(caso, texto, top):
        # Solo los casos con candidatos mapeables entran en las métricas por artículo: el resto no se envía al LLM.
        if caso["ley_principal"] == "ninguna" or not rr.normalizar_candidatos(
                caso["articulos_candidatos"], corpus, args.mapeo)[0]:
            return top[:rr.TOP_BUSQUEDA]
        cand = [dict(frag[t["fragmento_id"]], score=t["score"], id_norma=t["id_norma"]) for t in top]
        async with sem:
            r = await ev.evaluar(texto, cand, time.time())
        stats["usado"] += r.usado
        stats["fallido"] += r.motivo == "evaluador_fallido"
        stats["ninguno"] += r.motivo == "ninguno_aplica"
        stats["desc_id"] += r.descartados_id
        stats["desc_cita"] += r.descartados_cita
        stats["aplican"] += r.aplican
        stats["te"] += r.tokens_entrada
        stats["ts"] += r.tokens_salida
        return [{"fragmento_id": f["fragmento_id"], "id_norma": f["id_norma"], "score": f.get("confianza_evaluador", 0)}
                for f in r.fragmentos]

    return await asyncio.gather(*[uno(c, t, top) for c, t, top in zip(casos, textos, base_tops)]), stats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--variante", choices=["1", "2"], default="1")
    ap.add_argument("--candidatos", type=int, default=30)
    ap.add_argument("--lote", type=int, default=0, help="candidatos por llamada (0 = todos en una)")
    ap.add_argument("--cadena", default="gemini-3.5-flash,gemini-3.5-flash-lite")
    ap.add_argument("--esperas", default="", help="esperas ante 429/5xx por nivel, en s (vacío = pasa al siguiente modelo)")
    ap.add_argument("--concurrencia", type=int, default=3)
    ap.add_argument("--campo", default="texto_original", choices=["texto_original", "resumen_parafraseado"])
    ap.add_argument("--mapeo", choices=rr.MAPEOS, default="concordancia")
    ap.add_argument("--usd-millon-entrada", type=float, default=None, help="precio de lista (no verificado si se omite)")
    ap.add_argument("--usd-millon-salida", type=float, default=None)
    args = ap.parse_args(argv)
    inicio = time.monotonic()
    crudo = rr.DATASET.read_bytes()
    casos = json.loads(crudo)["casos"]
    corpus = rr.articulos_vigentes(COLECCION)
    textos = [rr.texto_consulta(c, args.campo) for c in casos]
    vectores = rr.embeber(textos, rr.ruta_cache(PROVEEDOR, MODELO), None, MODELO, rr.embed_sync.DIMS)
    base_tops = rr.buscar(vectores, k=args.candidatos, coleccion=COLECCION)
    frag = textos_fragmentos(COLECCION)
    niveles = [Nivel("oficial" if i == 0 else "respaldo", "gemini", m) for i, m in enumerate(args.cadena.split(","))]
    enr = Enrutador(niveles, ClienteGemini(os.environ["GEMINI_API_KEY"], timeout=180.0), plazo_global=600.0,
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
    extra = {"evaluador": {"variante_prompt": args.variante, "candidatos": args.candidatos, "lote": args.lote or args.candidatos,
                           "cadena": args.cadena, "base": MODELO, "hit_en_candidatos": hitN, "estadisticas": st,
                           "tokens_por_consulta": {"entrada": st["te"] / n, "salida": st["ts"] / n},
                           "respuestas_por_modelo": gen.por_modelo, "llamadas_nuevas": gen.llamadas, "respuestas_de_cache": gen.aciertos,
                           "latencia_llamada_ms": {"mediana": rr.percentil(gen.ms, 50), "p95": rr.percentil(gen.ms, 95)},
                           "costo_usd": costo, "base_sin_evaluador": res_base["metricas_articulo"].get("global"),
                           "diferencia_pareada_vs_base": pareado, "semilla": rr.SEMILLA}}
    rr.imprimir(res_ev, args.campo)
    b, g = res_base["metricas_articulo"]["global"], res_ev["metricas_articulo"]["global"]
    print("base", {k: round(b[k], 3) for k in ("recall5", "hit8", "ndcg10", "mrr")},
          "evaluador", {k: round(g[k], 3) for k in ("recall5", "hit8", "ndcg10", "mrr")}, "hit@N", round(hitN, 3))
    print(json.dumps(extra["evaluador"], indent=1, default=str))
    rr.registrar(res_ev, campo=args.campo, dataset=crudo, articulos_corpus=len(corpus), casos=len(casos),
                 duracion_s=time.monotonic() - inicio,
                 parametros={"modelo": MODELO, "proveedor": PROVEEDOR, "coleccion": COLECCION, "mapeo": args.mapeo,
                             "modelo_consulta": MODELO, "evaluador": args.cadena, "candidatos": args.candidatos},
                 extra=extra, comando="medir_evaluador.py " + " ".join(argv if argv is not None else sys.argv[1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
