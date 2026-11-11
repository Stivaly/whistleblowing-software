"""
Comparación de los candidatos de embeddings a partir de lo registrado por recall_retriever.py.

Lee registro/recall_retriever.jsonl, toma la última corrida de cada candidato de candidatos.json (mismo
campo de consulta y mismo dataset), calcula la diferencia de recall@5 por artículo entre cada par con IC
bootstrap pareado de 95 % (mismos casos y remuestreos) y aplica la regla de decisión:

  - si la diferencia de recall@5 es < 0,05 o los intervalos se superponen, desempata nDCG@10, luego el P95 de la
    vectorización de la consulta (menor), luego el costo (menor);
  - meta: recall@5 >= 0,80 por ARTÍCULO (por ley es un dato secundario).

Decisión de nube: el mejor de todos los candidatos; si es abierto, se usa en ambos modos. Decisión de local: el mejor
de los abiertos, aunque gane uno de nube. Escribe informe-embeddings.md.

Uso (desde kerna/):  python3 evaluacion/comparar_embeddings.py [--campo texto_original]
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from recall_retriever import REGISTRO, bootstrap_pareado, META, REMUESTREOS, SEMILLA  # noqa: E402

CANDIDATOS = AQUI / "candidatos.json"
INFORME = AQUI / "informe-embeddings.md"
UMBRAL_DIFERENCIA = 0.05


def cargar_registro(ruta: Path = REGISTRO) -> list[dict]:
    if not ruta.exists():
        return []
    return [json.loads(l) for l in ruta.read_text().splitlines() if l.strip()]


def ultima_corrida(entradas: list[dict], cand: dict, campo: str, dataset: str | None = None,
                   mapeo: str = "concordancia") -> dict | None:
    """Última entrada del registro para el candidato (colección + modelo + modelo de consulta) con el mapeo de
    candidatos dado; las corridas anteriores a `--mapeo` cuentan como "directo"."""
    coincide = [e for e in entradas
                if e["parametros"].get("campo_consulta") == campo
                and e["parametros"].get("mapeo", "directo") == mapeo
                and e["parametros"].get("coleccion") == cand["coleccion"]
                and e["parametros"].get("modelo") == cand["modelo"]
                and e["parametros"].get("modelo_consulta", cand["modelo"]) == cand["modelo_consulta"]
                and (dataset is None or e["dataset"]["sha256"] == dataset)]
    return max(coincide, key=lambda e: e["fecha"], default=None)


def con_tokens_medidos(entradas: list[dict], cand: dict, campo: str, e: dict) -> dict:
    """Las corridas que releen los vectores de consulta guardados no consumen la API y estiman los tokens
    (caracteres / 3). Si una corrida anterior del mismo candidato, campo y dataset los midió, se usan esos."""
    if (e.get("tokens_consultas") or {}).get("origen") == "medido":
        return e
    medidas = [x for x in entradas
               if x["parametros"].get("campo_consulta") == campo and x["parametros"].get("coleccion") == cand["coleccion"]
               and x["parametros"].get("modelo") == cand["modelo"]
               and x["parametros"].get("modelo_consulta", cand["modelo"]) == cand["modelo_consulta"]
               and x["dataset"]["sha256"] == e["dataset"]["sha256"]
               and (x.get("tokens_consultas") or {}).get("origen") == "medido"]
    if not medidas:
        return e
    m = max(medidas, key=lambda x: x["fecha"])
    return {**e, "tokens_consultas": m["tokens_consultas"], "costo_estimado": m.get("costo_estimado")}


def resumen(cand: dict, e: dict) -> dict:
    g = e.get("metricas_articulo", {}).get("global", {})
    detalle = {d["id"]: d["metricas"]["recall5"] for d in e["detalle"] if d.get("metricas")}
    costo = (e.get("costo_estimado") or {}).get("usd")
    return {"id": cand["id"], "etiqueta": cand["etiqueta"], "tipo": cand["tipo"], "fecha": e["fecha"],
            "commit": e["commit"], "recall5": g.get("recall5"), "ic95": g.get("recall5_ic95"),
            "ndcg10": g.get("ndcg10"), "mrr": g.get("mrr"), "p5": g.get("p5"), "hit5": g.get("hit5"),
            "casos_articulo": g.get("casos_articulo"), "recall_ley": e["por_ley"]["global"]["recall_ley"],
            "p95_ms": (e.get("latencia_consulta") or {}).get("p95_ms"),
            "tokens": (e.get("tokens_consultas") or {}).get("total"), "costo_usd": costo,
            "hit8": g.get("hit8"), "hit10": g.get("hit10"), "cobertura5": g.get("cobertura5"),
            "cobertura8": g.get("cobertura8"), "cobertura10": g.get("cobertura10"),
            "por_ley": e["por_ley"], "metricas_ley": e.get("metricas_articulo", {}), "por_caso": detalle}


TRAMOS_PUNTAJE = [(5, f"≥ {META:.2f}"), (4, f"≥ {META * 0.75:.2f}"), (3, f"≥ {META * 0.5:.2f}"),
                  (2, f"≥ {META * 0.25:.2f}"), (1, f"< {META * 0.25:.2f}")]


def puntaje_calidad(recall5: float) -> int:
    """Recall@5 por artículo convertido a la escala de 1 a 5: tramos iguales hasta la meta."""
    for puntos, fraccion in ((5, 1.0), (4, 0.75), (3, 0.5), (2, 0.25)):
        if recall5 >= META * fraccion - 1e-9:
            return puntos
    return 1


def solapan(a: list[float], b: list[float]) -> bool:
    return not (a[1] < b[0] or b[1] < a[0])


def mejor(a: dict, b: dict) -> tuple[dict, str]:
    """El mejor de dos candidatos según la regla de decisión y el criterio que decidió."""
    dif = a["recall5"] - b["recall5"]
    if abs(dif) >= UMBRAL_DIFERENCIA and not solapan(a["ic95"], b["ic95"]):
        return (a if dif > 0 else b), "recall@5"
    for clave, mayor, nombre in (("ndcg10", True, "nDCG@10"), ("p95_ms", False, "P95"),
                                 ("costo_usd", False, "costo")):
        x, y = a[clave], b[clave]
        if x is None or y is None or abs(x - y) < 1e-12:
            continue
        return (a if (x > y) == mayor else b), f"{nombre} (recall@5 sin diferencia decisiva)"
    return a, "empate total (se conserva el primero)"


def elegir(medidos: list[dict]) -> tuple[dict | None, list[str]]:
    """Torneo secuencial con `mejor`. -> (ganador, criterios aplicados)."""
    if not medidos:
        return None, []
    ganador, criterios = medidos[0], []
    for c in medidos[1:]:
        nuevo, criterio = mejor(c, ganador)
        criterios.append(f"{c['id']} vs {ganador['id']}: gana {nuevo['id']} por {criterio}")
        ganador = nuevo
    return ganador, criterios


def decidir(medidos: list[dict]) -> dict:
    ganador, criterios = elegir(medidos)
    abiertos = [m for m in medidos if m["tipo"] == "abierto"]
    local, crit_local = elegir(abiertos)
    nube = ganador if ganador and ganador["tipo"] == "nube" else ganador   # si gana un abierto, vale para ambos
    return {"ganador": ganador, "criterios": criterios, "nube": nube, "local": local,
            "criterios_local": crit_local, "un_solo_indice": bool(ganador and ganador["tipo"] == "abierto")}


def pares(medidos: list[dict]) -> list[dict]:
    out = []
    for a, b in itertools.combinations(medidos, 2):
        ids = sorted(set(a["por_caso"]) & set(b["por_caso"]))
        r = bootstrap_pareado([a["por_caso"][i] for i in ids], [b["por_caso"][i] for i in ids])
        if r:
            out.append({"a": a["id"], "b": b["id"], "casos": len(ids), **r,
                        "significativa": not (r["ic95"][0] <= 0 <= r["ic95"][1])})
    return out


def _f(x, d=3):
    return "—" if x is None else f"{x:.{d}f}"


def generar_informe(entradas: list[dict], candidatos: list[dict], campo: str, mapeo: str = "concordancia") -> str:
    # Dataset de referencia: el más usado entre las últimas corridas.
    ultimas = {c["id"]: ultima_corrida(entradas, c, campo, mapeo=mapeo) for c in candidatos}
    shas = Counter(e["dataset"]["sha256"] for e in ultimas.values() if e)
    dataset = shas.most_common(1)[0][0] if shas else None
    medidos, no_medidos = [], []
    for c in candidatos:
        if c.get("solo_si_falta") and ultimas.get(c["solo_si_falta"]):
            no_medidos.append((c, "no hacía falta: el 8B se midió"))
            continue
        e = ultima_corrida(entradas, c, campo, dataset, mapeo)
        if e and e.get("metricas_articulo", {}).get("global"):
            medidos.append(resumen(c, con_tokens_medidos(entradas, c, campo, e)))
        elif ultimas.get(c["id"]):
            no_medidos.append((c, "su última corrida es de otro dataset o no trae métricas por artículo"))
        else:
            no_medidos.append((c, c.get("motivo_no_medido") or "sin corrida registrada para este campo"))
    d = decidir(medidos)
    L = ["# Informe de la prueba comparativa de embeddings", "",
         "Generado por `comparar_embeddings.py` a partir de `registro/recall_retriever.jsonl`. Sin textos de denuncias.", "",
         "## Método", "",
         f"- Dataset: `datos/denuncias_publicas.json`, sha256 `{(dataset or '—')[:16]}…`; consulta = `{campo}`.",
         "- Mismo corpus (fragmentos sustantivos vigentes de la BCN) y mismo texto por fragmento (`texto_embedding`) en cada "
         "colección; coseno; filtro `vigente=true`; top 5 (nDCG@10 y MRR sobre el top 10); 1024 dimensiones salvo "
         "EmbeddingGemma (768) y `voyage-law-2` (1024 fijas).",
         "- Métrica principal: recall@5 por **artículo** (algún artículo candidato en el top 5; se evalúan solo los casos con "
         f"candidatos mapeables al corpus). Meta {META:.2f} por artículo; por ley es dato secundario. IC de 95 % por "
         f"bootstrap de casos ({REMUESTREOS} remuestreos, semilla {SEMILLA}). Los candidatos del dataset son alternativas "
         "aceptables, así que recall@5 y hit rate@5 coinciden. Mapeo de candidatos: "
         + ("`concordancia` (los artículos de la Ley 19.628 citados con la numeración previa a la Ley 21.719 se traducen "
            "al texto reformado que trae el corpus vigente)." if mapeo == "concordancia"
            else "`directo` (número citado tal cual; definición anterior).") + " Ver `analisis-recall-articulo.md`.",
         "- Pares: diferencia de recall@5 con IC bootstrap pareado (mismos casos y remuestreos).",
         f"- Regla: si la diferencia de recall@5 es < {UMBRAL_DIFERENCIA} o los intervalos se superponen, desempata "
         "nDCG@10, luego P95 de la consulta y luego costo.",
         "- Modelos abiertos: calculados dentro de Azure (job `job-kerna-eval-embeddings`, CPU); sus P95 son de CPU de 4 vCPU "
         "y su costo es de cómputo, no por token. Los de API miden la latencia de una consulta por petición desde el "
         "servidor de desarrollo, cuyas esperas de DNS (múltiplos de 5 s) la inflan: el P95 de Azure OpenAI (mínimo "
         "0,8 s, mediana 5,8 s) no es comparable con el de Voyage; repetirlo desde Azure antes de usarlo para decidir.", ""]
    L += ["## Resultados por candidato (nivel artículo)", "",
          "| Candidato | Tipo | Casos | recall@5 [IC 95 %] | nDCG@10 | MRR | P@5 | recall ley | P95 consulta (ms) | Tokens | Costo (USD) | ¿Meta? |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in medidos:
        ic = f"[{_f(m['ic95'][0])}, {_f(m['ic95'][1])}]" if m["ic95"] else "—"
        L.append(f"| {m['etiqueta']} | {m['tipo']} | {m['casos_articulo']} | {_f(m['recall5'])} {ic} | {_f(m['ndcg10'])} | "
                 f"{_f(m['mrr'])} | {_f(m['p5'])} | {_f(m['recall_ley'])} | {_f(m['p95_ms'], 0)} | {m['tokens'] or '—'} | "
                 f"{_f(m['costo_usd'], 4)} | {'sí' if m['recall5'] is not None and m['recall5'] >= META else 'no'} |")
    L += ["", "### Por ley", "", "| Candidato | Ley | Casos art. | recall@5 artículo | nDCG@10 | recall@5 ley |", "|---|---|---|---|---|---|"]
    for m in medidos:
        for ley in sorted(k for k in m["por_ley"] if k != "global"):
            ml = m["metricas_ley"].get(ley, {})
            L.append(f"| {m['etiqueta']} | {ley} | {m['por_ley'][ley]['casos_articulo']} | {_f(ml.get('recall5'))} | "
                     f"{_f(ml.get('ndcg10'))} | {_f(m['por_ley'][ley]['recall_ley'])} |")
    L += ["", "### Más allá del top 5", "",
          "hit = algún candidato en el top k (la métrica principal con k = 5); cobertura = fracción de los candidatos "
          "que aparece (recall verdadero). El núcleo entrega 8 fragmentos al modelo.", "",
          "| Candidato | hit@5 | hit@8 | hit@10 | cobertura@5 | cobertura@8 | cobertura@10 |", "|---|---|---|---|---|---|---|"]
    for m in medidos:
        L.append(f"| {m['etiqueta']} | {_f(m['recall5'])} | {_f(m['hit8'])} | {_f(m['hit10'])} | {_f(m['cobertura5'])} | "
                 f"{_f(m['cobertura8'])} | {_f(m['cobertura10'])} |")
    if mapeo != "directo":
        L += ["", "### Efecto de la corrección del mapeo de candidatos (recall@5 por artículo)", "",
              "| Candidato | Antes (`directo`) | Casos | Después (`" + mapeo + "`) | Casos |", "|---|---|---|---|---|"]
        for m in medidos:
            c = next(x for x in candidatos if x["id"] == m["id"])
            antes = ultima_corrida(entradas, c, campo, dataset, "directo")
            ga = (antes or {}).get("metricas_articulo", {}).get("global", {})
            L.append(f"| {m['etiqueta']} | {_f(ga.get('recall5'))} | {ga.get('casos_articulo', '—')} | "
                     f"{_f(m['recall5'])} | {m['casos_articulo']} |")
    L += ["", "## Comparación por pares (recall@5 por artículo)", ""]
    ps = pares(medidos)
    if ps:
        L += ["| A | B | Casos | A − B | IC 95 % pareado | ¿Diferencia significativa? |", "|---|---|---|---|---|---|"]
        L += [f"| {p['a']} | {p['b']} | {p['casos']} | {p['diferencia']:+.3f} | [{p['ic95'][0]:+.3f}, {p['ic95'][1]:+.3f}] | "
              f"{'sí' if p['significativa'] else 'no'} |" for p in ps]
    else:
        L.append("Se necesitan al menos dos candidatos medidos.")
    L += ["", "## Decisión", ""]
    if not d["ganador"]:
        L.append("Sin candidatos medidos: no hay decisión.")
    else:
        g = d["ganador"]
        L.append(f"- **Nube**: {d['nube']['etiqueta']} (recall@5 {_f(g['recall5'])}"
                 + ("; es un modelo abierto, se usa en ambos modos y queda un solo índice" if d["un_solo_indice"] else "") + ").")
        if d["local"]:
            L.append(f"- **Local** (el mejor de los abiertos, aunque gane uno de nube): {d['local']['etiqueta']} "
                     f"(recall@5 {_f(d['local']['recall5'])}).")
        else:
            L.append("- **Local**: ningún abierto medido todavía.")
        if g["recall5"] < META:
            L.append(f"- Ningún candidato llega a la meta de {META:.2f} por artículo (el mejor: {_f(g['recall5'])}): "
                     "revisar primero el texto que se vectoriza por fragmento (causa raíz y propuesta: `analisis-recall-articulo.md`).")
        L += ["", "Criterios aplicados:"] + [f"- {c}" for c in d["criterios"]]
        if d["criterios_local"]:
            L += ["", "Entre los abiertos:"] + [f"- {c}" for c in d["criterios_local"]]
    L += ["", "## Candidatos no medidos", ""]
    L += [f"- {c['etiqueta']}: {why}." for c, why in no_medidos] or ["Todos medidos."]
    L += ["", "## Calidad de recuperación medida, en escala de 1 a 5", "",
          f"Regla: el recall@5 por artículo se divide en cinco tramos iguales hasta la meta de {META:.2f} "
          "(" + "; ".join(f"{n}: {t}" for n, t in TRAMOS_PUNTAJE) + "). Reemplaza al puntaje de calidad basado en cifras del "
          "proveedor al recalcular el análisis ponderado del modelo de embeddings.", "",
          "| Candidato | recall@5 artículo | Puntaje |", "|---|---|---|"]
    L += [f"| {m['etiqueta']} | {_f(m['recall5'])} | {puntaje_calidad(m['recall5'])} |" for m in medidos]
    L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--campo", default="texto_original", choices=["texto_original", "resumen_parafraseado"])
    ap.add_argument("--mapeo", default="concordancia", choices=["concordancia", "directo"])
    ap.add_argument("--registro", default=str(REGISTRO))
    ap.add_argument("--salida", default=str(INFORME))
    args = ap.parse_args(argv)
    candidatos = json.loads(CANDIDATOS.read_text())["candidatos"]
    texto = generar_informe(cargar_registro(Path(args.registro)), candidatos, args.campo, args.mapeo)
    Path(args.salida).write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
