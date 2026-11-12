"""
Medición del revisor jurídico (nucleo/kerna_nucleo/revisor): recall@5 por artículo antes y después, precisión y vetos.

No llama a ningún modelo ni lee denuncias: recibe un JSON con los casos, sus artículos esperados y las sugerencias que
ya salieron del núcleo con KERNA_REVISOR encendido (cada una con su dictamen). Formato (lista de casos, o JSONL):
  {"id": "c1", "esperados": ["1008668-art-3"], "control": false, "ley": "Ley 20393" (opcional),
   "sugerencias": [{"id_articulo": "1008668-art-3", "confianza": 0.9, "dictamen": "veta"|"condiciona"|"confirma"|null,
                    "causal_veto": "...", "condiciones": [...], "confianza_revisor": 0.2, "revision_juridica": "revisado"}]}
`control` = caso sin norma aplicable del corpus (esperados vacío). Una sugerencia sin dictamen cuenta como sin revisión
(se conserva). Definiciones:
  antes   = las sugerencias del generador por confianza, top-k.
  después = las mismas sin las vetadas, ordenadas por confianza_revisor (o confianza), top-k. Anotar antes que eliminar:
            el veto solo se simula aquí; el núcleo conserva el artículo con su dictamen.
Métricas: recall@k por artículo (promedio de casos con esperados, y global), precisión@k, diferencia de recall con
bootstrap pareado (IC 95 %, semilla fija) frente al margen máximo de caída (0,02), vetos correctos/incorrectos (un veto
es correcto si el artículo no era esperado), vetos en controles y casos de control con todo vetado. Reporta además los
condicionados y la cobertura de revisión.

Uso (desde kerna/):
  PYTHONPATH=nucleo:comun python3 evaluacion/medir_revisor.py casos.json [--k 5] [--bootstrap 2000] \
      [--salida evaluacion/registro/revisor-AAAAMMDD.json] [--etiqueta texto]
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SEMILLA = 20261112
CAIDA_MAXIMA = 0.02


def cargar_casos(ruta: Path) -> list[dict]:
    texto = ruta.read_text(encoding="utf-8").strip()
    if not texto:
        return []
    if texto[0] == "[":
        return json.loads(texto)
    if texto[0] == "{" and "\n" not in texto:
        d = json.loads(texto)
        return d["casos"] if isinstance(d.get("casos"), list) else [d]
    return [json.loads(linea) for linea in texto.splitlines() if linea.strip()]


def _conf(s: dict, campo: str = "confianza") -> float:
    try:
        v = s.get(campo)
        return float(s.get("confianza", 0) if v is None else v)
    except (TypeError, ValueError):
        return 0.0


def vetada(s: dict) -> bool:
    return s.get("dictamen") == "veta"


def top_antes(sug: list[dict], k: int) -> list[str]:
    orden = sorted(sug, key=lambda s: -_conf(s, "confianza"))
    return [s["id_articulo"] for s in orden[:k]]


def top_despues(sug: list[dict], k: int) -> list[str]:
    vivas = [s for s in sug if not vetada(s)]
    orden = sorted(vivas, key=lambda s: -_conf(s, "confianza_revisor"))
    return [s["id_articulo"] for s in orden[:k]]


def _recall(top: list[str], esperados: set) -> float:
    return len(esperados & set(top)) / len(esperados)


def _prec(top: list[str], esperados: set) -> float | None:
    return len(esperados & set(top)) / len(top) if top else None


def _media(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def bootstrap_diferencia(dif: list[float], n: int, semilla: int = SEMILLA) -> dict:
    """IC 95 % de la media de las diferencias pareadas por caso (percentiles)."""
    if not dif:
        return {"media": None, "ic95": [None, None]}
    rng = random.Random(semilla)
    medias = sorted(sum(rng.choice(dif) for _ in dif) / len(dif) for _ in range(n))
    return {"media": round(sum(dif) / len(dif), 4),
            "ic95": [round(medias[int(0.025 * (n - 1))], 4), round(medias[int(0.975 * (n - 1))], 4)]}


def medir(casos: list[dict], k: int = 5, n_bootstrap: int = 2000) -> dict:
    con, controles = [], []
    dif, rec_a, rec_d, pre_a, pre_d = [], [], [], [], []
    hit_a = hit_d = total_esp = 0
    vetos = vetos_ok = vetos_mal = condicionadas = revisadas = sugeridas = 0
    vetos_ctrl = ctrl_total_vetado = 0
    por_dictamen = {"confirma": [0, 0], "condiciona": [0, 0], "veta": [0, 0], "sin_revision": [0, 0]}  # [esperadas, total]
    for c in casos:
        sug = [s for s in (c.get("sugerencias") or []) if isinstance(s, dict) and s.get("id_articulo")]
        esp = set(c.get("esperados") or [])
        es_control = bool(c.get("control")) or not esp
        ta, td = top_antes(sug, k), top_despues(sug, k)
        sugeridas += len(sug)
        for s in sug:
            d = s.get("dictamen") if s.get("dictamen") in ("confirma", "condiciona", "veta") else "sin_revision"
            por_dictamen[d][1] += 1
            por_dictamen[d][0] += s["id_articulo"] in esp
            revisadas += d != "sin_revision"
            condicionadas += d == "condiciona"
            if d == "veta":
                vetos += 1
                if es_control:
                    vetos_ctrl += 1
                else:
                    ok = s["id_articulo"] not in esp
                    vetos_ok += ok
                    vetos_mal += not ok
        if es_control:
            controles.append(c)
            ctrl_total_vetado += bool(sug) and all(vetada(s) for s in sug)
            continue
        con.append(c)
        ra, rd = _recall(ta, esp), _recall(td, esp)
        rec_a.append(ra)
        rec_d.append(rd)
        dif.append(rd - ra)
        pre_a.append(_prec(ta, esp))
        pre_d.append(_prec(td, esp))
        hit_a += len(esp & set(ta))
        hit_d += len(esp & set(td))
        total_esp += len(esp)
    ctrl_con_sug = sum(1 for c in controles if c.get("sugerencias"))
    boot = bootstrap_diferencia(dif, n_bootstrap)
    ic_inf = boot["ic95"][0]
    return {
        "k": k, "casos": len(casos), "casos_con_esperados": len(con), "casos_control": len(controles),
        "recall_por_articulo": {"antes": _media(rec_a), "despues": _media(rec_d),
                                "antes_global": round(hit_a / total_esp, 4) if total_esp else None,
                                "despues_global": round(hit_d / total_esp, 4) if total_esp else None,
                                "diferencia": boot, "caida_maxima_permitida": CAIDA_MAXIMA,
                                "no_rompe_recall": (boot["media"] is not None and ic_inf is not None
                                                    and ic_inf >= -CAIDA_MAXIMA)},
        "precision": {"antes": _media(pre_a), "despues": _media(pre_d)},
        "vetos": {"total": vetos, "correctos": vetos_ok, "incorrectos": vetos_mal,
                  "precision_del_veto": round(vetos_ok / (vetos_ok + vetos_mal), 4) if vetos_ok + vetos_mal else None,
                  "en_controles": vetos_ctrl,
                  "controles_con_sugerencias": ctrl_con_sug,
                  "controles_con_todo_vetado": ctrl_total_vetado,
                  "tasa_control_limpio": round(ctrl_total_vetado / ctrl_con_sug, 4) if ctrl_con_sug else None},
        "revision": {"sugerencias": sugeridas, "cobertura": round(revisadas / sugeridas, 4) if sugeridas else None,
                     "condicionadas": condicionadas,
                     "esperadas_por_dictamen": {d: {"esperadas": v[0], "total": v[1],
                                                    "proporcion": round(v[0] / v[1], 4) if v[1] else None}
                                                for d, v in por_dictamen.items()}},
    }


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=AQUI, capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:
        return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("casos", type=Path)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--salida", type=Path, help="guarda el resultado con fecha, commit y parámetros (registro de KPIs)")
    ap.add_argument("--etiqueta", default="", help="texto libre: versión de criterios, modelo, banderas")
    a = ap.parse_args(argv)
    res = medir(cargar_casos(a.casos), a.k, a.bootstrap)
    registro = {"fecha": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "commit": _commit(),
                "parametros": {"k": a.k, "bootstrap": a.bootstrap, "semilla": SEMILLA, "etiqueta": a.etiqueta,
                               "archivo": a.casos.name}, "resultado": res}
    texto = json.dumps(registro, ensure_ascii=False, indent=2)
    if a.salida:
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        a.salida.write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
