"""
Recall@5 del retriever de Kerna sobre el dataset de denuncias públicas.

Cada caso se consulta con embed_consultas() (Voyage, input_type "query", en lotes según
los límites de la cuenta) y se buscan los 5 fragmentos más cercanos en Qdrant/normativa_cl
con filtro vigente=true. Dos niveles:

  (a) ley: algún top-5 pertenece a la ley principal del caso (91 casos con ley_principal).
  (b) artículo: algún top-5 está en articulos_candidatos, normalizados a IDs de fragmento
      del corpus vigente (solo los casos con al menos un candidato mapeable).

Los 22 casos "ninguna" no tienen respuesta correcta: se reporta su score top-1 y la tasa
de falsos positivos para varios umbrales, junto a la fracción de casos positivos que
pasaría el mismo umbral.

Uso (desde kerna/):
  set -a; . pipeline_bcn/.env; set +a
  pipeline_bcn/.venv/bin/python evaluacion/recall_retriever.py [--campo texto_original|resumen_parafraseado]

Los vectores de las consultas se guardan en evaluacion/datos/embeddings_consultas.json (excluido
de git, como el dataset) para no volver a pagar la API al repetir la medición.

Cada medición se agrega a evaluacion/registro/recall_retriever.jsonl (versionado): fecha, commit,
parámetros, hash del dataset y resultados por ley y por caso (IDs, sin textos). Es la evidencia
de los KPIs del retriever.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "pipeline_bcn"))
import embed_sync  # noqa: E402

DATASET = AQUI / "datos" / "denuncias_publicas.json"
CACHE = AQUI / "datos" / "embeddings_consultas.json"
REGISTRO = AQUI / "registro" / "recall_retriever.jsonl"
TOP_K = 5
META = 0.8
UMBRALES = [round(0.15 + 0.05 * i, 2) for i in range(9)]

# ley_principal del dataset -> id_norma del corpus que la cubren.
LEYES = {
    "20.393": {1008668},
    "21.643": {1200096, 207436},          # la ley y los artículos del CT que modificó
    "19.628-21.719": {141599, 1209272},   # texto reformado de la 19.628 y la 21.719
}

# Cuerpo citado en articulos_candidatos -> prefijo de los IDs de fragmento vigentes.
PREFIJOS = {
    "CT": "207436-karin",
    "20.393": "1008668",
    "21.643": "1200096",
    "19.628": "141599-2026-12-01",
    "21.719": "1209272",
}

_SUFIJOS = "bis|ter|quater|quinquies|sexies|septies|octies|nonies"
_NUM = rf"(\d+)(?:\s*-\s*([A-Ea-e])(?!\w))?(?:\s+({_SUFIJOS})\b)?"
_REF = re.compile(rf"{_NUM}(?:\s*(?:\ba\b|-)\s*{_NUM})?")
_CUERPO = re.compile(r"\b(?:Ley\s+(\d{1,2}\.\d{3})|(CT|CP|CPP|DS|DFL|Constituci[oó]n|Reglamento))\b")


def _art_id(prefijo: str, num: str, letra: str | None, sufijo: str | None) -> str:
    return f"{prefijo}-art-{num}" + (f"-{letra.lower()}" if letra else "") + (f"-{sufijo}" if sufijo else "")


def _expandir(prefijo: str, m: re.Match) -> list[str]:
    n1, l1, s1, n2, l2, s2 = m.groups()
    if not n2:
        return [_art_id(prefijo, n1, l1, s1)]
    if n1 == n2 and l1 and l2:              # 211-A a 211-C
        return [_art_id(prefijo, n1, chr(c), None) for c in range(ord(l1.upper()), ord(l2.upper()) + 1)]
    a, b = int(n1), int(n2)
    if not (l1 or l2 or s1 or s2) and 0 < b - a <= 20:   # 17-19
        return [_art_id(prefijo, str(n), None, None) for n in range(a, b + 1)]
    return [_art_id(prefijo, n1, l1, s1), _art_id(prefijo, n2, l2, s2)]


def citas_a_articulos(texto: str) -> list[str]:
    """IDs de artículo (sin -pN) que nombra articulos_candidatos, para los cuerpos del corpus.

    Una ley sin "art." (p. ej. "Ley 21.719 (seguridad)") no aporta artículos. Los IDs que no
    existan en el corpus se descartan después, en normalizar_candidatos().
    """
    t = texto
    while re.search(r"\([^()]*\)", t):
        t = re.sub(r"\([^()]*\)", " ", t)       # comentarios del agente
    t = re.sub(r"Reglamento\s+(?:de\s+la\s+)?Ley", "Reglamento", t)
    t = re.sub(r"\binc\.\s*\d+", " ", t)         # incisos
    t = re.sub(r"N°\s*\d+", " ", t)              # numerales
    t = re.sub(r"\b[a-zñ]\)", " ", t)            # letras: a), g)
    cuerpos = list(_CUERPO.finditer(t))
    ids = []
    for i, c in enumerate(cuerpos):
        fin = cuerpos[i + 1].start() if i + 1 < len(cuerpos) else len(t)
        tramo = t[c.end():fin].split(";")[0]
        clave = c.group(1) or c.group(2)
        prefijo = PREFIJOS.get(clave)
        if not prefijo:
            continue
        if c.group(1):                          # "Ley N" solo cita artículos con "art."
            m = re.match(r"\s*arts?\.", tramo)
            if not m:
                continue
            tramo = tramo[m.end():]
        for m in _REF.finditer(tramo):
            ids += _expandir(prefijo, m)
    return list(dict.fromkeys(ids))


def articulo_de(fragmento_id: str) -> str:
    return re.sub(r"-p\d+$", "", fragmento_id)


def normalizar_candidatos(texto: str, articulos_corpus: set[str]) -> tuple[set[str], list[str]]:
    """(IDs de artículo presentes en el corpus vigente, IDs citados que no están en él)."""
    citados = citas_a_articulos(texto)
    return ({a for a in citados if a in articulos_corpus},
            [a for a in citados if a not in articulos_corpus])


# ---------------------------------------------------------------- Qdrant
_FILTRO_VIGENTE = {"must": [{"key": "vigente", "match": {"value": True}}]}


def articulos_vigentes() -> set[str]:
    col = embed_sync.COLECCION
    arts, offset = set(), None
    while True:
        body = {"filter": _FILTRO_VIGENTE, "limit": 256, "with_payload": ["fragmento_id"],
                "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        out = embed_sync.qdrant(f"/collections/{col}/points/scroll", body, method="POST")["result"]
        arts |= {articulo_de(p["payload"]["fragmento_id"]) for p in out["points"]}
        offset = out.get("next_page_offset")
        if offset is None:
            return arts


def buscar(vectores: list[list[float]], k: int = TOP_K, lote: int = 32) -> list[list[dict]]:
    """Top-k vigente por consulta: [{"fragmento_id", "id_norma", "score"}, ...]."""
    col = embed_sync.COLECCION
    resultados = []
    for i in range(0, len(vectores), lote):
        busquedas = [{"vector": v, "limit": k, "filter": _FILTRO_VIGENTE,
                      "with_payload": ["fragmento_id", "id_norma"]} for v in vectores[i:i + lote]]
        out = embed_sync.qdrant(f"/collections/{col}/points/search/batch",
                                {"searches": busquedas}, method="POST")["result"]
        resultados += [[{"fragmento_id": p["payload"]["fragmento_id"],
                         "id_norma": p["payload"]["id_norma"], "score": p["score"]} for p in r]
                       for r in out]
    return resultados


# ---------------------------------------------------------------- consultas
def texto_consulta(caso: dict, campo: str) -> str:
    return re.sub(r"^\[Resumen parafraseado\]\s*", "", caso[campo].strip())


def _clave(texto: str) -> str:
    return hashlib.sha256(f"{embed_sync.VOYAGE_MODELO}|{embed_sync.DIMS}|query|{texto}".encode()).hexdigest()


def embeber(textos: list[str], cache_path: Path = CACHE) -> list[list[float]]:
    """Vectores de consulta, reutilizando los ya calculados; los faltantes van en lotes."""
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    faltan = list(dict.fromkeys(t for t in textos if _clave(t) not in cache))
    if faltan:
        print(f"Embebiendo {len(faltan)} consultas con {embed_sync.VOYAGE_MODELO}...", flush=True)
        vectores = embed_sync.embed_consultas(faltan)
        if len(vectores) != len(faltan) or any(len(v) != embed_sync.DIMS for v in vectores):
            raise RuntimeError("Voyage devolvió un número o tamaño de vectores inesperado")
        cache.update({_clave(t): v for t, v in zip(faltan, vectores)})
        cache_path.write_text(json.dumps(cache))
    return [cache[_clave(t)] for t in textos]


# ---------------------------------------------------------------- métricas
def evaluar(casos: list[dict], tops: list[list[dict]], articulos_corpus: set[str]) -> dict:
    por_ley = defaultdict(lambda: {"n": 0, "ley": 0, "n_art": 0, "art": 0})
    ninguna, top1_pos, detalle = [], [], []
    for caso, top in zip(casos, tops):
        ley = caso["ley_principal"]
        top1 = top[0]["score"] if top else 0.0
        if ley == "ninguna":
            ninguna.append(top1)
            detalle.append({"id": caso["id"], "ley": ley, "top1": top1,
                            "top": [t["fragmento_id"] for t in top]})
            continue
        if ley not in LEYES:
            raise ValueError(f"{caso['id']}: ley_principal desconocida {ley!r}")
        top1_pos.append(top1)
        candidatos, _ = normalizar_candidatos(caso["articulos_candidatos"], articulos_corpus)
        acierto_ley = any(t["id_norma"] in LEYES[ley] for t in top)
        acierto_art = any(articulo_de(t["fragmento_id"]) in candidatos for t in top) if candidatos else None
        for g in (ley, "global"):
            r = por_ley[g]
            r["n"] += 1
            r["ley"] += acierto_ley
            if candidatos:
                r["n_art"] += 1
                r["art"] += acierto_art
        detalle.append({"id": caso["id"], "ley": ley, "top1": top1, "acierto_ley": acierto_ley,
                        "acierto_articulo": acierto_art, "candidatos": sorted(candidatos),
                        "top": [t["fragmento_id"] for t in top]})
    resumen = {g: {"casos": r["n"], "recall_ley": r["ley"] / r["n"] if r["n"] else None,
                   "casos_articulo": r["n_art"],
                   "recall_articulo": r["art"] / r["n_art"] if r["n_art"] else None}
               for g, r in por_ley.items()}
    umbrales = [{"umbral": u,
                 "falsos_positivos": sum(s >= u for s in ninguna) / len(ninguna) if ninguna else None,
                 "positivos_que_pasan": sum(s >= u for s in top1_pos) / len(top1_pos) if top1_pos else None}
                for u in UMBRALES]
    return {"por_ley": resumen, "ninguna": {"casos": len(ninguna), "top1": sorted(ninguna),
                                             "umbrales": umbrales},
            "detalle": detalle}


def _pct(x):
    return "  —  " if x is None else f"{x:5.3f}"


def imprimir(res: dict, campo: str):
    print(f"\nRecall@{TOP_K} — consulta = {campo} (meta ≥ {META})")
    print(f"{'ley':<15}{'casos':>6}{'(a) ley':>9}{'casos art':>11}{'(b) art':>9}")
    orden = sorted(k for k in res["por_ley"] if k != "global") + ["global"]
    for g in orden:
        r = res["por_ley"][g]
        print(f"{g:<15}{r['casos']:>6}{_pct(r['recall_ley']):>9}{r['casos_articulo']:>11}"
              f"{_pct(r['recall_articulo']):>9}")
    n = res["ninguna"]
    print(f"\nCasos 'ninguna' ({n['casos']}): score top-1 de {_pct(min(n['top1'], default=None))}"
          f" a {_pct(max(n['top1'], default=None))}")
    print(f"{'umbral':>7}{'FP ninguna':>12}{'positivos ≥':>13}")
    for u in n["umbrales"]:
        print(f"{u['umbral']:>7.2f}{_pct(u['falsos_positivos']):>12}{_pct(u['positivos_que_pasan']):>13}")


def _commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=AQUI, capture_output=True,
                             text=True, check=True).stdout.strip()
        sucio = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=AQUI.parent,
                               capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("+cambios" if sucio else "")
    except (OSError, subprocess.CalledProcessError):
        return "desconocido"


def registrar(res: dict, *, campo: str, dataset: bytes, articulos_corpus: int, casos: int,
              duracion_s: float, registro: Path = REGISTRO) -> dict:
    """Agrega la medición al registro JSONL y la devuelve."""
    entrada = {
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _commit(),
        "medicion": f"recall@{TOP_K}",
        "parametros": {"campo_consulta": campo, "modelo": embed_sync.VOYAGE_MODELO,
                       "dims": embed_sync.DIMS, "input_type": "query", "top_k": TOP_K,
                       "coleccion": embed_sync.COLECCION, "filtro": "vigente=true", "meta": META},
        "dataset": {"sha256": hashlib.sha256(dataset).hexdigest(), "casos": casos},
        "corpus_articulos_vigentes": articulos_corpus,
        "duracion_s": round(duracion_s, 1),
        "por_ley": res["por_ley"],
        "ninguna": {"casos": res["ninguna"]["casos"], "top1_min": min(res["ninguna"]["top1"], default=None),
                    "top1_max": max(res["ninguna"]["top1"], default=None),
                    "umbrales": res["ninguna"]["umbrales"]},
        "detalle": res["detalle"],
    }
    registro.parent.mkdir(exist_ok=True)
    with registro.open("a") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    return entrada


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--campo", default="texto_original", choices=["texto_original", "resumen_parafraseado"])
    ap.add_argument("--solo-mapeo", action="store_true",
                    help="solo cuenta los casos con artículos mapeables (sin Voyage)")
    args = ap.parse_args(argv)

    inicio = time.monotonic()
    crudo = DATASET.read_bytes()
    casos = json.loads(crudo)["casos"]
    articulos_corpus = articulos_vigentes()
    positivos = [c for c in casos if c["ley_principal"] != "ninguna"]
    mapeables = defaultdict(int)
    for c in positivos:
        if normalizar_candidatos(c["articulos_candidatos"], articulos_corpus)[0]:
            mapeables[c["ley_principal"]] += 1
    print(f"Corpus vigente: {len(articulos_corpus)} artículos. Casos con ley_principal: {len(positivos)}; "
          f"con artículos candidatos mapeables: {sum(mapeables.values())} ({dict(sorted(mapeables.items()))})")
    if args.solo_mapeo:
        return 0

    tops = buscar(embeber([texto_consulta(c, args.campo) for c in casos]))
    res = evaluar(casos, tops, articulos_corpus)
    imprimir(res, args.campo)
    salida = AQUI / "datos" / f"resultado_recall_{args.campo}.json"
    salida.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    registrar(res, campo=args.campo, dataset=crudo, articulos_corpus=len(articulos_corpus),
              casos=len(casos), duracion_s=time.monotonic() - inicio)
    print(f"\nDetalle por caso: {salida.relative_to(AQUI.parent)}; registrado en {REGISTRO.relative_to(AQUI.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
