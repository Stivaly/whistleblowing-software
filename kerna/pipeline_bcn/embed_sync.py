"""
Sincronizador de embeddings: Mongo (fragmentos pendientes) -> Qdrant Cloud.

Toma cada fragmento con estado_embedding="pendiente", genera el embedding del
campo `texto_embedding` (proveedor configurable) y hace upsert en Qdrant con
payload de metadatos para filtrado. Idempotente: el ID del punto es estable
(hash del _id del fragmento), y si un artículo no cambió su hash_texto,
extraer_bcn.py no lo vuelve a marcar pendiente.

Uso:
  python3 embed_sync.py [--batch 64] [--proveedor gemini|voyage|openai]

Variables de entorno:
  MONGODB_URI, QDRANT_URL, QDRANT_API_KEY
  GEMINI_API_KEY   (proveedor gemini, por defecto: gemini-embedding-2, multilingüe)
  VOYAGE_API_KEY   (proveedor voyage: modelo voyage-3.5, multilingüe)
  OPENAI_API_KEY   (proveedor openai: text-embedding-3-large, dims=1024)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

COLECCION = "normativa_cl"
DIMS = 1024


def _post(url: str, headers: dict, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def embed_gemini(textos: list[str]) -> list[list[float]]:
    # gemini-embedding-2 no usa task_type: la tarea va en el texto. Formato de documento
    # para búsqueda; el título va en "none" porque texto_embedding ya trae la norma.
    # Con menos de 3072 dimensiones el modelo devuelve los vectores ya normalizados.
    modelo = "models/gemini-embedding-2"
    out = _post(f"https://generativelanguage.googleapis.com/v1beta/{modelo}:batchEmbedContents",
                {"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                {"requests": [{"model": modelo,
                               "content": {"parts": [{"text": f"title: none | text: {t}"}]},
                               "outputDimensionality": DIMS} for t in textos]})
    return [e["values"] for e in out["embeddings"]]


def embed_voyage(textos: list[str]) -> list[list[float]]:
    out = _post("https://api.voyageai.com/v1/embeddings",
                {"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
                {"model": "voyage-3.5", "input": textos,
                 "input_type": "document", "output_dimension": DIMS})
    return [d["embedding"] for d in out["data"]]


def embed_openai(textos: list[str]) -> list[list[float]]:
    out = _post("https://api.openai.com/v1/embeddings",
                {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                {"model": "text-embedding-3-large", "input": textos, "dimensions": DIMS})
    return [d["embedding"] for d in out["data"]]


PROVEEDORES = {"gemini": embed_gemini, "voyage": embed_voyage, "openai": embed_openai}


def qdrant(path: str, body: dict | None = None, method: str = "PUT") -> dict:
    url = os.environ["QDRANT_URL"].rstrip("/") + path
    headers = {"api-key": os.environ["QDRANT_API_KEY"],
               "Content-Type": "application/json"}
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def asegurar_coleccion():
    try:
        qdrant(f"/collections/{COLECCION}", method="GET")
    except Exception:
        qdrant(f"/collections/{COLECCION}", {
            "vectors": {"size": DIMS, "distance": "Cosine"},
            "on_disk_payload": True,
        })
        for campo, tipo in [("categorias", "keyword"), ("id_norma", "integer"),
                            ("vigente", "bool"), ("clave_corpus", "keyword")]:
            qdrant(f"/collections/{COLECCION}/index",
                   {"field_name": campo, "field_schema": tipo})


def punto_id(frag_id: str) -> str:
    # Qdrant acepta UUID: derivamos uno estable del _id del fragmento
    h = hashlib.md5(frag_id.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=64)  # Gemini acepta hasta 100 por llamada
    ap.add_argument("--proveedor", default="gemini", choices=PROVEEDORES)
    args = ap.parse_args()

    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGODB_URI"]).get_default_database()
    asegurar_coleccion()
    embed = PROVEEDORES[args.proveedor]

    total = 0
    while True:
        lote = list(db.fragmentos.find({"estado_embedding": "pendiente"})
                    .limit(args.batch))
        if not lote:
            break
        vectores = embed([f["texto_embedding"] for f in lote])
        puntos = [{
            "id": punto_id(f["_id"]),
            "vector": v,
            "payload": {
                "fragmento_id": f["_id"], "id_norma": f["id_norma"],
                "norma": f["norma"], "tipo_numero": f["tipo_numero"],
                "articulo": f["articulo"], "jerarquia": f["jerarquia"],
                "texto": f["texto"], "materias": f["materias"],
                "categorias": f["categorias"], "fecha_version": f["fecha_version"],
                "vigente": f["vigente"], "url_fuente": f["url_fuente"],
                "transitorio": f.get("transitorio", False), "parte": f.get("parte", ""),
                "clave_corpus": f.get("clave_corpus", ""),
                "tipo_contenido": f.get("tipo_contenido", "sustantiva"),
                "vigencia_desde": f.get("vigencia_desde", ""),
                "vigencia_anticipada": f.get("vigencia_anticipada", False),
            },
        } for f, v in zip(lote, vectores)]
        qdrant(f"/collections/{COLECCION}/points?wait=true", {"points": puntos})
        db.fragmentos.update_many(
            {"_id": {"$in": [f["_id"] for f in lote]}},
            {"$set": {"estado_embedding": "ok",
                      "embedding_modelo": args.proveedor,
                      "embedding_en": datetime.now(timezone.utc).isoformat()}})
        total += len(lote)
        print(f"Embebidos {total} fragmentos...")

    print(f"Listo: {total} fragmentos sincronizados a Qdrant/{COLECCION}.")


if __name__ == "__main__":
    sys.exit(main())
