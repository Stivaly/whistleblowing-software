"""
Sincronizador de embeddings: Mongo (fragmentos pendientes) -> Qdrant Cloud.

Toma cada fragmento con estado_embedding="pendiente", genera el embedding del
campo `texto_embedding` (proveedor configurable) y hace upsert en Qdrant con
payload de metadatos para filtrado. Idempotente: el ID del punto es estable
(hash del _id del fragmento), y si un artículo no cambió su hash_texto,
extraer_bcn.py no lo vuelve a marcar pendiente.

Uso:
  python3 embed_sync.py [--batch 64] [--proveedor voyage|gemini|openai]

Variables de entorno:
  MONGODB_URI, QDRANT_URL, QDRANT_API_KEY
  VOYAGE_API_KEY   (proveedor voyage, por defecto: voyage-4-large, multilingüe)
  VOYAGE_TPM, VOYAGE_RPM  (límites de la cuenta; por defecto 10000 tokens y 3 peticiones
                   por minuto, los de una cuenta sin medio de pago)
  GEMINI_API_KEY   (proveedor gemini: gemini-embedding-2)
  OPENAI_API_KEY   (proveedor openai: text-embedding-3-large, dims=1024)

Las consultas del retriever usan embed_consulta() (input_type "query"): documentos y
consultas deben salir del mismo modelo y con las mismas dimensiones.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

COLECCION = "normativa_cl"
DIMS = 1024
VOYAGE_MODELO = "voyage-4-large"


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


# Estimación conservadora de tokens para armar lotes antes de llamar a la API (el
# español con el tokenizador de Voyage ronda 3,5-4 caracteres por token). El ritmo real
# se ajusta con usage.total_tokens de cada respuesta.
CHARS_POR_TOKEN = 3
_voyage_proxima = 0.0  # time.monotonic() desde el que se puede hacer la siguiente petición


def _voyage_limites() -> tuple[int, int]:
    return int(os.environ.get("VOYAGE_TPM", "10000")), int(os.environ.get("VOYAGE_RPM", "3"))


def _lotes_por_tokens(textos: list[str], max_tokens: int) -> list[list[str]]:
    lotes, actual, tokens = [], [], 0
    for t in textos:
        n = len(t) // CHARS_POR_TOKEN + 1
        if actual and tokens + n > max_tokens:
            lotes.append(actual)
            actual, tokens = [], 0
        actual.append(t)
        tokens += n
    if actual:
        lotes.append(actual)
    return lotes


def _voyage_peticion(textos: list[str], input_type: str) -> list[list[float]]:
    global _voyage_proxima
    tpm, rpm = _voyage_limites()
    for intento in range(5):
        time.sleep(max(0.0, _voyage_proxima - time.monotonic()))
        try:
            out = _post("https://api.voyageai.com/v1/embeddings",
                        {"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
                        {"model": VOYAGE_MODELO, "input": textos,
                         "input_type": input_type, "output_dimension": DIMS})
        except urllib.error.HTTPError as e:
            if e.code != 429 or intento == 4:
                raise
            espera = float(e.headers.get("Retry-After") or 60)
            print(f"Voyage: límite de uso (429), espero {espera:.0f} s", flush=True)
            _voyage_proxima = time.monotonic() + espera
            continue
        # La siguiente petición espera lo que exija el más estricto de los dos límites.
        usados = out.get("usage", {}).get("total_tokens", 0)
        _voyage_proxima = time.monotonic() + max(60 / rpm, usados * 60 / tpm)
        return [d["embedding"] for d in sorted(out["data"], key=lambda d: d["index"])]
    raise RuntimeError("Voyage: se agotaron los reintentos")


def embed_voyage(textos: list[str], input_type: str = "document") -> list[list[float]]:
    # Lotes chicos (bajo el límite de tokens por minuto) y espera entre peticiones.
    tpm, _ = _voyage_limites()
    vectores = []
    for lote in _lotes_por_tokens(textos, int(tpm * 0.8)):
        vectores += _voyage_peticion(lote, input_type)
    return vectores


def embed_consulta(texto: str) -> list[float]:
    """Embedding de una consulta del retriever (mismo espacio que los documentos)."""
    return embed_voyage([texto], input_type="query")[0]


def embed_openai(textos: list[str]) -> list[list[float]]:
    out = _post("https://api.openai.com/v1/embeddings",
                {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                {"model": "text-embedding-3-large", "input": textos, "dimensions": DIMS})
    return [d["embedding"] for d in out["data"]]


PROVEEDORES = {"voyage": embed_voyage, "gemini": embed_gemini, "openai": embed_openai}
MODELOS = {"voyage": VOYAGE_MODELO, "gemini": "gemini-embedding-2",
           "openai": "text-embedding-3-large"}


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
    # Fragmentos leídos de Mongo por vuelta; Voyage los reparte en peticiones según tokens.
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--proveedor", default="voyage", choices=PROVEEDORES)
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
        if len(vectores) != len(lote) or any(len(v) != DIMS for v in vectores):
            raise RuntimeError(f"{args.proveedor}: se esperaban {len(lote)} vectores de {DIMS} dimensiones")
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
                      "embedding_modelo": MODELOS[args.proveedor],
                      "embedding_en": datetime.now(timezone.utc).isoformat()}})
        total += len(lote)
        print(f"Embebidos {total} fragmentos...", flush=True)

    print(f"Listo: {total} fragmentos sincronizados a Qdrant/{COLECCION}.")


if __name__ == "__main__":
    sys.exit(main())
