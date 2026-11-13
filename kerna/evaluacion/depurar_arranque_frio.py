"""Marca arranques en frío del servidor que duerme (App Service F1, ~20 min sin uso) en mediciones de latencia.

Regla: se excluye un pedido solo si (a) es el primero de la corrida o viene tras >= 20 min sin pedidos Y
(b) su tiempo es atípico: > 3 x mediana del resto o > Q3 + 3 x IQR. Sin marcas de hora no se excluye nada.
Entrada de `depurar`: lista de {"id", "t" (ISO UTC o None), "ms"}. No modifica los datos originales.

  python3 depurar_arranque_frio.py   # escribe registro/latencia_sin_arranque_frio.json
"""
import json
import pathlib
import statistics
from datetime import datetime

AQUI = pathlib.Path(__file__).resolve().parent
UMBRAL_S = 20 * 60


def pct(v, p):
    s = sorted(v)
    if not s:
        return None
    k = (len(s) - 1) * p / 100
    i = int(k)
    return s[i] + (s[min(i + 1, len(s) - 1)] - s[i]) * (k - i)


def _t(x):
    return datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()


def resumen(ms):
    return {"p50": pct(ms, 50), "p95": pct(ms, 95)}


def depurar(pedidos):
    pedidos = list(pedidos)
    ms = [p["ms"] for p in pedidos]
    out = {"n_total": len(pedidos), "n_excluidos": 0, "excluidos": [], "con_exclusion": resumen(ms), "sin_exclusion": resumen(ms)}
    if not pedidos or any(not p.get("t") for p in pedidos):
        out["estado"] = "sin datos para depurar; repetir con calentamiento"
        return out
    orden = sorted(pedidos, key=lambda p: _t(p["t"]))
    excl = []
    for i, p in enumerate(orden):
        brecha = None if i == 0 else _t(p["t"]) - _t(orden[i - 1]["t"])
        if i > 0 and brecha < UMBRAL_S:
            continue
        resto = [q["ms"] for q in orden if q is not p]
        if len(resto) < 3:
            continue
        q1, q3 = pct(resto, 25), pct(resto, 75)
        if p["ms"] > 3 * statistics.median(resto) or p["ms"] > q3 + 3 * (q3 - q1):
            excl.append({"id": p["id"], "t": p["t"], "ms": p["ms"],
                         "motivo": "primero de la corrida" if i == 0 else f"{brecha / 60:.0f} min sin pedidos"})
    ids = {e["id"] for e in excl}
    out.update(estado="depurado", n_excluidos=len(excl), excluidos=excl,
               con_exclusion=resumen([p["ms"] for p in orden if p["id"] not in ids]))
    return out


def desde_capturas():
    res = {}
    for f in sorted((AQUI.parent / "front/diseno-v2/capturas").glob("prod*.json")):
        d = json.loads(f.read_text())
        ped = [{"id": k, "t": None, "ms": v["ttfb"]} for k, v in d.items() if "ttfb" in v]
        r = depurar(ped)
        r["servidor"] = "App Service F1 del front (duerme)"
        r["nota"] = "TTFB, un valor por vista y ancho; sin marca de hora por pedido; el archivo no registra orden de visita real"
        res[f"kerna/front/diseno-v2/capturas/{f.name}"] = r
    return res


if __name__ == "__main__":
    salida = {"regla": "primero tras >= 20 min sin pedidos (o primero de la corrida) Y > 3 x mediana del resto o > Q3 + 3 x IQR",
              "unidad": "ms", "mediciones": desde_capturas()}
    (AQUI / "registro/latencia_sin_arranque_frio.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1))
    for k, v in salida["mediciones"].items():
        print(k, v["estado"], v["n_total"], v["sin_exclusion"])
