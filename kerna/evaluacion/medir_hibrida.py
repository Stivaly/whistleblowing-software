"""
Medición de la búsqueda híbrida (BM25 + densa por RRF) y de la multi-query por conductas del perfil.

Base: voyage-4-large (normativa_cl), vectores de consulta guardados (relatos anonimizados, como en producción),
filtro vigente=true, mapeo `concordancia`. Las listas por consulta (densa y BM25, profundidad 100) se fusionan con la
misma `bm25.rrf` que usa el retriever del núcleo. Las conductas salen de la extracción del perfil (variante `3m` del
evaluador por IDs, gpt-5-nano), cacheada en datos/evaluador_cache.json.

Particiones del triage (datos/triage_casos.json, solo casos "si"): `desarrollo` (jurídicos) para elegir y `prueba`
(reddit) solo para la variante elegida; `todos` = los 61 casos evaluables por artículo (referencia histórica).

Uso (desde kerna/; credenciales de pipeline_bcn/.env y AZURE_OPENAI_* en el entorno):
  PYTHONPATH=nucleo:comun python3 evaluacion/medir_hibrida.py --particion desarrollo            # rejilla del retriever
  ... --particion desarrollo --evaluador base,hibrida,h+mq3                                       # con evaluador por IDs
  ... --particion prueba --solo base,<elegida> --evaluador base,<elegida>
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "nucleo"))
sys.path.insert(0, str(AQUI.parent / "comun"))
import medir_evaluador as me  # noqa: E402
import recall_retriever as rr  # noqa: E402
from kerna_comun import anonimizador  # noqa: E402
from kerna_nucleo.bm25 import IndiceBM25, rrf  # noqa: E402
from kerna_nucleo.enrutador import Enrutador, Nivel  # noqa: E402
from kerna_nucleo.evaluador_ids import EvaluadorIds  # noqa: E402
from kerna_nucleo.proveedores.azure_openai import ClienteAzureOpenAI  # noqa: E402

REGISTRO = AQUI / "registro" / "hibrida_multiquery.jsonl"
TRIAGE = AQUI / "datos" / "triage_casos.json"
PROF = 100
N = 70
VARIANTE_PERFIL = "3m"
MODELO_LLM = "gpt-5-nano"


def configuraciones() -> dict[str, dict]:
    """nombre -> {hibrida, stemming, mq: None | {relato, peso, max}}."""
    c = {"base": {"hibrida": False, "stemming": True, "mq": None},
         "bm25_solo": {"bm25_solo": True, "hibrida": True, "stemming": True, "mq": None},
         "hibrida": {"hibrida": True, "stemming": True, "mq": None},
         "hibrida_sin_stemming": {"hibrida": True, "stemming": False, "mq": None}}
    for hib in (False, True):
        for relato in (True, False):
            for peso in ((1.0, 2.0) if relato else (1.0,)):
                for m in (3, 5, 8):
                    nom = f"{'h+' if hib else ''}mq{m}_{'relato' if relato else 'solo'}" + (f"_p{peso:g}" if relato else "")
                    c[nom] = {"hibrida": hib, "stemming": True, "mq": {"relato": relato, "peso": peso, "max": m}}
    for e in (15, 30):
        c[f"u{e}_hibrida"] = {"hibrida": True, "stemming": True, "mq": None, "extras": e}
        for m in (3, 5):
            for peso in (1.0, 2.0):
                c[f"u{e}_h+mq{m}_relato_p{peso:g}"] = {"hibrida": True, "stemming": True, "extras": e,
                                                       "mq": {"relato": True, "peso": peso, "max": m}}
        c[f"u{e}_mq3_relato_p2"] = {"hibrida": False, "stemming": True, "extras": e,
                                    "mq": {"relato": True, "peso": 2.0, "max": 3}}
    return c


def fragmentos_vigentes(coleccion: str) -> dict[str, dict]:
    out, offset = {}, None
    while True:
        body = {"filter": rr._FILTRO_VIGENTE, "limit": 256, "with_vector": False,
                "with_payload": ["fragmento_id", "id_norma", "texto", "norma", "tipo_numero", "articulo", "jerarquia"]}
        if offset is not None:
            body["offset"] = offset
        r = rr.qdrant(f"/collections/{coleccion}/points/scroll", body, method="POST")["result"]
        out.update({p["payload"]["fragmento_id"]: p["payload"] for p in r["points"]})
        offset = r.get("next_page_offset")
        if offset is None:
            return out


def fusionar(cfg: dict, densa_relato: list[str], densas_frases: list[list[str]], lex_relato: list[str],
             lex_frases: list[list[str]]) -> list[str]:
    """Ids ordenados por RRF según la configuración (misma lógica que Retriever._nube_fusionada)."""
    if cfg.get("bm25_solo"):
        return lex_relato[:N]
    mq = cfg["mq"]
    frases = densas_frases[: mq["max"]] if mq else []
    lfrases = lex_frases[: mq["max"]] if mq else []
    listas, pesos = [], []
    if not mq or mq["relato"] or not frases:
        w = mq["peso"] if (mq and frases) else 1.0
        listas.append(densa_relato)
        pesos.append(w)
        if cfg["hibrida"]:
            listas.append(lex_relato)
            pesos.append(w)
    for i, d in enumerate(frases):
        listas.append(d)
        pesos.append(1.0)
        if cfg["hibrida"]:
            listas.append(lfrases[i])
            pesos.append(1.0)
    fus = [i for i, _ in rrf(listas, 60, pesos)]
    e = cfg.get("extras")
    if e:      # unión: los N-e primeros de la densa del relato quedan protegidos; la fusión aporta hasta e nuevos
        base = densa_relato[: N - e]
        fijos = set(base)
        nuevos = [i for i in fus if i not in fijos][:e]
        pool = fijos | set(nuevos)
        return [i for i in fus if i in pool][:N]
    return fus[:N]


def metricas(casos, tops, corpus, mapeo):
    res = rr.evaluar(casos, [t[:rr.TOP_BUSQUEDA] for t in tops], corpus, mapeo)
    g = res["metricas_articulo"]["global"]
    ceil = rr.evaluar(casos, tops, corpus, mapeo)
    det = [d for d in ceil["detalle"] if d.get("metricas")]
    techo = {n: sum(any(rr.articulo_de(t) in set(d["candidatos"]) for t in d["top"][:n]) for d in det) / len(det)
             for n in (8, 30, 70)}
    por_ley = {k: {"casos_articulo": v["casos_articulo"], "recall_articulo": v["recall_articulo"]}
               for k, v in res["por_ley"].items()}
    return {"casos": g["casos_articulo"], "recall5": g["recall5"], "ic95": g["recall5_ic95"], "ndcg10": g["ndcg10"],
            "mrr": g["mrr"], "hit8": g["hit8"], "hit30": techo[30], "hit70": techo[70], "por_ley": por_ley}, res


def commit() -> str:
    return rr._commit()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", choices=["desarrollo", "prueba", "todos"], default="desarrollo")
    ap.add_argument("--solo", default="", help="configuraciones separadas por coma (por defecto todas)")
    ap.add_argument("--evaluador", default="", help="configuraciones para medir con el evaluador por IDs (variante 3m)")
    ap.add_argument("--tope-usd", type=float, default=0.8)
    ap.add_argument("--concurrencia", type=int, default=3)
    ap.add_argument("--sin-registro", action="store_true")
    args = ap.parse_args(argv)
    inicio = time.monotonic()
    crudo = rr.DATASET.read_bytes()
    todos = json.loads(crudo)["casos"]
    corpus = rr.articulos_vigentes(me.COLECCION)
    division = me.dividir(todos, corpus, "concordancia")
    triage = {e["id"]: e for e in json.loads(TRIAGE.read_text())["casos"]}
    ev_ids = [todos[i] for i in division["todos"]]
    if args.particion == "todos":
        casos = ev_ids
    else:
        casos = [c for c in ev_ids if triage.get(c["id"], {}).get("en_alcance") == "si"
                 and triage[c["id"]]["particion"] == args.particion]
    print(f"{args.particion}: {len(casos)} casos evaluables por artículo", flush=True)
    textos = [anonimizador.anonimizar(rr.texto_consulta(c, "texto_original")).texto for c in casos]
    cache_vec = rr.ruta_cache(me.PROVEEDOR, me.MODELO)
    vectores = rr.embeber(textos, cache_vec, None, me.MODELO, rr.embed_sync.DIMS)
    frag = fragmentos_vigentes(me.COLECCION)
    dens_relato = [[t["fragmento_id"] for t in lista] for lista in rr.buscar(vectores, k=PROF, coleccion=me.COLECCION)]
    id_norma = {i: f["id_norma"] for i, f in frag.items()}

    # perfiles (conductas) con gpt-5-nano, cacheados
    me.TOPE.update(usd=args.tope_usd, pe=0.05, ps=0.40)
    def crear_gen():     # cliente HTTP nuevo por bucle de eventos (no se puede reutilizar entre asyncio.run)
        cli = ClienteAzureOpenAI(os.environ["AZURE_OPENAI_ENDPOINT"], os.environ["AZURE_OPENAI_KEY"], timeout=300.0,
                                 esfuerzo=os.environ.get("KERNA_AZURE_OPENAI_ESFUERZO", "low"), max_salida=16000)
        enr = Enrutador([Nivel("oficial", "azure-openai", MODELO_LLM)], cli, plazo_global=1800.0,
                        umbral_fallas=10**6, corte=180.0, esperas=(30.0, 60.0))
        return me.Generador(enr, MODELO_LLM)
    gen = crear_gen()
    evid = EvaluadorIds(gen, variante=VARIANTE_PERFIL, salida=rr.TOP_BUSQUEDA)

    async def perfiles():
        sem = asyncio.Semaphore(args.concurrencia)

        async def uno(t):
            async with sem:
                return await evid.extraer_perfil(t, time.time())
        return await asyncio.gather(*[uno(t) for t in textos])
    perf = asyncio.run(perfiles())
    conductas = [p.conductas for p in perf]
    n_cond = [len(c) for c in conductas]
    print(f"perfiles: ok {sum(p.ok for p in perf)}/{len(perf)}; conductas por caso: media "
          f"{sum(n_cond) / len(n_cond):.1f}; llamadas nuevas {gen.llamadas}, de caché {gen.aciertos}; "
          f"gasto acumulado {me.gasto_acumulado():.3f} USD", flush=True)

    # vectores de las frases (una sola vez; caché por texto) y listas densas por frase
    frases = list(dict.fromkeys(f for c in conductas for f in c))
    vf = rr.embeber(frases, cache_vec, None, me.MODELO, rr.embed_sync.DIMS) if frases else []
    top_f = rr.buscar(vf, k=PROF, coleccion=me.COLECCION) if frases else []
    dens_frase = {f: [t["fragmento_id"] for t in lista] for f, lista in zip(frases, top_f)}

    indices = {st: IndiceBM25(((i, d["texto"]) for i, d in frag.items()), stemming=st) for st in (True, False)}

    def lex(st, texto):
        return [i for i, _ in indices[st].buscar(texto, PROF)]
    cfgs = configuraciones()
    elegidas = [x for x in args.solo.split(",") if x] or list(cfgs)
    salida, tops_por_cfg = {}, {}
    for nom in elegidas:
        cfg = cfgs[nom]
        st = cfg["stemming"]
        tops = []
        for i, t in enumerate(textos):
            fr = conductas[i]
            ids = fusionar(cfg, dens_relato[i], [dens_frase[f] for f in fr],
                           lex(st, t) if cfg["hibrida"] else [], [lex(st, f) for f in fr] if cfg["hibrida"] else [])
            tops.append([{"fragmento_id": x, "id_norma": id_norma[x], "score": 0.0} for x in ids if x in id_norma])
        m, _ = metricas(casos, tops, corpus, "concordancia")
        salida[nom] = m
        tops_por_cfg[nom] = tops
    print(f"\n{'configuración':<26}{'n':>3}{'recall@5':>9}{'IC95':>15}{'hit@8':>7}{'hit@30':>7}{'hit@70':>7}{'nDCG':>7}{'MRR':>7}")
    for nom, m in salida.items():
        print(f"{nom:<26}{m['casos']:>3}{m['recall5']:>9.3f}  [{m['ic95'][0]:.2f},{m['ic95'][1]:.2f}]"
              f"{m['hit8']:>7.3f}{m['hit30']:>7.3f}{m['hit70']:>7.3f}{m['ndcg10']:>7.3f}{m['mrr']:>7.3f}")

    # con el evaluador por IDs (gpt-5-nano, 70 candidatos, perfil 3m reutilizado de la caché)
    ev_res = {}
    nombres_ev = [x for x in args.evaluador.split(",") if x]
    for nom in nombres_ev:
        if nom not in tops_por_cfg:
            raise SystemExit(f"{nom}: incluir en --solo")
    a = SimpleNamespace(variante=VARIANTE_PERFIL, lote=0, concurrencia=args.concurrencia, mapeo="concordancia")

    async def evaluadores():     # un solo bucle de eventos: el cliente HTTP no se puede reutilizar entre bucles
        g2 = crear_gen()
        return [await me.correr(a, casos, textos, tops_por_cfg[n], frag, g2, corpus) for n in nombres_ev]
    for nom, (tops_ev, st) in zip(nombres_ev, asyncio.run(evaluadores()) if nombres_ev else []):
        m, _ = metricas(casos, tops_ev, corpus, "concordancia")
        ev_res[nom] = {**m, "tokens_entrada": st["te"], "tokens_salida": st["ts"], "fallidos": st["fallido"]}
        print(f"evaluador [{nom}] recall@5 {m['recall5']:.3f} IC [{m['ic95'][0]:.2f},{m['ic95'][1]:.2f}] "
              f"ndcg {m['ndcg10']:.3f} mrr {m['mrr']:.3f} (fallidos {st['fallido']}; gasto {me.gasto_acumulado():.3f} USD)",
              flush=True)
        for k, v in m["por_ley"].items():
            print(f"   {k}: {v['recall_articulo']}")
    if not args.sin_registro:
        entrada = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "commit": commit(),
                   "comando": "medir_hibrida.py " + " ".join(argv if argv is not None else sys.argv[1:]),
                   "particion": args.particion, "casos": [c["id"] for c in casos],
                   "dataset_sha256": hashlib.sha256(crudo).hexdigest(),
                   "parametros": {"modelo_embedding": me.MODELO, "coleccion": me.COLECCION, "rrf_k": 60,
                                  "profundidad_listas": PROF, "candidatos": N, "variante_perfil": VARIANTE_PERFIL,
                                  "llm": MODELO_LLM, "mapeo": "concordancia", "bm25": {"k1": 1.5, "b": 0.75}},
                   "conductas_por_caso": {"media": sum(n_cond) / len(n_cond), "perfiles_ok": sum(p.ok for p in perf)},
                   "retriever": salida, "con_evaluador": ev_res, "duracion_s": round(time.monotonic() - inicio, 1),
                   "gasto_acumulado_usd": me.gasto_acumulado()}
        with REGISTRO.open("a") as f:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
        print(f"registrado en {REGISTRO.relative_to(AQUI.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
