"""
Medición base por set, ley y configuración: recall@5 por artículo (IC 95 %) y hit@5/10/20/70 para saber si el
problema es traer, ordenar o revisar. Solo IDs y números; no escribe textos de denuncias.

Configuraciones:
  retriever   búsqueda densa sola (voyage-4-large, texto_original, como `recall_retriever.py`), top-70.
  candidatos  lo que entrega el retriever de la cadena (híbrida + multiquery) al evaluador, hasta 70 fragmentos.
  evaluador   los top-5 que deja el evaluador por IDs (antes del generador).
  cadena      las sugerencias del generador (≤ 5 artículos por confianza) = cadena sin revisor.
  revisor     las mismas sin los vetados, por confianza del revisor (KERNA_REVISOR=1).
La cadena y el revisor salen de una misma corrida con KERNA_REVISOR=1 (el revisor va después del generador y no
cambia lo que sugiere el generador); un caso que no llega a `completada` (revisión manual) cuenta como fallo.
`hit@k` = algún artículo esperado entre los k primeros fragmentos (recall@5 por artículo del KPI = hit@5).

Uso (desde kerna/):
  operaciones/correr_evaluacion.sh python3 evaluacion/medir_base_b2.py --salida evaluacion/registro/base-b2-AAAAMMDD.json \
      --set desarrollo=evaluacion/registro/casos_b2_desarrollo.json ...
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import recall_retriever as rr  # noqa: E402

PROFUNDIDADES = (5, 10, 20, 70)
TRIAGE = AQUI / "datos" / "triage_casos.json"
EXTRA = {"prueba2": AQUI / "datos" / "denuncias_nuevas_20261112.json",
         "prueba3": AQUI / "datos" / "denuncias_sinteticas_20261113_prueba3.json",
         "afinar": AQUI / "datos" / "denuncias_complejas_20261114_etiquetadas.json",
         "medir_complejas": AQUI / "datos" / "denuncias_complejas_20261114_etiquetadas.json",
         "desarrollo_nuevo": AQUI / "datos" / "denuncias_desarrollo_20261115_etiquetadas.json"}
SETS = ("desarrollo", "prueba", "prueba2", "prueba3")
SETS_VALIDOS = SETS + ("afinar", "medir_complejas", "desarrollo_nuevo")
OPCIONES = {"coleccion": None, "dedup": False}   # --coleccion / --dedup-literales (experimento de enriquecimiento)


def hit(lista: list[str], esperados: set[str], k: int) -> float:
    """1 si algún artículo esperado está entre los k primeros (se normaliza fragmento -> artículo)."""
    return float(any(rr.articulo_de(x) in esperados for x in lista[:k]))


def resumen(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0, "valor": None, "ic95": [None, None]}
    lo, hi = rr.bootstrap_ic(valores)
    return {"n": len(valores), "valor": round(sum(valores) / len(valores), 4), "ic95": [round(lo, 4), round(hi, 4)]}


def casos_set(nombre: str, corpus: set[str]) -> list[dict]:
    """Casos del set con esperados en el corpus (los controles quedan fuera del recall) y su ley principal."""
    dataset = json.loads(rr.DATASET.read_bytes())["casos"]
    triage = json.loads(TRIAGE.read_text())
    if nombre in EXTRA:
        extra, tri_extra = rr.cargar_extra_casos(EXTRA[nombre])
        dataset += extra
        triage = {**triage, "casos": triage["casos"] + tri_extra["casos"]}
    casos = rr.aplicar_etiqueta_corregida(rr.filtrar_por_triage(dataset, triage, nombre), triage)
    out = []
    for c in casos:
        esp = set(c["_candidatos_ids"]) & corpus
        if c["ley_principal"] != "ninguna" and esp:
            out.append({"id": c["id"], "ley": c["ley_principal"], "esperados": esp, "caso": c})
    return out


def agrupar(filas: list[dict], campos: list[str]) -> dict:
    """Por ley y global: resumen (valor + IC) de cada campo."""
    por = defaultdict(list)
    for f in filas:
        por[f["ley"]].append(f)
        por["global"].append(f)
    return {g: {c: resumen([f[c] for f in fs if f.get(c) is not None]) for c in campos} for g, fs in sorted(por.items())}


def medir_retriever(nombre: str, casos: list[dict], corpus: set[str]) -> tuple[dict, dict]:
    textos = [rr.texto_consulta(c["caso"], "texto_original") for c in casos]
    vectores = rr.embeber(textos)
    tops = rr.buscar(vectores, k=max(PROFUNDIDADES), coleccion=OPCIONES["coleccion"], dedup_literales=OPCIONES["dedup"])
    filas, ranking = [], []
    for c, top in zip(casos, tops):
        ids = [t["fragmento_id"] for t in top]
        fila = {"id": c["id"], "ley": c["ley"], **{f"hit{k}": hit(ids, c["esperados"], k) for k in PROFUNDIDADES}}
        filas.append(fila)
        ranking.append({"id": c["id"], "ley": c["ley"], "esperados": sorted(c["esperados"]),
                        "top5": [rr.articulo_de(i) for i in ids[:5]],
                        "pos_primer_esperado": next((i + 1 for i, x in enumerate(ids) if rr.articulo_de(x) in c["esperados"]), None)})
    return agrupar(filas, [f"hit{k}" for k in PROFUNDIDADES]), {"ranking": ranking}


def top_antes(sug: list[dict]) -> list[str]:
    return [s["id_articulo"] for s in sorted(sug, key=lambda s: -float(s.get("confianza") or 0))][:5]


def top_despues(sug: list[dict]) -> list[str]:
    vivas = [s for s in sug if s.get("dictamen") != "veta"]
    orden = sorted(vivas, key=lambda s: -float(s.get("confianza_revisor") if s.get("confianza_revisor") is not None
                                                 else (s.get("confianza") or 0)))
    return [s["id_articulo"] for s in orden][:5]


def medir_cadena(casos: list[dict], salida: list[dict]) -> tuple[dict, dict]:
    por_id = {x["id"]: x for x in salida}
    filas, estados = [], Counter()
    for c in casos:
        r = por_id.get(c["id"])
        if r is None:
            estados["sin_dato"] += 1
            continue
        estados[r["estado"] + (f":{r['motivo_revision']}" if r.get("motivo_revision") else "")] += 1
        sug = r.get("sugerencias") or []
        fila = {"id": c["id"], "ley": c["ley"],
                "evaluador5": hit(r.get("evaluador") or [], c["esperados"], 5),
                "cadena5": hit(top_antes(sug), c["esperados"], 5),
                "revisor5": hit(top_despues(sug), c["esperados"], 5)}
        for k in PROFUNDIDADES:
            fila[f"cand{k}"] = hit(r.get("candidatos") or [], c["esperados"], k)   # sin etapa = fallo
        filas.append(fila)
    campos = [f"cand{k}" for k in PROFUNDIDADES] + ["evaluador5", "cadena5", "revisor5"]
    return agrupar(filas, campos), {"estados": dict(estados), "casos": len(filas)}


def controles(salida: list[dict]) -> dict:
    ctrl = [x for x in salida if x.get("control")]
    con = [x for x in ctrl if x.get("sugerencias")]
    limpios = [x for x in con if all(s.get("dictamen") == "veta" for s in x["sugerencias"])]
    return {"controles": len(ctrl), "con_sugerencias": len(con), "con_todo_vetado": len(limpios)}


def articulos_en_top5_20393(ranking: list[dict]) -> dict:
    """Para los casos de 20.393 que fallan en top-5: qué artículos aparecen (conteo) y cuáles se esperaban."""
    falla = [r for r in ranking if r["ley"] == "20.393" and (r["pos_primer_esperado"] is None or r["pos_primer_esperado"] > 5)]
    return {"casos_fallidos": len(falla),
            "de_20393_total": sum(r["ley"] == "20.393" for r in ranking),
            "top5_aparecen": dict(Counter(a for r in falla for a in r["top5"]).most_common(12)),
            "esperados_perdidos": dict(Counter(a for r in falla for a in r["esperados"]).most_common()),
            "posicion_primer_esperado": dict(Counter(str(r["pos_primer_esperado"]) for r in falla).most_common())}


def _commit() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=AQUI, capture_output=True, text=True).stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", action="append", default=[], metavar="NOMBRE=casos.json",
                    help="salida de correr_revisor.py de ese set (repetible)")
    ap.add_argument("--sets", default=",".join(SETS), help=f"sets a medir, separados por coma ({', '.join(SETS_VALIDOS)})")
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--coleccion", help="colección del retriever solo (por defecto normativa_cl)")
    ap.add_argument("--dedup-literales", action="store_true", help="un literal por artículo partido (colecciones _p/_pe)")
    a = ap.parse_args(argv)
    sets = a.sets.split(",")
    if not set(sets) <= set(SETS_VALIDOS):
        ap.error(f"--sets: {sorted(set(sets) - set(SETS_VALIDOS))} desconocidos")
    OPCIONES.update(coleccion=a.coleccion, dedup=a.dedup_literales)
    cadenas = dict(s.split("=", 1) for s in a.set)
    corpus = rr.articulos_vigentes(a.coleccion)
    res = {"fecha": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "commit": _commit(),
           "corpus_articulos": len(corpus), "coleccion": a.coleccion or rr.embed_sync.COLECCION,
           "dedup_literales": a.dedup_literales, "profundidades": list(PROFUNDIDADES),
           "comando": "medir_base_b2.py " + " ".join(argv if argv is not None else sys.argv[1:]), "sets": {}}
    for nombre in sets:
        casos = casos_set(nombre, corpus)
        ret, extra = medir_retriever(nombre, casos, corpus)
        entrada = {"casos_con_esperados": len(casos), "retriever": ret,
                   "20393": articulos_en_top5_20393(extra["ranking"]), "ranking": extra["ranking"]}
        if nombre in cadenas:
            salida = json.loads(Path(cadenas[nombre]).read_text())
            entrada["cadena"], entrada["cadena_meta"] = medir_cadena(casos, salida)
            entrada["controles"] = controles(salida)
            entrada["cadena_20393_top5"] = dict(Counter(
                s["id_articulo"] for x in salida if x.get("ley") == "20.393" and not x.get("control")
                and not (set(x["esperados"]) & set(top_antes(x.get("sugerencias") or [])))
                for s in sorted(x.get("sugerencias") or [], key=lambda s: -float(s.get("confianza") or 0))[:5]).most_common(12))
        res["sets"][nombre] = entrada
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
    for nombre, e in res["sets"].items():
        print(f"== {nombre} ({e['casos_con_esperados']} casos con esperados)")
        for cfg in ("retriever", "cadena"):
            for ley, m in e.get(cfg, {}).items():
                print(f"  {cfg:9} {ley:14} " + " ".join(
                    f"{k}={v['valor']}[{v['ic95'][0]}-{v['ic95'][1]}](n={v['n']})" for k, v in m.items()))
    print("escrito:", a.salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
