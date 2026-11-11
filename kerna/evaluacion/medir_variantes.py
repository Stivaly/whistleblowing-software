"""Mide variantes del texto vectorizado por fragmento con text-embedding-3-large (Azure OpenAI, 1024 dims).

No toca las colecciones de producción ni `texto_embedding` de Mongo: lee los fragmentos vigentes de
`job_embeddings/datos/fragmentos.json` (copia local usada también por analisis_recall_articulo.py), construye el
texto de la variante (`variantes_texto.py`) y lo sube a una colección propia `normativa_cl_eval_te3l_var<V>`.
La medición la hace `recall_retriever.py --coleccion <esa colección>` (las consultas no cambian).

  /usr/bin/python3 evaluacion/medir_variantes.py resumenes            # Gemini -> datos/resumenes_materia.json
  /usr/bin/python3 evaluacion/medir_variantes.py vectorizar A|AB      # Azure OpenAI -> Qdrant
  /usr/bin/python3 evaluacion/medir_variantes.py medir A|AB           # recall_retriever.py

Variables: GEMINI_API_KEY (resúmenes); AZURE_OPENAI_ENDPOINT y AZURE_OPENAI_KEY, QDRANT_URL y QDRANT_API_KEY.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "pipeline_bcn"))

import variantes_texto as vt  # noqa: E402

FRAGMENTOS = AQUI / "job_embeddings" / "datos" / "fragmentos.json"
CACHE_RESUMENES = AQUI / "datos" / "resumenes_materia.json"
MODELO_RESUMEN = "gemini-3.5-flash-lite"
MODELO_EMBEDDING = "text-embedding-3-large"
DIMS = 1024
PAUSA_ENTRE_PETICIONES_S = 4.0     # margen bajo el límite de tasa del nivel gratuito


def coleccion_de(variante: str) -> str:
    return f"normativa_cl_eval_te3l_var{variante}"


def cargar_fragmentos(ruta: Path = FRAGMENTOS) -> list[dict]:
    return json.loads(ruta.read_text())


def cargar_cache(ruta: Path = CACHE_RESUMENES) -> dict[str, dict]:
    return json.loads(ruta.read_text()) if ruta.exists() else {}


def guardar_cache(cache: dict, ruta: Path = CACHE_RESUMENES):
    ruta.parent.mkdir(exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    tmp.replace(ruta)


def resumenes_de(cache: dict) -> dict[str, str]:
    return {k: v["resumen"] for k, v in cache.items() if v.get("resumen")}


def cobertura(fragmentos: list[dict], cache: dict) -> tuple[int, int]:
    res = resumenes_de(cache)
    return sum(f["payload"]["fragmento_id"] in res for f in fragmentos), len(fragmentos)


# ---------------------------------------------------------------- Gemini
def _gemini(prompt: str, intentos: int = 8) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO_RESUMEN}:generateContent"
    cuerpo = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                         "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600}}).encode()
    espera = 10.0
    for i in range(intentos):
        req = urllib.request.Request(url, cuerpo, {"Content-Type": "application/json",
                                                   "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                out = json.load(r)
            partes = out["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in partes if not p.get("thought"))
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 503) or i == intentos - 1:
                raise
            print(f"  HTTP {e.code}, reintento en {espera:.0f} s", flush=True)
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as e:
            if i == intentos - 1:
                raise
            print(f"  {type(e).__name__}, reintento en {espera:.0f} s", flush=True)
        time.sleep(espera)
        espera = min(espera * 1.7, 90)
    raise RuntimeError("sin respuesta")


def generar_resumenes(fragmentos: list[dict], cache: dict, generar=_gemini, pausa: float = PAUSA_ENTRE_PETICIONES_S,
                      guardar=guardar_cache) -> dict:
    """Completa la caché con los resúmenes que falten. Si la cuota se agota (429 sin remedio) se detiene y
    conserva lo hecho."""
    for n, f in enumerate(fragmentos, 1):
        fid = f["payload"]["fragmento_id"]
        if cache.get(fid, {}).get("resumen"):
            continue
        try:
            r = vt.limpiar_resumen(generar(vt.prompt_resumen(f)))
        except urllib.error.HTTPError as e:
            print(f"detenido en {fid}: HTTP {e.code} (cuota)", flush=True)
            break
        if not r:
            print(f"  {fid}: respuesta vacía", flush=True)
            continue
        cache[fid] = {"resumen": r, "modelo": MODELO_RESUMEN, "en": time.strftime("%Y-%m-%dT%H:%M:%S")}
        guardar(cache)
        print(f"[{n}/{len(fragmentos)}] {fid}: {len(r)} caracteres", flush=True)
        time.sleep(pausa)
    return cache


# ---------------------------------------------------------------- vectorizar
def vectorizar(variante: str, fragmentos: list[dict], resumenes: dict[str, str] | None = None, lote: int = 32):
    import embed_sync as E
    textos = [vt.construir(f, variante, resumenes) for f in fragmentos]
    col = coleccion_de(variante)
    E.asegurar_coleccion(col, DIMS)
    for i in range(0, len(fragmentos), lote):
        sub = fragmentos[i:i + lote]
        vecs = E.embed_azure_openai(textos[i:i + lote], "document", MODELO_EMBEDDING, DIMS)
        if len(vecs) != len(sub) or any(len(v) != DIMS for v in vecs):
            raise RuntimeError("vectores incompletos")
        E.qdrant(f"/collections/{col}/points?wait=true", {"points": [
            {"id": E.punto_id(f["payload"]["fragmento_id"]), "vector": v, "payload": f["payload"]}
            for f, v in zip(sub, vecs)]})
        print(f"[{col}] {min(i + lote, len(fragmentos))}/{len(fragmentos)}", flush=True)
    return col


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    if not a or a[0] not in ("resumenes", "vectorizar", "medir"):
        print(__doc__)
        return 2
    frs = cargar_fragmentos()
    if a[0] == "resumenes":
        cache = generar_resumenes(frs, cargar_cache())
        ok, total = cobertura(frs, cache)
        print(f"cobertura de resúmenes: {ok}/{total}")
        return 0 if ok == total else 1
    var = a[1]
    if a[0] == "vectorizar":
        res = None
        if var == "AB":
            cache = cargar_cache()
            ok, total = cobertura(frs, cache)
            if ok != total:
                print(f"resúmenes incompletos ({ok}/{total}): no se vectoriza AB")
                return 1
            res = resumenes_de(cache)
        vectorizar(var, frs, res)
        return 0
    import recall_retriever as R
    return R.main(["--coleccion", coleccion_de(var), "--proveedor", "azure-openai", "--modelo", MODELO_EMBEDDING,
                   "--dims", str(DIMS)])


if __name__ == "__main__":
    sys.exit(main())
