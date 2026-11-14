"""
Mide solo el reranker LLM listwise sobre las etapas guardadas de una corrida de `correr_revisor.py` (que ya guarda IDs
y puntajes del evaluador): no repite la recuperación ni el evaluador. Recalcula el texto de cada denuncia como la
cadena (anonimizado, solo en memoria), baja los fragmentos vigentes de Qdrant y reordena la ventana.
hit@5 = algún artículo esperado entre los 5 primeros (recall@5 por artículo). Solo IDs y números en la salida.

Uso (desde kerna/):
  operaciones/correr_evaluacion.sh KERNA_COLECCION=normativa_cl_x_e python3 evaluacion/medir_rerank_llm.py \
      --particion desarrollo --casos evaluacion/registro/casos_...json --fuente evaluador --ventana 35 \
      --salida evaluacion/registro/rerank-llm-....json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import correr_revisor as cr  # noqa: E402
import recall_retriever as rr  # noqa: E402
from kerna_comun import anonimizador  # noqa: E402
from kerna_nucleo.api import proveedores_reales  # noqa: E402
from kerna_nucleo.config import Config  # noqa: E402
from kerna_nucleo.enrutador import PlazoAgotado  # noqa: E402
from kerna_nucleo.reranker_llm import RerankerLLM  # noqa: E402


def hit5(ids: list[str], esperados: set[str]) -> float:
    return float(any(rr.articulo_de(x) in esperados for x in ids[:5]))


def ordenar_eval(r: dict) -> list[str]:
    return [x[0] for x in (r.get("evaluador_orden") or [])]


async def correr(a, c: Config) -> dict:
    caso_dat, triage = cr.cargar_casos(a.particion, a.extra_casos)
    previos = {x["id"]: x for x in json.loads(Path(a.casos).read_text())}
    alm, orq = cr.construir(c, a.modelo)
    prov = proveedores_reales(c)
    frags = {f["fragmento_id"]: dict(f, vigente=True) for f in await prov.qdrant.fragmentos_vigentes(c.coleccion)
             if f.get("tipo") != "meta" and f.get("fragmento_id")}
    rr_llm = RerankerLLM(orq.enrutador.generar, a.ventana, a.voto_eval, permutaciones=a.permutaciones, criterios=a.criterios,
                        voto_retriever=a.voto_ret)
    sem = asyncio.Semaphore(a.concurrencia)
    filas: list[dict] = []

    async def uno(caso):
        t = triage[caso["id"]]
        r = previos.get(caso["id"])
        if t["en_alcance"] == "control" or r is None or not (r.get("evaluador_orden") or r.get("candidatos")):
            return
        esp = set(t["articulos_corregidos"])
        orden_eval = ordenar_eval(r)
        base = orden_eval if a.fuente == "evaluador" and orden_eval else (r.get("candidatos") or [])
        ventana = [frags[i] for i in base[: a.ventana] if i in frags]
        if len(ventana) < 2:
            return
        texto = anonimizador.anonimizar(rr.texto_consulta(caso, "texto_original")).texto
        async with sem:
            try:
                res = await rr_llm.reordenar(texto, ventana, time.time(), orden_eval, r.get("candidatos") or [])
            except PlazoAgotado:
                print(f"{caso['id']}: plazo agotado", flush=True)
                return
        nuevo = [f["fragmento_id"] for f in res.fragmentos]
        filas.append({"id": caso["id"], "ley": caso["ley_principal"], "usado": res.usado, "motivo": res.motivo,
                      "antes": hit5(base, esp), "despues": hit5(nuevo, esp),
                      "hit_ventana": float(any(rr.articulo_de(x) in esp for x in base[: a.ventana])),
                      "tokens": res.tokens_entrada + res.tokens_salida, "top5": nuevo[:5]})
        print(f"{caso['id']}: {filas[-1]['antes']} -> {filas[-1]['despues']}", flush=True)

    await asyncio.gather(*(uno(x) for x in caso_dat))
    return {"filas": sorted(filas, key=lambda f: f["id"])}


def resumir(filas: list[dict]) -> dict:
    out = {}
    grupos = defaultdict(list)
    for f in filas:
        grupos["global"].append(f)
        grupos[f["ley"]].append(f)
    for g, fs in grupos.items():
        ant, des = [f["antes"] for f in fs], [f["despues"] for f in fs]
        ic = lambda v: [round(x, 3) for x in rr.bootstrap_ic(v)]  # noqa: E731
        out[g] = {"n": len(fs), "antes": round(sum(ant) / len(fs), 3), "antes_ic": ic(ant),
                  "despues": round(sum(des) / len(fs), 3), "despues_ic": ic(des),
                  "hit_ventana": round(sum(f["hit_ventana"] for f in fs) / len(fs), 3),
                  "pareado": {k: ([round(x, 3) for x in v] if isinstance(v, list) else round(v, 3))
                              for k, v in rr.bootstrap_pareado(des, ant).items()},
                  "fallidos": sum(not f["usado"] for f in fs)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", required=True)
    ap.add_argument("--extra-casos")
    ap.add_argument("--casos", required=True, help="salida de correr_revisor.py (con evaluador_orden y candidatos)")
    ap.add_argument("--fuente", choices=["evaluador", "retriever"], default="evaluador")
    ap.add_argument("--ventana", type=int, default=35)
    ap.add_argument("--voto-eval", type=float, default=0.0)
    ap.add_argument("--voto-ret", type=float, default=0.0)
    ap.add_argument("--criterios", action="store_true")
    ap.add_argument("--permutaciones", type=int, default=2)
    ap.add_argument("--modelo", default="gpt-5-nano")
    ap.add_argument("--concurrencia", type=int, default=4)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args(argv)
    c = Config.desde_entorno()
    res = asyncio.run(correr(a, c))
    res.update(resumen=resumir(res["filas"]), parametros={k: v for k, v in vars(a).items()},
               coleccion=c.coleccion, comando="medir_rerank_llm.py " + " ".join(argv if argv is not None else sys.argv[1:]),
               fecha=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    Path(a.salida).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for g, m in res["resumen"].items():
        print(f"{g:15} n={m['n']} antes={m['antes']} {m['antes_ic']} despues={m['despues']} {m['despues_ic']} "
              f"ventana={m['hit_ventana']} pareado={m['pareado']} fallidos={m['fallidos']}")


if __name__ == "__main__":
    main()
