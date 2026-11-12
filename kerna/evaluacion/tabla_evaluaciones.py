"""Escribe cada resultado de medición en la tabla `evaluaciones` de Azure Table Storage (cuenta de datos de Kerna).

Una fila por (corrida, métrica, ámbito): PartitionKey = fuente (recall_retriever, anonimizador, pruebas,
comparacion_embeddings, embeddings_job), RowKey = fecha~commit~métrica~ámbito (idempotente: reescribir una corrida
no duplica filas), más fecha, commit, metrica, ambito, valor, parametros (JSON) y detalle (JSON).
Solo agregados: nunca texto de denuncias ni identificadores. Es de mejor esfuerzo: si no hay URL de la cuenta o
falla la escritura avisa por stderr y no interrumpe la medición (el JSONL sigue siendo la fuente local).

Cuenta: variable KERNA_TABLAS_URL o `terraform output nucleo_tablas_url` (infra/terraform). Identidad: la sesión de
`az login` (rol Storage Table Data Contributor; la cuenta no admite claves).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

TABLA = "evaluaciones"
RAIZ = Path(__file__).resolve().parents[2]
_INVALIDO = re.compile(r"[\\/#?\x00-\x1f\x7f-\x9f]")


def _clave(*partes) -> str:
    return _INVALIDO.sub("-", "~".join(str(p) for p in partes))


def fila(fuente: str, fecha: str, commit: str, metrica: str, valor, ambito: str = "global",
         parametros: dict | None = None, detalle: dict | None = None) -> dict:
    return {"PartitionKey": fuente, "RowKey": _clave(fecha, commit, metrica, ambito), "fecha": fecha,
            "commit": commit or "desconocido", "metrica": metrica, "ambito": ambito,
            "valor": None if valor is None else float(valor),
            "parametros": json.dumps(parametros or {}, ensure_ascii=False, default=str),
            "detalle": json.dumps(detalle or {}, ensure_ascii=False, default=str)}


def _config(r: dict) -> str:
    p = r.get("parametros", {})
    if r.get("reranker"):
        return "retriever + reranker abierto"
    if r.get("evaluador"):
        ev = r["evaluador"]
        return f"retriever + evaluador LLM ({ev.get('cadena', '?')}, {ev.get('candidatos', '?')} candidatos)"
    return f"solo retriever ({p.get('modelo', '?')}, campo {p.get('campo_consulta', '?')})"


def filas_recall(r: dict) -> list[dict]:
    """Filas de una entrada de recall_retriever.jsonl (también medir_evaluador y medir_rerank)."""
    ma = r.get("metricas_articulo") or {}
    base = {**(r.get("parametros") or {}), "configuracion": _config(r), "dataset_casos": (r.get("dataset") or {}).get("casos"),
            "corpus_articulos": r.get("corpus_articulos_vigentes")}
    out = []
    for ambito, m in ma.items():
        pl = (r.get("por_ley") or {}).get(ambito, {})
        ic = m.get("recall5_ic95") or [None, None]
        par = dict(base)
        if ambito == "global":
            ev = r.get("evaluador")
            if ev:
                par["evaluador_resumen"] = {k: ev.get(k) for k in ("cadena", "proveedor", "tokens_por_consulta", "latencia_llamada_ms",
                                                           "costo_usd", "hit_en_candidatos")}
        out.append(fila("recall_retriever", r["fecha"], r.get("commit"), "recall5", m.get("recall5"), ambito, par,
                        {"casos": pl.get("casos"), "casos_articulo": m.get("casos_articulo"), "recall_ley": pl.get("recall_ley"),
                         "ic95_inf": ic[0], "ic95_sup": ic[1]}))
        for k in ("hit8", "ndcg10", "mrr", "p5"):
            if m.get(k) is not None:
                out.append(fila("recall_retriever", r["fecha"], r.get("commit"), k, m[k], ambito, base))
    return out


def filas_anonimizador(a: dict, fecha: str, commit: str) -> list[dict]:
    par = {"casos": a.get("n_casos")}
    out = []
    for t, n in sorted((a.get("casos_con_etiqueta") or {}).items()):
        d = (a.get("casos_con_deteccion_del_tipo") or {}).get(t, 0)
        out.append(fila("anonimizador", fecha, commit, "recall_por_caso", round(d / n, 6) if n else None, t, par,
                        {"casos_con_dato": n, "casos_detectados": d}))
    for t, v in (a.get("apariciones_independientes") or {}).items():
        out.append(fila("anonimizador", fecha, commit, "ocultas", v["ocultas"] / v["total"] if v.get("total") else None, t, par,
                        {"total": v.get("total"), "ocultas": v.get("ocultas")}))
    return out


def filas_pruebas(p: dict) -> list[dict]:
    out = []
    for capa, c in (p.get("capas") or {}).items():
        out.append(fila("pruebas", p.get("fecha_utc", ""), p.get("commit"), "pruebas_pasadas", c.get("pasadas"), capa,
                        {"ok": p.get("ok")}, {k: c.get(k) for k in ("total", "pasadas", "fallidas", "omitidas")}))
    return out


def filas_embeddings_job(resultado: dict, fecha: str, commit: str = "job") -> list[dict]:
    """Un resultado de modelo del job de Azure (evaluar.py, evento resultado_modelo)."""
    modelo = str(resultado.get("modelo", "?"))
    out = []
    for k in ("p95_consulta_ms", "segundos", "tokens_fragmentos", "tokens_consultas"):
        if isinstance(resultado.get(k), (int, float)):
            out.append(fila("embeddings_job", fecha, commit, k, resultado[k], modelo, {"estado": resultado.get("estado")}))
    if not out:
        out.append(fila("embeddings_job", fecha, commit, "estado", None, modelo, {"estado": resultado.get("estado")}))
    return out


def filas_comparacion(medidos: list[dict], fecha: str, commit: str, campo: str, mapeo: str) -> list[dict]:
    par = {"campo_consulta": campo, "mapeo": mapeo}
    return [fila("comparacion_embeddings", fecha, commit, "recall5", m.get("recall5"), str(m["id"]), par,
                 {"etiqueta": m.get("etiqueta"), "ndcg10": m.get("ndcg10"), "mrr": m.get("mrr"), "p95_ms": m.get("p95_ms"),
                  "ic95": m.get("ic95")}) for m in medidos]


def filas_precios(precios: dict, fecha: str) -> list[dict]:
    """precios_embeddings.json: USD por millón de tokens de cada modelo de embeddings (None = sin precio verificado)."""
    return [fila("precios_embeddings", fecha, "precios", "usd_por_millon_tokens", v.get("usd_por_millon_tokens"), str(m))
            for m, v in (precios.get("modelos") or {}).items()]


def url_cuenta() -> str | None:
    url = os.environ.get("KERNA_TABLAS_URL")
    if url:
        return url
    try:
        r = subprocess.run(["terraform", f"-chdir={RAIZ / 'infra' / 'terraform'}", "output", "-raw", "nucleo_tablas_url"],
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.startswith("https://") else None
    except (OSError, subprocess.SubprocessError):
        return None


def cliente_tabla(url: str | None = None):
    from azure.data.tables import TableServiceClient
    from azure.identity import DefaultAzureCredential
    servicio = TableServiceClient(endpoint=url or url_cuenta(), credential=DefaultAzureCredential())
    return servicio.create_table_if_not_exists(TABLA)


def subir(filas: list[dict], tabla=None) -> int:
    """Upsert de las filas. Devuelve cuántas se escribieron (0 si no hay cuenta o falla: nunca lanza)."""
    if not filas:
        return 0
    try:
        if tabla is None:
            if not url_cuenta():
                print("evaluaciones: sin KERNA_TABLAS_URL ni terraform output; solo se guardó el registro local", file=sys.stderr)
                return 0
            tabla = cliente_tabla()
        n = 0
        for f in filas:
            tabla.upsert_entity({k: v for k, v in f.items() if v is not None}, mode="replace")
            n += 1
        return n
    except Exception as exc:  # noqa: BLE001  (la medición no depende de Azure)
        print(f"evaluaciones: no se escribió en la tabla ({type(exc).__name__})", file=sys.stderr)
        return 0


def backfill(registro: Path, tabla=None) -> int:
    """Sube los registros históricos de kerna/evaluacion/registro (idempotente)."""
    filas: list[dict] = []
    jl = registro / "recall_retriever.jsonl"
    if jl.exists():
        for linea in jl.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                filas += filas_recall(json.loads(linea))
    for f in sorted(registro.glob("anonimizador_*.json")):
        fecha = f.stem.split("_")[-1]
        filas += filas_anonimizador(json.loads(f.read_text(encoding="utf-8")), fecha, "historico")
    for f in sorted(registro.glob("pruebas-*.json")):
        filas += filas_pruebas(json.loads(f.read_text(encoding="utf-8")))
    precios = registro.parent / "precios_embeddings.json"
    if precios.exists():
        filas += filas_precios(json.loads(precios.read_text(encoding="utf-8")), "2026-01-01")
    return subir(filas, tabla)


if __name__ == "__main__":
    print("filas escritas:", backfill(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "registro"))
