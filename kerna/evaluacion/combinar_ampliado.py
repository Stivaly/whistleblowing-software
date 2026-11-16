"""
Recall@5 por artículo (= hit@5) del set de desarrollo ampliado: une, por corrida, los casos de `desarrollo` (42) y
`desarrollo_nuevo` (lote DX, 2026-11-15) a partir de los archivos `casos_cfg2_*` (solo IDs) y reporta, por variante,
cada set por separado y el ampliado: evaluador, cadena y cadena + revisor, con IC 95 % bootstrap, global y por ley;
y la diferencia pareada por caso entre variantes (misma repetición). Un caso sin `completada` cuenta como fallo.

Uso (desde kerna/evaluacion):
  python3 combinar_ampliado.py --corrida base:1=registro/casos_cfg2_vb1_desarrollo_20261115.json,registro/casos_cfg2_dvb1_desarrollo_nuevo_20261115.json \
      --corrida alt3:1=... --salida registro/ampliado_20261115.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import medir_base_b2 as mb  # noqa: E402

CAMPOS = ("evaluador5", "cadena5", "revisor5")


def filas(casos: list[dict], salida: list[dict]) -> dict[str, dict]:
    por_id = {x["id"]: x for x in salida}
    out = {}
    for c in casos:
        r = por_id.get(c["id"]) or {}
        sug = r.get("sugerencias") or []
        out[c["id"]] = {"ley": c["ley"], "evaluador5": mb.hit(r.get("evaluador") or [], c["esperados"], 5),
                        "cadena5": mb.hit(mb.top_antes(sug), c["esperados"], 5),
                        "revisor5": mb.hit(mb.top_despues(sug), c["esperados"], 5)}
    return out


def ic_diferencia(d: list[float], n: int = 2000, semilla: int = 20261115) -> list[float]:
    rnd = random.Random(semilla)
    medias = sorted(sum(rnd.choice(d) for _ in d) / len(d) for _ in range(n))
    return [round(medias[int(0.025 * n)], 4), round(medias[int(0.975 * n) - 1], 4)]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corrida", action="append", required=True, metavar="VARIANTE:REP=casos_42.json,casos_nuevo.json")
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args(argv)
    corpus = set(json.loads((AQUI / "datos" / "corpus_articulos.json").read_text()))
    sets = {"desarrollo": mb.casos_set("desarrollo", corpus), "desarrollo_nuevo": mb.casos_set("desarrollo_nuevo", corpus)}
    corr: dict[str, dict[str, dict]] = defaultdict(dict)   # variante -> rep -> {id: fila}
    for spec in a.corrida:
        clave, _, rutas = spec.partition("=")
        var, _, rep = clave.partition(":")
        r42, rnuevo = rutas.split(",")
        f = {**filas(sets["desarrollo"], json.loads(Path(r42).read_text())),
             **filas(sets["desarrollo_nuevo"], json.loads(Path(rnuevo).read_text()))}
        corr[var][rep] = f
    ids = {"desarrollo": [c["id"] for c in sets["desarrollo"]], "desarrollo_nuevo": [c["id"] for c in sets["desarrollo_nuevo"]]}
    ids["ampliado"] = ids["desarrollo"] + ids["desarrollo_nuevo"]
    res = {"fecha": "2026-11-15", "commit": mb._commit(), "comando": "combinar_ampliado.py " + " ".join(argv or sys.argv[1:]),
           "n": {k: len(v) for k, v in ids.items()}, "variantes": {}, "diferencias": {}}
    for var, reps in corr.items():
        rv = res["variantes"][var] = {}
        for rep, f in sorted(reps.items()):
            rv[rep] = {}
            for s, lista in ids.items():
                por = defaultdict(list)
                for i in lista:
                    por[f[i]["ley"]].append(f[i])
                    por["global"].append(f[i])
                rv[rep][s] = {g: {c: mb.resumen([x[c] for x in fs]) for c in CAMPOS} for g, fs in sorted(por.items())}
        rv["media"] = {s: {c: {"media": round(statistics.mean(rv[r][s]["global"][c]["valor"] for r in reps), 4),
                               "min": min(rv[r][s]["global"][c]["valor"] for r in reps),
                               "max": max(rv[r][s]["global"][c]["valor"] for r in reps)} for c in CAMPOS} for s in ids}
    vs = sorted(corr)
    for i, v1 in enumerate(vs):
        for v2 in vs[i + 1:]:
            comunes = sorted(set(corr[v1]) & set(corr[v2]))
            for c in CAMPOS:
                d = [corr[v2][r][x][c] - corr[v1][r][x][c] for r in comunes for x in ids["ampliado"]]
                if d:
                    res["diferencias"][f"{v2}-{v1}:{c}"] = {"reps": comunes, "n": len(d), "media": round(sum(d) / len(d), 4),
                                                           "ic95": ic_diferencia(d)}
    a.salida.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
    for var in vs:
        for s in ids:
            m = res["variantes"][var]["media"][s]
            print(f"{var:6} {s:17} n={res['n'][s]:3} " + "  ".join(f"{c} {m[c]['media']:.3f} [{m[c]['min']:.3f}-{m[c]['max']:.3f}]" for c in CAMPOS))
    for k, v in res["diferencias"].items():
        print(f"{k}: {v['media']:+.3f} {v['ic95']} (n={v['n']})")


if __name__ == "__main__":
    main()
