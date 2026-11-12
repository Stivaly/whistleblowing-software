"""Genera app/datos/evaluacion.json: instantánea de la evaluación registrada para el informe de gestión.

El App Service no tiene acceso a kerna/evaluacion; este script (que corre desplegar.sh en el host) resume
registro/recall_retriever.jsonl, registro/anonimizador_*.json, registro/pruebas-*.json y precios_embeddings.json.
Solo agregados: nunca texto de denuncias ni identificadores.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
REG = RAIZ / "evaluacion" / "registro"
SALIDA = Path(__file__).parent / "app" / "datos" / "evaluacion.json"


def _config(r: dict) -> str:
    p = r.get("parametros", {})
    if r.get("reranker"):
        return "retriever + reranker abierto"
    if r.get("evaluador"):
        ev = r["evaluador"]
        return f"retriever + evaluador LLM ({ev.get('cadena', '?')}, {ev.get('candidatos', '?')} candidatos)"
    return f"solo retriever ({p.get('modelo', '?')}, campo {p.get('campo_consulta', '?')})"


def generar(reg: Path = REG) -> dict:
    regs = [json.loads(l) for l in (reg / "recall_retriever.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    con_art = [r for r in regs if r.get("metricas_articulo")]
    ult = con_art[-1]
    por_ley = []
    for ley, m in ult["metricas_articulo"].items():
        pl = ult["por_ley"].get(ley, {})
        ic = m.get("recall5_ic95") or [None, None]
        por_ley.append({"ley": "Global" if ley == "global" else ley, "casos": pl.get("casos"), "casos_articulo": m.get("casos_articulo"),
                        "recall_ley": pl.get("recall_ley"), "recall5": m.get("recall5"), "ic95_inf": ic[0], "ic95_sup": ic[1]})
    por_ley.sort(key=lambda x: (x["ley"] != "Global", x["ley"]))
    ev = ult.get("evaluador") or {}
    out = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "recall": {"fecha": ult["fecha"], "commit": ult.get("commit"), "configuracion": _config(ult), "meta": ult["parametros"].get("meta", 0.8),
                   "dataset_casos": ult["dataset"]["casos"], "por_ley": por_ley,
                   "fuente": "kerna/evaluacion/registro/recall_retriever.jsonl"},
        "serie": [{"fecha": r["fecha"][:16].replace("T", " "), "configuracion": _config(r), "recall5": r["metricas_articulo"]["global"]["recall5"]}
                  for r in con_art if r["parametros"].get("campo_consulta") == "texto_original" or r.get("evaluador")],
        "corpus_articulos": ult.get("corpus_articulos_vigentes"),
        "evaluador": {k: ev.get(k) for k in ("cadena", "proveedor", "tokens_por_consulta", "latencia_llamada_ms", "costo_usd", "hit_en_candidatos")} if ev else None,
    }
    anon_f = sorted(reg.glob("anonimizador_*.json"))
    if anon_f:
        a = json.loads(anon_f[-1].read_text(encoding="utf-8"))
        tipos = []
        for t, n in sorted(a.get("casos_con_etiqueta", {}).items()):
            d = a.get("casos_con_deteccion_del_tipo", {}).get(t, 0)
            tipos.append({"tipo": t, "casos_con_dato": n, "casos_detectados": d, "recall_por_caso": round(d / n, 3) if n else None})
        out["anonimizador"] = {"fecha": anon_f[-1].stem.split("_")[-1], "casos": a.get("n_casos"), "tipos": tipos,
                               "apariciones": [{"tipo": t, "total": v["total"], "ocultas": v["ocultas"]} for t, v in a.get("apariciones_independientes", {}).items()],
                               "fuente": f"kerna/evaluacion/registro/{anon_f[-1].name}"}
    pr = sorted(reg.glob("pruebas-*.json"))
    if pr:
        p = json.loads(pr[-1].read_text(encoding="utf-8"))
        out["pruebas"] = {"fecha": p.get("fecha_utc"), "commit": p.get("commit"),
                          "capas": {k: {c: v.get(c) for c in ("total", "pasadas", "fallidas", "omitidas")} for k, v in p.get("capas", {}).items()},
                          "fuente": f"kerna/evaluacion/registro/{pr[-1].name}"}
    precios = RAIZ / "evaluacion" / "precios_embeddings.json"
    if precios.exists():
        out["precios_embeddings"] = {k: v.get("usd_por_millon_tokens") for k, v in json.loads(precios.read_text(encoding="utf-8"))["modelos"].items()}
    return out


if __name__ == "__main__":
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    datos = generar()
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print("escrito", SALIDA, file=sys.stderr)
