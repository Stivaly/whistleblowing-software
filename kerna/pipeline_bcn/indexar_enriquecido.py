"""Construye las colecciones de Qdrant del experimento de enriquecimiento (KERNA_ENRIQUECIDO) sin tocar `normativa_cl`.

A partir de los payloads vigentes de `normativa_cl` y de `enriquecimiento_articulos.json` crea, con voyage-4-large:
  <base>_p      partición por literal de los artículos-lista, sin enriquecimiento en el vector
  <base>_e      sin partición, con el enriquecimiento concatenado al texto del vector
  <base>_pe     partición + enriquecimiento concatenado
  <base>_eonly  (ids de _pe) vector del encabezado + enriquecimiento solo: lista densa «aparte» (KERNA_ENR_COLECCION_APARTE)
Todos los payloads llevan `articulo_id`, `rol`, `enriquecimiento` y, en los literales, `literal` (el texto legal de
`texto` no cambia salvo que en los literales es introducción + literal). Los ids de los literales son `<artículo>-pN`.

Uso: operaciones/indexar_enriquecido.sh [--base normativa_cl_x] [--modos p,e,pe,eonly] [--fragmentos JSON]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import embed_sync as es  # noqa: E402
from fragmentar_literales import partir_literales  # noqa: E402

_qdrant_original = es.qdrant


def _qdrant(ruta: str, cuerpo: dict | None = None, method: str = "PUT", intentos: int = 6) -> dict:
    """embed_sync.qdrant con reintentos: el DNS del servidor falla de forma transitoria."""
    for i in range(intentos):
        try:
            return _qdrant_original(ruta, cuerpo, method=method)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, OSError):
            if i == intentos - 1:
                raise
            time.sleep(5 * (i + 1))


es.qdrant = _qdrant      # asegurar_coleccion y los upserts usan la versión con reintentos
ENRIQUECIMIENTO = AQUI / "enriquecimiento_articulos.json"
MODOS = ("p", "e", "pe", "eonly")


def encabezado(f: dict, marca: str = "") -> str:
    return f"{f['tipo_numero']} — {f['norma']}. {' > '.join(f['jerarquia'])}{marca}. "


def construir(fragmentos: list[dict], enr: dict, modo: str) -> list[dict]:
    """-> [{frag_id, texto_embedding, payload}] para el modo (p | e | pe | eonly)."""
    partir = modo in ("p", "pe", "eonly")
    en_vector = modo in ("e", "pe", "eonly")
    solo_enr = modo == "eonly"
    por: dict[str, list[dict]] = {}
    for f in fragmentos:
        por.setdefault(re.sub(r"-p\d+$", "", f["fragmento_id"]), []).append(f)
    out = []
    for aid, fr in sorted(por.items()):
        e = enr.get(aid) or {}
        art_hechos = "; ".join(e.get("hechos", []))
        extra = {"articulo_id": aid, "rol": e.get("rol", ""), "enriquecimiento": art_hechos}
        intro, lits = partir_literales(fr[0]["texto"]) if len(fr) == 1 and partir else ("", [])
        if lits:
            f = fr[0]
            for n, (letra, texto) in enumerate(lits, 1):
                hechos = "; ".join((e.get("literales") or {}).get(letra, [])) or art_hechos
                cuerpo = f"{intro}\n\n{texto}"
                base = encabezado(f, f" > literal {letra}") + cuerpo
                out.append({"frag_id": f"{aid}-p{n}",
                            "texto_embedding": (encabezado(f, f" > literal {letra}") + "Situaciones típicas: " + hechos)
                            if solo_enr else base + (f"\nSituaciones típicas: {hechos}" if en_vector else ""),
                            "payload": {**f, **extra, "fragmento_id": f"{aid}-p{n}", "texto": cuerpo, "parte": f"{n}/{len(lits)}",
                                        "literal": letra, "enriquecimiento": hechos}})
            continue
        for f in fr:
            marca = f" (parte {f['parte'].replace('/', '/')})" if f.get("parte") else ""
            base = encabezado(f, marca) + f["texto"]
            out.append({"frag_id": f["fragmento_id"],
                        "texto_embedding": (encabezado(f, marca) + "Situaciones típicas: " + art_hechos)
                        if solo_enr else base + (f"\nSituaciones típicas: {art_hechos}" if en_vector else ""),
                        "payload": {**f, **extra}})
    return out


def indexar(base: str, modo: str, docs: list[dict], meta: dict | None, dims: int = es.DIMS) -> int:
    nombre = f"{base}_{modo}"
    try:
        es.qdrant(f"/collections/{nombre}", method="DELETE")      # colección propia del experimento: se recrea
    except Exception:  # noqa: BLE001
        pass
    es.asegurar_coleccion(nombre, dims)
    vectores = es.embed_voyage([d["texto_embedding"] for d in docs], "document")
    for i in range(0, len(docs), 64):
        es.qdrant(f"/collections/{nombre}/points?wait=true", {"points": [
            {"id": es.punto_id(d["frag_id"]), "vector": v, "payload": d["payload"]}
            for d, v in zip(docs[i:i + 64], vectores[i:i + 64])]})
    if meta:
        es.qdrant(f"/collections/{nombre}/points?wait=true", {"points": [
            {"id": es.PUNTO_META_ID, "vector": [1.0] + [0.0] * (dims - 1), "payload": meta}]})
    print(f"[{nombre}] {len(docs)} fragmentos", flush=True)
    return len(docs)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="normativa_cl_x")
    ap.add_argument("--modos", default=",".join(MODOS))
    ap.add_argument("--fragmentos", required=True, help="JSON con los payloads vigentes de normativa_cl")
    a = ap.parse_args(argv)
    fragmentos = json.loads(Path(a.fragmentos).read_text())
    enr = json.loads(ENRIQUECIMIENTO.read_text())["articulos"]
    r = es.qdrant(f"/collections/{es.COLECCION}/points", {"ids": [es.PUNTO_META_ID], "with_payload": True}, "POST")
    meta = ((r or {}).get("result") or [{}])[0].get("payload")
    for modo in a.modos.split(","):
        if modo not in MODOS:
            raise SystemExit(f"modo desconocido: {modo}")
        indexar(a.base, modo, construir(fragmentos, enr, modo), meta)


if __name__ == "__main__":
    main()
