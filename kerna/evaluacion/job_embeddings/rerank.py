"""
Job de Azure: reordena con un cross-encoder abierto (BAAI/bge-reranker-v2-m3, CPU) los candidatos de cada consulta.

Entrada: datos/rerank_candidatos.json (lo escribe `medir_rerank.py --accion preparar`):
  {"reranker", "base", "casos": [{"id", "consulta", "ids": [fragmento_id...], "docs": [texto...]}]}
Salida: colección `normativa_cl_eval_rerank_<reranker>_<base>` en Qdrant, un punto por caso (vector de relleno)
con payload {caso_id, orden: [[indice, puntaje]...], ms}. `ms` es el tiempo de puntuar los candidatos de una consulta.
Lo invoca evaluar.py cuando MODELOS es `bge-reranker-v2-m3`.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

AQUI = Path(__file__).resolve().parent
MODELOS = {"bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3"}
SALIDA_TOP = 10


def punto_id(caso_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"rerank|{caso_id}"))


def ejecutar(nombre: str, qdrant, asegurar_coleccion, subir, log) -> dict:
    from sentence_transformers import CrossEncoder
    datos = json.loads((AQUI / "datos" / "rerank_candidatos.json").read_text(encoding="utf-8"))
    coleccion = f"normativa_cl_eval_rerank_{nombre}_{datos['base']}"
    t0 = time.monotonic()
    modelo = CrossEncoder(MODELOS[nombre], max_length=512, device="cpu")
    log(evento="modelo_listo", modelo=nombre, descarga_s=round(time.monotonic() - t0, 1))
    modelo.predict([["calentamiento", "calentamiento"]])
    puntos, ms = [], []
    for caso in datos["casos"]:
        t = time.perf_counter()
        pun = modelo.predict([[caso["consulta"], d] for d in caso["docs"]], batch_size=8)
        dt = (time.perf_counter() - t) * 1000
        ms.append(dt)
        orden = sorted(enumerate(float(x) for x in pun), key=lambda p: -p[1])[:SALIDA_TOP]
        puntos.append({"id": punto_id(caso["id"]), "vector": [1.0],
                       "payload": {"caso_id": caso["id"], "orden": [[i, s] for i, s in orden], "ms": round(dt, 1)}})
    asegurar_coleccion(coleccion, 1, indices=False)
    subir(coleccion, puntos)
    ms.sort()
    return {"modelo": nombre, "estado": "ok", "coleccion": coleccion, "casos": len(puntos),
            "mediana_ms": round(ms[len(ms) // 2], 1), "p95_ms": round(ms[max(0, -(-95 * len(ms) // 100) - 1)], 1),
            "segundos": round(time.monotonic() - t0, 1)}
