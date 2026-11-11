"""
Sincronizador de embeddings: Mongo (fragmentos pendientes) -> colecciones de Qdrant Cloud.

Cada colección tiene su proveedor, modelo y dimensiones. Un fragmento está pendiente para una
colección si no tiene entrada en `embeddings.<coleccion>` o si su `hash_texto`, su `firma` (texto
contextualizado + vigencia + categorías) o el modelo difieren de los de esa entrada. Se vectoriza
`texto_embedding` y se hace upsert en Qdrant con el payload de metadatos. El ID del punto es
estable (hash del _id del fragmento). Cada colección tiene además un punto reservado de metadatos
(`PUNTO_META_ID`) con la `version_corpus` vigente.

Uso:
  python3 embed_sync.py                                  # normativa_cl (colecciones.json)
  python3 embed_sync.py --todas                          # todas las colecciones activas
  python3 embed_sync.py --todas --si-cambios RESULTADO   # regla de disparo de run.sh
  python3 embed_sync.py --coleccion X --proveedor azure-openai --modelo text-embedding-3-large
  python3 embed_sync.py --paridad [--coleccion X | --todas]

Variables de entorno:
  MONGODB_URI, QDRANT_URL, QDRANT_API_KEY
  VOYAGE_API_KEY   (proveedor voyage: voyage-4-large, voyage-4-lite, voyage-law-2)
  VOYAGE_TPM, VOYAGE_RPM  (límites de la cuenta; por defecto 10000 tokens y 3 peticiones
                   por minuto, los de una cuenta sin medio de pago)
  AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY  (proveedor azure-openai; el despliegue se llama
                   como el modelo, o AZURE_OPENAI_DEPLOYMENT)
  KERNA_LOCAL_URL, KERNA_LOCAL_TOKEN  (proveedor local: POST /embed con X-Token-Interno)
  GEMINI_API_KEY   (proveedor gemini: gemini-embedding-2)
  OPENAI_API_KEY   (proveedor openai: text-embedding-3-large, dims=1024)

Las consultas del retriever usan embed_consulta() (input_type "query"): documentos y
consultas deben salir del mismo modelo y con las mismas dimensiones.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

COLECCION = "normativa_cl"
DIMS = 1024
VOYAGE_MODELO = "voyage-4-large"
COLECCIONES_JSON = Path(__file__).resolve().parent / "colecciones.json"
PUNTO_META_ID = "00000000-0000-0000-0000-000000000000"
# Colección anterior al mapa `embeddings`: sus fragmentos con estado_embedding="ok" y el mismo
# modelo cuentan como sincronizados aunque no tengan entrada en el mapa.
COLECCION_LEGADA = "normativa_cl"
# Modelos de Voyage que no aceptan output_dimension (dimensión fija de 1024).
VOYAGE_SIN_OUTPUT_DIMENSION = {"voyage-law-2"}

# Medición de la última tanda de peticiones (la lee evaluacion/recall_retriever.py): tokens
# informados por el proveedor y latencia de cada petición HTTP, sin las esperas por límites.
MEDICION: dict = {"tokens": 0, "latencias_ms": []}


def reiniciar_medicion():
    MEDICION["tokens"] = 0
    MEDICION["latencias_ms"] = []


def _post(url: str, headers: dict, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _post_medido(url: str, headers: dict, body: dict) -> dict:
    """_post que registra la latencia de la petición en MEDICION."""
    t0 = time.perf_counter()
    out = _post(url, headers, body)
    MEDICION["latencias_ms"].append((time.perf_counter() - t0) * 1000)
    return out


def _tokens(usage: dict | None):
    n = (usage or {}).get("total_tokens") or (usage or {}).get("prompt_tokens") or 0
    MEDICION["tokens"] += n
    return n


def _espera_429(e: urllib.error.HTTPError, intento: int, base: float) -> float:
    """Retry-After si lo hay; si no, una espera creciente (base, 2 base, 3 base...)."""
    return float(e.headers.get("Retry-After") or base * (intento + 1))


def embed_gemini(textos: list[str], tipo: str = "document", modelo: str = "gemini-embedding-2",
                 dims: int = DIMS) -> list[list[float]]:
    # gemini-embedding-2 no usa task_type: la tarea va en el texto. Formato de documento
    # para búsqueda; el título va en "none" porque texto_embedding ya trae la norma.
    # Con menos de 3072 dimensiones el modelo devuelve los vectores ya normalizados.
    ruta = f"models/{modelo}"
    out = _post_medido(f"https://generativelanguage.googleapis.com/v1beta/{ruta}:batchEmbedContents",
                       {"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                       {"requests": [{"model": ruta,
                                      "content": {"parts": [{"text": f"title: none | text: {t}"}]},
                                      "outputDimensionality": dims} for t in textos]})
    return [e["values"] for e in out["embeddings"]]


# Estimación conservadora de tokens para armar lotes antes de llamar a la API (el
# español con el tokenizador de Voyage ronda 3,5-4 caracteres por token). El ritmo real
# se ajusta con usage.total_tokens de cada respuesta.
CHARS_POR_TOKEN = 3
_voyage_proxima = 0.0  # time.monotonic() desde el que se puede hacer la siguiente petición


def _voyage_limites() -> tuple[int, int]:
    return int(os.environ.get("VOYAGE_TPM", "10000")), int(os.environ.get("VOYAGE_RPM", "3"))


def _lotes_por_tokens(textos: list[str], max_tokens: int, max_textos: int | None = None) -> list[list[str]]:
    lotes, actual, tokens = [], [], 0
    for t in textos:
        n = len(t) // CHARS_POR_TOKEN + 1
        if actual and (tokens + n > max_tokens or (max_textos and len(actual) >= max_textos)):
            lotes.append(actual)
            actual, tokens = [], 0
        actual.append(t)
        tokens += n
    if actual:
        lotes.append(actual)
    return lotes


def _cuerpo_voyage(textos: list[str], input_type: str, modelo: str, dims: int) -> dict:
    cuerpo = {"model": modelo, "input": textos, "input_type": input_type}
    if modelo not in VOYAGE_SIN_OUTPUT_DIMENSION:   # voyage-law-2: 1024 fijas
        cuerpo["output_dimension"] = dims
    return cuerpo


def _voyage_peticion(textos: list[str], input_type: str, modelo: str = VOYAGE_MODELO,
                     dims: int = DIMS) -> list[list[float]]:
    global _voyage_proxima
    tpm, rpm = _voyage_limites()
    for intento in range(5):
        time.sleep(max(0.0, _voyage_proxima - time.monotonic()))
        try:
            out = _post_medido("https://api.voyageai.com/v1/embeddings",
                               {"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
                               _cuerpo_voyage(textos, input_type, modelo, dims))
        except urllib.error.HTTPError as e:
            if e.code != 429 or intento == 4:
                raise
            espera = _espera_429(e, intento, 60)
            print(f"Voyage: límite de uso (429), espero {espera:.0f} s", flush=True)
            _voyage_proxima = time.monotonic() + espera
            continue
        # La siguiente petición espera lo que exija el más estricto de los dos límites.
        usados = _tokens(out.get("usage"))
        _voyage_proxima = time.monotonic() + max(60 / rpm, usados * 60 / tpm)
        return [d["embedding"] for d in sorted(out["data"], key=lambda d: d["index"])]
    raise RuntimeError("Voyage: se agotaron los reintentos")


def embed_voyage(textos: list[str], input_type: str = "document", modelo: str = VOYAGE_MODELO,
                 dims: int = DIMS) -> list[list[float]]:
    # Lotes chicos (bajo el límite de tokens por minuto) y espera entre peticiones.
    tpm, _ = _voyage_limites()
    vectores = []
    for lote in _lotes_por_tokens(textos, int(tpm * 0.8)):
        vectores += _voyage_peticion(lote, input_type, modelo, dims)
    return vectores


def embed_consultas(textos: list[str], modelo: str = VOYAGE_MODELO, dims: int = DIMS) -> list[list[float]]:
    """Embeddings de varias consultas en lotes, con los límites de Voyage."""
    return embed_voyage(textos, input_type="query", modelo=modelo, dims=dims)


def embed_consulta(texto: str) -> list[float]:
    """Embedding de una consulta del retriever (mismo espacio que los documentos)."""
    return embed_consultas([texto])[0]


def embed_azure_openai(textos: list[str], tipo: str = "document", modelo: str = "text-embedding-3-large",
                       dims: int = DIMS) -> list[list[float]]:
    """Azure OpenAI: el despliegue se llama como el modelo (o AZURE_OPENAI_DEPLOYMENT)."""
    base = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
    despliegue = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or modelo
    url = f"{base}/openai/deployments/{despliegue}/embeddings?api-version=2024-10-21"
    vectores = []
    for lote in _lotes_por_tokens(textos, 20000, max_textos=16):
        for intento in range(5):
            try:
                out = _post_medido(url, {"api-key": os.environ["AZURE_OPENAI_KEY"]},
                                   {"input": lote, "dimensions": dims})
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or intento == 4:
                    raise
                espera = _espera_429(e, intento, 10)
                print(f"Azure OpenAI: límite de uso (429), espero {espera:.0f} s", flush=True)
                time.sleep(espera)
        _tokens(out.get("usage"))
        vectores += [d["embedding"] for d in sorted(out["data"], key=lambda d: d["index"])]
    return vectores


def embed_local(textos: list[str], tipo: str = "document", modelo: str = "local",
                dims: int = DIMS) -> list[list[float]]:
    """Servicio local del contrato: POST {KERNA_LOCAL_URL}/embed con X-Token-Interno."""
    url = os.environ["KERNA_LOCAL_URL"].rstrip("/") + "/embed"
    cabecera = {"X-Token-Interno": os.environ.get("KERNA_LOCAL_TOKEN", "")}
    vectores = []
    for lote in _lotes_por_tokens(textos, 20000, max_textos=16):
        out = _post_medido(url, cabecera, {"textos": lote, "tipo": tipo})
        vectores += out["vectores"]
    return vectores


def embed_openai(textos: list[str]) -> list[list[float]]:
    out = _post_medido("https://api.openai.com/v1/embeddings",
                       {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                       {"model": "text-embedding-3-large", "input": textos, "dimensions": DIMS})
    return [d["embedding"] for d in out["data"]]


# Funciones por defecto de cada proveedor (solo textos). Para modelo y dimensiones propios,
# crear_embedder().
PROVEEDORES = {"voyage": embed_voyage, "gemini": embed_gemini, "openai": embed_openai,
               "azure-openai": embed_azure_openai, "local": embed_local}
MODELOS = {"voyage": VOYAGE_MODELO, "gemini": "gemini-embedding-2",
           "openai": "text-embedding-3-large", "azure-openai": "text-embedding-3-large",
           "local": "local"}


def crear_embedder(proveedor: str, modelo: str | None = None, dims: int = DIMS):
    """-> f(textos, tipo="document"|"query") -> vectores, para el proveedor y modelo dados."""
    if proveedor not in PROVEEDORES:
        raise ValueError(f"proveedor desconocido: {proveedor}")
    modelo = modelo or MODELOS[proveedor]
    if proveedor == "voyage":
        return lambda textos, tipo="document": embed_voyage(textos, tipo, modelo, dims)
    if proveedor == "azure-openai":
        return lambda textos, tipo="document": embed_azure_openai(textos, tipo, modelo, dims)
    if proveedor == "local":
        return lambda textos, tipo="document": embed_local(textos, tipo, modelo, dims)
    if proveedor == "gemini":
        return lambda textos, tipo="document": embed_gemini(textos, tipo, modelo, dims)
    return lambda textos, tipo="document": embed_openai(textos)


# ---------------------------------------------------------------- colecciones activas
def cargar_colecciones(ruta: Path | str | None = None, solo_activas: bool = True) -> list[dict]:
    """Colecciones de colecciones.json: [{nombre, proveedor, modelo, dims, activa?}, ...]."""
    datos = json.loads(Path(ruta or COLECCIONES_JSON).read_text(encoding="utf-8"))
    cols = datos["colecciones"] if isinstance(datos, dict) else datos
    for c in cols:
        for k in ("nombre", "proveedor", "modelo", "dims"):
            if k not in c:
                raise ValueError(f"colecciones.json: falta {k!r} en {c}")
    return [c for c in cols if c.get("activa", True)] if solo_activas else cols


# ---------------------------------------------------------------- Qdrant
def qdrant(path: str, body: dict | None = None, method: str = "PUT") -> dict:
    url = os.environ["QDRANT_URL"].rstrip("/") + path
    headers = {"api-key": os.environ["QDRANT_API_KEY"],
               "Content-Type": "application/json"}
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def asegurar_coleccion(nombre: str = COLECCION, dims: int = DIMS):
    try:
        qdrant(f"/collections/{nombre}", method="GET")
    except Exception:
        qdrant(f"/collections/{nombre}", {
            "vectors": {"size": dims, "distance": "Cosine"},
            "on_disk_payload": True,
        })
        for campo, tipo in [("categorias", "keyword"), ("id_norma", "integer"),
                            ("vigente", "bool"), ("clave_corpus", "keyword")]:
            qdrant(f"/collections/{nombre}/index",
                   {"field_name": campo, "field_schema": tipo})


def punto_id(frag_id: str) -> str:
    # Qdrant acepta UUID: derivamos uno estable del _id del fragmento
    h = hashlib.md5(frag_id.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def payload_de(f: dict) -> dict:
    return {
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
    }


# ---------------------------------------------------------------- estado por colección
def filtro_pendientes(col: dict) -> dict:
    """Fragmentos pendientes para la colección `col`, como consulta de Mongo (sin proveedores).

    Pendiente = sin entrada en embeddings.<nombre>, o con entrada de otro modelo, otro
    hash_texto u otra firma. Los "no_aplica" (no sustantivos) nunca se vectorizan."""
    n, modelo = col["nombre"], col["modelo"]
    entrada = f"$embeddings.{n}"
    sin_entrada: dict = {f"embeddings.{n}": {"$exists": False}}
    if n == COLECCION_LEGADA:
        sin_entrada["$nor"] = [{"estado_embedding": "ok", "embedding_modelo": modelo}]
    distinta = {f"embeddings.{n}": {"$exists": True}, "$expr": {"$or": [
        {"$ne": [{"$ifNull": [f"{entrada}.modelo", ""]}, modelo]},
        {"$ne": [{"$ifNull": [f"{entrada}.hash_texto", ""]}, {"$ifNull": ["$hash_texto", ""]}]},
        {"$ne": [{"$ifNull": [f"{entrada}.firma", ""]}, {"$ifNull": ["$firma", ""]}]},
    ]}}
    return {"estado_embedding": {"$ne": "no_aplica"}, "$or": [sin_entrada, distinta]}


def contar_pendientes(db, col: dict) -> int:
    return db.fragmentos.count_documents(filtro_pendientes(col))


def version_corpus(db) -> int:
    """Contador que extraer_bcn.py incrementa cuando hay fragmentos nuevos, cambiados o retirados."""
    doc = db.meta.find_one({"_id": "corpus"}) or {}
    return int(doc.get("version_corpus", 0))


def actualizar_meta(col: dict, db) -> dict:
    """Punto reservado de metadatos de la colección (vigente=false: nunca sale en búsquedas)."""
    payload = {"tipo": "meta", "vigente": False, "version_corpus": version_corpus(db),
               "modelo": col["modelo"], "actualizado_en": datetime.now(timezone.utc).isoformat()}
    vector = [1.0] + [0.0] * (col["dims"] - 1)   # el vector no se usa: es unitario para el coseno
    qdrant(f"/collections/{col['nombre']}/points?wait=true",
           {"points": [{"id": PUNTO_META_ID, "vector": vector, "payload": payload}]})
    return payload


def sincronizar_coleccion(db, col: dict, batch: int = 64, embed=None) -> int:
    """Vectoriza los fragmentos pendientes de `col` y los sube. -> cantidad sincronizada."""
    from pymongo import UpdateOne

    embed = embed or crear_embedder(col["proveedor"], col["modelo"], col["dims"])
    asegurar_coleccion(col["nombre"], col["dims"])
    total = 0
    while True:
        lote = list(db.fragmentos.find(filtro_pendientes(col)).limit(batch))
        if not lote:
            break
        vectores = embed([f["texto_embedding"] for f in lote], "document")
        if len(vectores) != len(lote) or any(len(v) != col["dims"] for v in vectores):
            raise RuntimeError(f"{col['nombre']}: se esperaban {len(lote)} vectores de {col['dims']} dimensiones")
        qdrant(f"/collections/{col['nombre']}/points?wait=true", {"points": [
            {"id": punto_id(f["_id"]), "vector": v, "payload": payload_de(f)}
            for f, v in zip(lote, vectores)]})
        ahora = datetime.now(timezone.utc).isoformat()
        ops = []
        for f in lote:
            cambios = {f"embeddings.{col['nombre']}": {
                "modelo": col["modelo"], "hash_texto": f.get("hash_texto", ""),
                "firma": f.get("firma", ""), "en": ahora}}
            if col["nombre"] == COLECCION_LEGADA:   # compatibilidad con estado_embedding
                cambios.update({"estado_embedding": "ok", "embedding_modelo": col["modelo"],
                                "embedding_en": ahora})
            ops.append(UpdateOne({"_id": f["_id"]}, {"$set": cambios}))
        db.fragmentos.bulk_write(ops, ordered=False)
        total += len(lote)
        print(f"[{col['nombre']}] embebidos {total} fragmentos...", flush=True)
    if total:
        actualizar_meta(col, db)
    print(f"[{col['nombre']}] listo: {total} fragmentos sincronizados ({col['proveedor']}/{col['modelo']}).")
    return total


# ---------------------------------------------------------------- paridad Mongo <-> colección
def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def puntos_de(coleccion: str) -> dict[str, dict]:
    """payload de cada punto de la colección por fragmento_id (sin el punto meta)."""
    puntos, offset = {}, None
    while True:
        body = {"limit": 256, "with_payload": True, "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        out = qdrant(f"/collections/{coleccion}/points/scroll", body, method="POST")["result"]
        for p in out["points"]:
            pl = p.get("payload") or {}
            if pl.get("tipo") != "meta" and "fragmento_id" in pl:
                puntos[pl["fragmento_id"]] = pl
        offset = out.get("next_page_offset")
        if offset is None:
            return puntos


def verificar_paridad(coleccion: str, db=None, puntos: dict | None = None) -> dict:
    """Compara por fragmento vigente texto (hash) y vigencia entre Mongo y la colección.

    faltantes: vigente en Mongo, sin punto. desactualizados: con punto pero texto distinto o
    vigente=false. sobrantes: puntos vigente=true cuyo fragmento ya no es vigente en Mongo
    (o no existe). Los puntos vigente=false de fragmentos no vigentes son correctos."""
    if db is None:
        from pymongo import MongoClient
        db = MongoClient(os.environ["MONGODB_URI"]).get_default_database()
    puntos = puntos_de(coleccion) if puntos is None else puntos
    vigentes = {f["_id"]: f for f in db.fragmentos.find(
        {"vigente": True, "estado_embedding": {"$ne": "no_aplica"}},
        {"texto": 1, "hash_texto": 1})}
    faltantes = sorted(i for i in vigentes if i not in puntos)
    desactualizados = sorted(
        i for i, f in vigentes.items() if i in puntos and (
            _sha(puntos[i].get("texto", "")) != _sha(f["texto"])
            or puntos[i].get("vigente") is not True))
    sobrantes = sorted(i for i, pl in puntos.items() if pl.get("vigente") is True and i not in vigentes)
    return {"coleccion": coleccion, "faltantes": faltantes, "sobrantes": sobrantes,
            "desactualizados": desactualizados,
            "ok": not (faltantes or sobrantes or desactualizados)}


# ---------------------------------------------------------------- regla de disparo
def leer_resultado(ruta: Path | str) -> dict | None:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def sincronizar_todas(db, colecciones: list[dict], batch: int = 64) -> int:
    """Sincroniza cada colección; si una falla sigue con las demás. -> 0 si todas bien, 1 si no."""
    errores = 0
    for col in colecciones:
        try:
            sincronizar_coleccion(db, col, batch)
        except Exception as e:  # noqa: BLE001
            errores += 1
            print(f"[{col['nombre']}] ERROR: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
    return 1 if errores else 0


def disparar(db, colecciones: list[dict], ruta_resultado: Path | str, batch: int = 64) -> int:
    """Regla de disparo: vectoriza solo si la extracción terminó bien y trajo cambios, o si
    alguna colección quedó con fragmentos pendientes de una corrida anterior fallida."""
    res = leer_resultado(ruta_resultado)
    if res is None:
        print("Sin resultado de extracción legible: no se vectoriza.", file=sys.stderr)
        return 1
    if not res.get("ok", False):
        print("La extracción falló: no se vectoriza.", file=sys.stderr)
        return 1
    cambios = int(res.get("cambios", 0))
    pendientes = {c["nombre"]: contar_pendientes(db, c) for c in colecciones}
    if cambios == 0 and not any(pendientes.values()):
        print("sin cambios: ningún fragmento nuevo, modificado ni pendiente; no se llama a ningún proveedor.")
        return 0
    print(f"Cambios en la extracción: {cambios}; pendientes por colección: {pendientes}")
    return sincronizar_todas(db, colecciones, batch)


def _config_desde_args(args) -> dict:
    base = next((c for c in cargar_colecciones(solo_activas=False) if c["nombre"] == args.coleccion), None) \
        if args.coleccion else None
    if base is None and args.coleccion is None:
        base = next((c for c in cargar_colecciones(solo_activas=False) if c["nombre"] == COLECCION), None)
    proveedor = args.proveedor or (base or {}).get("proveedor") or "voyage"
    return {"nombre": args.coleccion or (base or {}).get("nombre") or COLECCION,
            "proveedor": proveedor,
            "modelo": args.modelo or ((base or {}).get("modelo") if not args.proveedor else None)
            or MODELOS[proveedor],
            "dims": args.dims or (base or {}).get("dims") or DIMS}


def main(argv=None):
    ap = argparse.ArgumentParser()
    # Fragmentos leídos de Mongo por vuelta; Voyage los reparte en peticiones según tokens.
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--proveedor", choices=PROVEEDORES)
    ap.add_argument("--modelo")
    ap.add_argument("--coleccion")
    ap.add_argument("--dims", type=int)
    ap.add_argument("--todas", action="store_true", help="todas las colecciones activas de colecciones.json")
    ap.add_argument("--si-cambios", metavar="RESULTADO",
                    help="regla de disparo: lee el resultado de extraer_bcn.py y solo vectoriza si hubo "
                         "cambios o quedaron pendientes")
    ap.add_argument("--paridad", action="store_true",
                    help="compara Mongo con la colección (o con todas) y sale con 1 si difieren")
    args = ap.parse_args(argv)

    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGODB_URI"]).get_default_database()
    colecciones = cargar_colecciones() if args.todas else [_config_desde_args(args)]

    if args.paridad:
        resultados = [verificar_paridad(c["nombre"], db) for c in colecciones]
        for r in resultados:
            print(f"[{r['coleccion']}] paridad {'OK' if r['ok'] else 'CON DIFERENCIAS'}: "
                  f"{len(r['faltantes'])} faltantes, {len(r['sobrantes'])} sobrantes, "
                  f"{len(r['desactualizados'])} desactualizados")
            for k in ("faltantes", "sobrantes", "desactualizados"):
                for i in r[k][:20]:
                    print(f"  {k}: {i}")
        return 0 if all(r["ok"] for r in resultados) else 1
    if args.si_cambios:
        return disparar(db, colecciones, args.si_cambios, args.batch)
    if args.todas:
        return sincronizar_todas(db, colecciones, args.batch)
    sincronizar_coleccion(db, colecciones[0], args.batch)   # una sola: los errores se propagan
    return 0


if __name__ == "__main__":
    sys.exit(main())
