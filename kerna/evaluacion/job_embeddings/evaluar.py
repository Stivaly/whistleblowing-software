"""
Job de Azure: vectoriza fragmentos y consultas con modelos de embeddings abiertos y los sube a Qdrant.

Por cada modelo de MODELOS:
  1. vectoriza los fragmentos vigentes (datos/fragmentos.json) y los sube a `normativa_cl_eval_<modelo>` con el
     mismo id y payload que embed_sync.py;
  2. vectoriza una por una las consultas del dataset (`texto_original` y `resumen_parafraseado`), mide el tiempo
     de cada una y las sube a `normativa_cl_eval_<modelo>_consultas` (payload: clave, ms, tokens; sin texto).
     recall_retriever.py las lee con `--vectores-consulta qdrant:<coleccion>_consultas`.

Si un modelo falla o excede su tiempo se registra y se sigue con el siguiente. Un modelo cuyas colecciones ya están
completas se omite (salvo FORZAR=1), así un reintento del job no repite lo hecho.

Variables: QDRANT_URL, QDRANT_API_KEY, MODELOS (lista separada por comas; por defecto los cuatro, el más
pesado al final), TIEMPO_MODELO_S (3600), TIEMPO_TOTAL_S (8700, bajo el límite de 9000 s del job), FORZAR.
Solo biblioteca estándar, más sentence-transformers para multilingual-e5-large-instruct.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
OLLAMA = "http://" + os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
TAREA = "Given a description of a workplace or corporate complaint, retrieve the relevant articles of Chilean legislation"
DIMS_OBJETIVO = 1024
CAMPOS = ("texto_original", "resumen_parafraseado")

# nombre -> motor, etiqueta del motor, dimensiones nativas, prefijos de documento y consulta.
CONFIG = {
    "embeddinggemma-300m": {"motor": "ollama", "tag": "embeddinggemma", "dims": 768,
                            "doc": "title: none | text: ", "consulta": "task: search result | query: "},
    "bge-m3": {"motor": "ollama", "tag": "bge-m3", "dims": 1024, "doc": "", "consulta": ""},
    "multilingual-e5-large-instruct": {"motor": "st", "tag": "intfloat/multilingual-e5-large-instruct",
                                       "dims": 1024, "doc": "", "consulta": f"Instruct: {TAREA}\nQuery: "},
    "qwen3-embedding-8b": {"motor": "ollama", "tag": "qwen3-embedding:8b", "dims": 4096, "doc": "",
                           "consulta": f"Instruct: {TAREA}\nQuery:"},
    "qwen3-embedding-4b": {"motor": "ollama", "tag": "qwen3-embedding:4b", "dims": 2560, "doc": "",
                           "consulta": f"Instruct: {TAREA}\nQuery:"},
}
POR_DEFECTO = "embeddinggemma-300m,bge-m3,multilingual-e5-large-instruct,qwen3-embedding-8b"


class TiempoExcedido(Exception):
    pass


def log(**kw):
    print(json.dumps(kw, ensure_ascii=False), flush=True)


# ---------------------------------------------------------------- HTTP
def http(url: str, body: dict | None = None, method: str = "POST", headers: dict | None = None,
         timeout: float = 900) -> dict:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def qdrant(path: str, body: dict | None = None, method: str = "PUT") -> dict:
    return http(os.environ["QDRANT_URL"].rstrip("/") + path, body, method,
                {"api-key": os.environ["QDRANT_API_KEY"]}, timeout=120)


def contar(coleccion: str) -> int | None:
    try:
        return qdrant(f"/collections/{coleccion}/points/count", {"exact": True}, "POST")["result"]["count"]
    except urllib.error.HTTPError:
        return None


def asegurar_coleccion(nombre: str, dims: int, indices: bool):
    try:
        qdrant(f"/collections/{nombre}", method="GET")
        return
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    qdrant(f"/collections/{nombre}", {"vectors": {"size": dims, "distance": "Cosine"}, "on_disk_payload": True})
    if indices:   # los mismos índices que normativa_cl
        for campo, tipo in [("categorias", "keyword"), ("id_norma", "integer"),
                            ("vigente", "bool"), ("clave_corpus", "keyword")]:
            qdrant(f"/collections/{nombre}/index", {"field_name": campo, "field_schema": tipo})


def subir(coleccion: str, puntos: list[dict], lote: int = 64):
    for i in range(0, len(puntos), lote):
        qdrant(f"/collections/{coleccion}/points?wait=true", {"points": puntos[i:i + lote]})


# ---------------------------------------------------------------- vectores
def normalizar(v: list[float], dims: int = DIMS_OBJETIVO) -> list[float]:
    """Trunca (Matryoshka) a `dims` si el modelo trae más y normaliza a norma 1."""
    v = v[:dims]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class Ollama:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.proceso = None

    def __enter__(self):
        self.proceso = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        limite = time.monotonic() + 120
        while True:   # espera por condición: el servidor responde
            try:
                http(OLLAMA + "/api/version", method="GET", timeout=5)
                break
            except Exception:
                if time.monotonic() > limite or self.proceso.poll() is not None:
                    raise RuntimeError("ollama serve no arrancó")
                time.sleep(0.5)
        log(evento="ollama_pull", modelo=self.cfg["tag"])
        http(OLLAMA + "/api/pull", {"model": self.cfg["tag"], "stream": False}, timeout=3600)
        return self

    def __exit__(self, *exc):
        try:
            http(OLLAMA + "/api/delete", {"model": self.cfg["tag"]}, "DELETE", timeout=60)   # libera el disco efímero
        except Exception:
            pass
        self.proceso.terminate()
        try:
            self.proceso.wait(30)
        except subprocess.TimeoutExpired:
            self.proceso.kill()

    def embed(self, textos: list[str], prefijo: str) -> tuple[list[list[float]], int]:
        out = http(OLLAMA + "/api/embed", {"model": self.cfg["tag"], "input": [prefijo + t for t in textos],
                                           "truncate": True, "options": {"num_ctx": 4096}})
        return [normalizar(v) for v in out["embeddings"]], int(out.get("prompt_eval_count") or 0)


class SentenceTransformers:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    def __enter__(self):
        from sentence_transformers import SentenceTransformer
        self.modelo = SentenceTransformer(self.cfg["tag"], device="cpu")
        self.modelo.max_seq_length = 512
        return self

    def __exit__(self, *exc):
        self.modelo = None

    def embed(self, textos: list[str], prefijo: str) -> tuple[list[list[float]], int]:
        entradas = [prefijo + t for t in textos]
        tokens = sum(len(self.modelo.tokenizer(t, truncation=True, max_length=512)["input_ids"]) for t in entradas)
        vs = self.modelo.encode(entradas, normalize_embeddings=True, batch_size=4)
        return [normalizar([float(x) for x in v]) for v in vs], tokens


# ---------------------------------------------------------------- datos
def texto_consulta(caso: dict, campo: str) -> str:
    # Igual que recall_retriever.texto_consulta.
    return re.sub(r"^\[Resumen parafraseado\]\s*", "", caso[campo].strip())


def clave_texto(texto: str) -> str:
    # Igual que recall_retriever.clave_texto.
    return hashlib.sha256(f"query|{texto}".encode()).hexdigest()


def id_de_clave(clave: str) -> str:
    return f"{clave[:8]}-{clave[8:12]}-{clave[12:16]}-{clave[16:20]}-{clave[20:32]}"


def cargar_datos() -> tuple[list[dict], list[str]]:
    fragmentos = json.loads((AQUI / "datos" / "fragmentos.json").read_text(encoding="utf-8"))
    casos = json.loads((AQUI / "datos" / "denuncias_publicas.json").read_text(encoding="utf-8"))["casos"]
    consultas = list(dict.fromkeys(texto_consulta(c, campo) for c in casos for campo in CAMPOS))
    return fragmentos, consultas


# ---------------------------------------------------------------- un modelo
def evaluar_modelo(nombre: str, fragmentos: list[dict], consultas: list[str], limite: float) -> dict:
    cfg = CONFIG[nombre]
    col_f = f"normativa_cl_eval_{nombre}"
    col_q = f"{col_f}_consultas"
    if os.environ.get("FORZAR") != "1" and contar(col_f) == len(fragmentos) and contar(col_q) == len(consultas):
        return {"modelo": nombre, "estado": "omitido", "motivo": "colecciones ya completas"}

    def revisar():
        if time.monotonic() > limite:
            raise TiempoExcedido(f"{nombre} excedió su tiempo")

    motor = Ollama if cfg["motor"] == "ollama" else SentenceTransformers
    t0 = time.monotonic()
    with motor(cfg) as m:
        log(evento="modelo_listo", modelo=nombre, descarga_s=round(time.monotonic() - t0, 1))
        m.embed(["calentamiento"], cfg["doc"])   # carga el modelo antes de medir
        # 1. fragmentos
        puntos, tokens_f, t1 = [], 0, time.monotonic()
        for i in range(0, len(fragmentos), 4):
            revisar()
            lote = fragmentos[i:i + 4]
            vs, tk = m.embed([f["texto_embedding"] for f in lote], cfg["doc"])
            tokens_f += tk
            puntos += [{"id": f["id"], "vector": v, "payload": f["payload"]} for f, v in zip(lote, vs)]
        dims = len(puntos[0]["vector"])
        asegurar_coleccion(col_f, dims, indices=True)
        subir(col_f, puntos)
        log(evento="fragmentos_listos", modelo=nombre, n=len(puntos), dims=dims, tokens=tokens_f,
            segundos=round(time.monotonic() - t1, 1))
        # 2. consultas, una por petición
        puntos_q, ms, tokens_q = [], [], 0
        for texto in consultas:
            revisar()
            t = time.perf_counter()
            (v,), tk = m.embed([texto], cfg["consulta"])
            dt = (time.perf_counter() - t) * 1000
            ms.append(dt)
            tokens_q += tk
            clave = clave_texto(texto)
            puntos_q.append({"id": id_de_clave(clave), "vector": v,
                             "payload": {"clave": clave, "ms": round(dt, 1), "tokens": tk, "modelo": nombre}})
        asegurar_coleccion(col_q, dims, indices=False)
        subir(col_q, puntos_q)
    ms.sort()
    p95 = ms[max(0, math.ceil(0.95 * len(ms)) - 1)]
    return {"modelo": nombre, "estado": "ok", "dims": dims, "fragmentos": len(puntos), "consultas": len(puntos_q),
            "tokens_fragmentos": tokens_f, "tokens_consultas": tokens_q, "p95_consulta_ms": round(p95, 1),
            "segundos": round(time.monotonic() - t0, 1)}


def main() -> int:
    inicio = time.monotonic()
    total = float(os.environ.get("TIEMPO_TOTAL_S", "8700"))
    por_modelo = float(os.environ.get("TIEMPO_MODELO_S", "3600"))
    modelos = [m.strip() for m in os.environ.get("MODELOS", POR_DEFECTO).split(",") if m.strip()]
    desconocidos = [m for m in modelos if m not in CONFIG]
    if desconocidos:
        log(evento="error", motivo=f"modelos desconocidos: {desconocidos}", validos=sorted(CONFIG))
        return 2
    fragmentos, consultas = cargar_datos()
    log(evento="inicio", modelos=modelos, fragmentos=len(fragmentos), consultas=len(consultas))
    resultados = []
    for nombre in modelos:
        limite = min(time.monotonic() + por_modelo, inicio + total)
        if time.monotonic() >= inicio + total:
            resultados.append({"modelo": nombre, "estado": "no_ejecutado", "motivo": "se agotó el tiempo total"})
            continue
        try:
            r = evaluar_modelo(nombre, fragmentos, consultas, limite)
        except Exception as e:  # noqa: BLE001  (un modelo que falla no detiene a los demás)
            r = {"modelo": nombre, "estado": "tiempo_excedido" if isinstance(e, TiempoExcedido) else "error",
                 "motivo": f"{type(e).__name__}: {e}"[:300]}
        log(evento="resultado_modelo", **r)
        resultados.append(r)
    log(evento="fin", segundos=round(time.monotonic() - inicio, 1), resultados=resultados)
    return 0 if any(r["estado"] in ("ok", "omitido") for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
