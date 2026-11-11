"""
Evaluación del retriever de Kerna (recall@5 y métricas secundarias) sobre el dataset de denuncias públicas.

Sirve para cualquier colección y modelo de embeddings. Cada caso se consulta con el modelo de consulta
(`--modelo-consulta`, por defecto el mismo del corpus; distinto para la configuración asimétrica) y se buscan
los 10 fragmentos más cercanos en la colección con filtro vigente=true. Dos niveles:

  (a) ley: algún top-5 pertenece a la ley principal del caso (91 casos con ley_principal).
  (b) artículo: algún top-5 está en articulos_candidatos, normalizados a IDs de fragmento
      del corpus vigente (solo los casos con al menos un candidato mapeable). Es el nivel de la meta 0,80.

Métricas por artículo, por ley y global: recall@5 (con IC bootstrap 95 %, semilla fija, 2.000 remuestreos),
nDCG@10, MRR, Precision@5, Hit rate@5 y cobertura@5; además P95 de la vectorización de una consulta (ms),
tokens de las consultas y costo estimado (precios_embeddings.json). Los candidatos de este dataset son
alternativas aceptables (basta uno), por lo que recall@5 y hit rate@5 coinciden; la cobertura@5 mide qué
fracción de los candidatos aparece.

Mapeo de candidatos (`--mapeo`): `concordancia` (por defecto) traduce los artículos de la Ley 19.628 citados con la
numeración previa a la Ley 21.719 a los del texto reformado que trae el corpus; `directo` usa el número citado tal
cual (la definición anterior, para comparar). Además de recall@5 se guardan hit y cobertura a 8 y 10 resultados.

Los 22 casos "ninguna" no tienen respuesta correcta: se reporta su score top-1 y la tasa
de falsos positivos para varios umbrales.

Uso (desde kerna/):
  set -a; . pipeline_bcn/.env; set +a
  pipeline_bcn/.venv/bin/python evaluacion/recall_retriever.py [--campo texto_original|resumen_parafraseado]
  ... --coleccion normativa_cl_eval_voyage-law-2 --proveedor voyage --modelo voyage-law-2
  ... --coleccion normativa_cl --modelo-consulta voyage-4-lite                  # asimétrica
  ... --coleccion normativa_cl_eval_bge-m3 --vectores-consulta qdrant:normativa_cl_eval_bge-m3_consultas
  ... --vectores-consulta consultas.json    # {"consultas": {sha256("query|"+texto): {"vector","ms","tokens"}}}

Los vectores de las consultas se guardan en evaluacion/datos/embeddings_consultas.json (voyage-4-large) o en
embeddings_consultas_<proveedor>_<modelo>.json (excluidos de git, como el dataset) para no volver a pagar la API.

Cada medición se agrega a evaluacion/registro/recall_retriever.jsonl (versionado): fecha, commit, comando,
parámetros, hash del dataset y resultados por ley y por caso (IDs, sin textos). comparar_embeddings.py lee ese
registro.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import subprocess
import sys
import time
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "pipeline_bcn"))
import embed_sync  # noqa: E402

DATASET = AQUI / "datos" / "denuncias_publicas.json"
CACHE = AQUI / "datos" / "embeddings_consultas.json"
REGISTRO = AQUI / "registro" / "recall_retriever.jsonl"
LATENCIAS = AQUI / "datos" / "latencias_consultas.json"
PRECIOS = AQUI / "precios_embeddings.json"
TOP_K = 5
TOP_BUSQUEDA = 10          # nDCG@10 y MRR miran hasta 10 resultados
TOP_NUCLEO = 8             # el núcleo entrega los 8 primeros al modelo
SEMILLA = 20261110
REMUESTREOS = 2000
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

# El dataset cita la Ley 19.628 con la numeración del texto previo a la Ley 21.719 (2023-05-09, vigente=false en
# el corpus), pero el corpus vigente trae el texto reformado (2026-12-01), donde la mayoría de esos números son
# otros artículos (p. ej. el 10 era "datos sensibles" y hoy es "forma de ejercer los derechos"; los datos
# sensibles pasaron al 16). Concordancia por título de artículo (verificada leyendo ambos textos): número del texto
# previo -> artículos del texto reformado que tratan la misma materia. Los no listados (2, 17, 18, 19) coinciden.
CONCORDANCIA_19628 = {
    "4": ["12", "13"],          # tratamiento solo con ley o consentimiento -> licitud del tratamiento
    "6": ["6", "7"],            # eliminar o cancelar datos / modificar erróneos -> rectificación y supresión
    "7": ["14-bis"],            # deber de secreto
    "9": ["3"],                 # finalidad -> principios
    "10": ["16"],               # datos sensibles
    "11": ["14-quinquies"],     # seguridad y cuidado de los datos
    "12": ["4", "5", "6", "7"],  # derechos de acceso, rectificación y cancelación -> derechos del titular
}
PREFIJO_19628 = PREFIJOS["19.628"]
MAPEOS = ("concordancia", "directo")

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


def aplicar_concordancia(ids: list[str]) -> list[str]:
    """Cambia los artículos de la Ley 19.628 citados con la numeración previa por sus equivalentes del texto
    reformado (CONCORDANCIA_19628); el resto queda igual."""
    out = []
    for a in ids:
        pref, _, resto = a.partition("-art-")
        if pref == PREFIJO_19628 and resto in CONCORDANCIA_19628:
            out += [f"{pref}-art-{n}" for n in CONCORDANCIA_19628[resto]]
        else:
            out.append(a)
    return list(dict.fromkeys(out))


def normalizar_candidatos(texto: str, articulos_corpus: set[str],
                          mapeo: str = "concordancia") -> tuple[set[str], list[str]]:
    """(IDs de artículo presentes en el corpus vigente, IDs citados que no están en él).

    mapeo "concordancia" (por defecto) traduce la numeración previa de la Ley 19.628 al texto reformado que trae
    el corpus; "directo" usa el número citado tal cual (la definición anterior, para comparar)."""
    if mapeo not in MAPEOS:
        raise ValueError(f"mapeo desconocido: {mapeo!r}")
    citados = citas_a_articulos(texto)
    if mapeo == "concordancia":
        citados = aplicar_concordancia(citados)
    return ({a for a in citados if a in articulos_corpus},
            [a for a in citados if a not in articulos_corpus])


# ---------------------------------------------------------------- Qdrant
def qdrant(ruta: str, cuerpo: dict | None = None, method: str = "PUT", intentos: int = 6) -> dict:
    """embed_sync.qdrant con reintentos: el DNS del servidor falla de forma transitoria."""
    for i in range(intentos):
        try:
            return embed_sync.qdrant(ruta, cuerpo, method=method)
        except urllib.error.HTTPError:
            raise
        except OSError:               # URLError, socket.gaierror, timeout
            if i == intentos - 1:
                raise
            time.sleep(5 * (i + 1))


_FILTRO_VIGENTE = {"must": [{"key": "vigente", "match": {"value": True}}]}


def articulos_vigentes(coleccion: str | None = None) -> set[str]:
    col = coleccion or embed_sync.COLECCION
    arts, offset = set(), None
    while True:
        body = {"filter": _FILTRO_VIGENTE, "limit": 256, "with_payload": ["fragmento_id"],
                "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        out = qdrant(f"/collections/{col}/points/scroll", body, method="POST")["result"]
        arts |= {articulo_de(p["payload"]["fragmento_id"]) for p in out["points"]}
        offset = out.get("next_page_offset")
        if offset is None:
            return arts


def buscar(vectores: list[list[float]], k: int = TOP_BUSQUEDA, lote: int = 32,
           coleccion: str | None = None) -> list[list[dict]]:
    """Top-k vigente por consulta: [{"fragmento_id", "id_norma", "score"}, ...]."""
    col = coleccion or embed_sync.COLECCION
    resultados = []
    for i in range(0, len(vectores), lote):
        busquedas = [{"vector": v, "limit": k, "filter": _FILTRO_VIGENTE,
                      "with_payload": ["fragmento_id", "id_norma"]} for v in vectores[i:i + lote]]
        out = qdrant(f"/collections/{col}/points/search/batch",
                                {"searches": busquedas}, method="POST")["result"]
        resultados += [[{"fragmento_id": p["payload"]["fragmento_id"],
                         "id_norma": p["payload"]["id_norma"], "score": p["score"]} for p in r]
                       for r in out]
    return resultados


# ---------------------------------------------------------------- consultas
def texto_consulta(caso: dict, campo: str) -> str:
    return re.sub(r"^\[Resumen parafraseado\]\s*", "", caso[campo].strip())


def _clave(texto: str, modelo: str = embed_sync.VOYAGE_MODELO, dims: int = embed_sync.DIMS) -> str:
    # Para voyage-4-large/1024 es la clave del cache original (no se invalida).
    return hashlib.sha256(f"{modelo}|{dims}|query|{texto}".encode()).hexdigest()


def clave_texto(texto: str) -> str:
    """Clave de un vector de consulta precalculado (independiente del modelo): job_embeddings/evaluar.py
    usa la misma."""
    return hashlib.sha256(f"query|{texto}".encode()).hexdigest()


def ruta_cache(proveedor: str, modelo: str) -> Path:
    if (proveedor, modelo) == ("voyage", embed_sync.VOYAGE_MODELO):
        return CACHE
    return AQUI / "datos" / f"embeddings_consultas_{proveedor}_{re.sub(r'[^A-Za-z0-9._-]', '-', modelo)}.json"


def embeber(textos: list[str], cache_path: Path = CACHE, embedder=None,
            modelo: str = embed_sync.VOYAGE_MODELO, dims: int = embed_sync.DIMS) -> list[list[float]]:
    """Vectores de consulta, reutilizando los ya calculados; los faltantes van en lotes."""
    embedder = embedder or embed_sync.embed_consultas
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    faltan = list(dict.fromkeys(t for t in textos if _clave(t, modelo, dims) not in cache))
    if faltan:
        print(f"Embebiendo {len(faltan)} consultas con {modelo}...", flush=True)
        vectores = embedder(faltan)
        if len(vectores) != len(faltan) or any(len(v) != dims for v in vectores):
            raise RuntimeError(f"{modelo} devolvió un número o tamaño de vectores inesperado")
        cache.update({_clave(t, modelo, dims): v for t, v in zip(faltan, vectores)})
        cache_path.parent.mkdir(exist_ok=True)
        cache_path.write_text(json.dumps(cache))
    return [cache[_clave(t, modelo, dims)] for t in textos]


def cargar_vectores_externos(ref: str, textos: list[str]) -> tuple[list[list[float]], list[float], list]:
    """Vectores de consulta precalculados (modelos abiertos calculados en Azure).

    ref: archivo JSON {"consultas": {clave_texto: {"vector", "ms", "tokens"}}} o "qdrant:<coleccion>"
    (puntos con payload {clave, ms, tokens}). -> (vectores, ms por consulta, tokens por consulta)."""
    if ref.startswith("qdrant:"):
        col, consultas, offset = ref[len("qdrant:"):], {}, None
        while True:
            body = {"limit": 128, "with_payload": True, "with_vector": True}
            if offset is not None:
                body["offset"] = offset
            out = qdrant(f"/collections/{col}/points/scroll", body, method="POST")["result"]
            for p in out["points"]:
                pl = p["payload"]
                consultas[pl["clave"]] = {"vector": p["vector"], "ms": pl.get("ms"), "tokens": pl.get("tokens")}
            offset = out.get("next_page_offset")
            if offset is None:
                break
    else:
        consultas = json.loads(Path(ref).read_text())["consultas"]
    faltan = [t for t in textos if clave_texto(t) not in consultas]
    if faltan:
        raise RuntimeError(f"{len(faltan)} consultas sin vector precalculado en {ref}")
    filas = [consultas[clave_texto(t)] for t in textos]
    return [f["vector"] for f in filas], [f.get("ms") for f in filas], [f.get("tokens") for f in filas]


# ---------------------------------------------------------------- métricas
def bootstrap_ic(valores: list[float], n: int = REMUESTREOS, semilla: int = SEMILLA,
                 confianza: float = 0.95) -> tuple[float, float] | None:
    """Intervalo de percentiles de la media (remuestreo de casos con reemplazo, semilla fija)."""
    if not valores:
        return None
    rng, m = random.Random(semilla), len(valores)
    medias = sorted(sum(valores[rng.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return medias[int((1 - confianza) / 2 * n)], medias[int((1 + confianza) / 2 * n) - 1]


def bootstrap_pareado(a: list[float], b: list[float], n: int = REMUESTREOS, semilla: int = SEMILLA,
                      confianza: float = 0.95) -> dict | None:
    """Diferencia media a - b sobre los mismos casos, con los mismos remuestreos para ambos."""
    if not a or len(a) != len(b):
        return None
    rng, m = random.Random(semilla), len(a)
    d = [x - y for x, y in zip(a, b)]
    medias = []
    for _ in range(n):
        medias.append(sum(d[rng.randrange(m)] for _ in range(m)) / m)
    medias.sort()
    return {"diferencia": sum(d) / m, "ic95": [medias[int((1 - confianza) / 2 * n)],
                                               medias[int((1 + confianza) / 2 * n) - 1]]}


def percentil(valores: list[float], p: float) -> float | None:
    """Percentil por rango más cercano (P95 = p 95)."""
    v = sorted(x for x in valores if x is not None)
    return v[max(0, math.ceil(p / 100 * len(v)) - 1)] if v else None


def metricas_caso(top: list[dict], candidatos: set[str]) -> dict:
    """Métricas de un caso con candidatos. Un artículo cuenta una vez (la primera parte que aparece)."""
    vistos, rel = set(), []
    for t in top[:TOP_BUSQUEDA]:
        a = articulo_de(t["fragmento_id"])
        rel.append(1 if a in candidatos and a not in vistos else 0)
        vistos.add(a)
    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rel))
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(candidatos), TOP_BUSQUEDA)))
    primero = next((i for i, r in enumerate(rel) if r), None)
    return {"recall5": float(any(rel[:TOP_K])), "hit5": float(any(rel[:TOP_K])),
            "cobertura5": sum(rel[:TOP_K]) / len(candidatos), "p5": sum(rel[:TOP_K]) / TOP_K,
            "ndcg10": dcg / idcg if idcg else 0.0, "mrr": 1 / (primero + 1) if primero is not None else 0.0,
            # Con más resultados (el núcleo usa 8) y recall verdadero (fracción de candidatos hallados):
            "hit8": float(any(rel[:TOP_NUCLEO])), "hit10": float(any(rel[:TOP_BUSQUEDA])),
            "cobertura8": sum(rel[:TOP_NUCLEO]) / len(candidatos),
            "cobertura10": sum(rel[:TOP_BUSQUEDA]) / len(candidatos)}


METRICAS = ("recall5", "hit5", "cobertura5", "p5", "ndcg10", "mrr", "hit8", "hit10", "cobertura8", "cobertura10")


def evaluar(casos: list[dict], tops: list[list[dict]], articulos_corpus: set[str],
            mapeo: str = "concordancia") -> dict:
    por_ley = defaultdict(lambda: {"n": 0, "ley": 0, "n_art": 0, "art": 0})
    valores = defaultdict(lambda: defaultdict(list))
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
        candidatos, _ = normalizar_candidatos(caso["articulos_candidatos"], articulos_corpus, mapeo)
        top5 = top[:TOP_K]
        acierto_ley = any(t["id_norma"] in LEYES[ley] for t in top5)
        acierto_art = any(articulo_de(t["fragmento_id"]) in candidatos for t in top5) if candidatos else None
        m = metricas_caso(top, candidatos) if candidatos else None
        for g in (ley, "global"):
            r = por_ley[g]
            r["n"] += 1
            r["ley"] += acierto_ley
            if candidatos:
                r["n_art"] += 1
                r["art"] += acierto_art
                for k in METRICAS:
                    valores[g][k].append(m[k])
        detalle.append({"id": caso["id"], "ley": ley, "top1": top1, "acierto_ley": acierto_ley,
                        "acierto_articulo": acierto_art, "candidatos": sorted(candidatos),
                        "metricas": m, "top": [t["fragmento_id"] for t in top]})
    resumen = {g: {"casos": r["n"], "recall_ley": r["ley"] / r["n"] if r["n"] else None,
                   "casos_articulo": r["n_art"],
                   "recall_articulo": r["art"] / r["n_art"] if r["n_art"] else None}
               for g, r in por_ley.items()}
    metricas = {}
    for g, vs in valores.items():
        metricas[g] = {k: sum(v) / len(v) for k, v in vs.items()}
        metricas[g]["recall5_ic95"] = list(bootstrap_ic(vs["recall5"]))
        metricas[g]["casos_articulo"] = len(vs["recall5"])
    umbrales = [{"umbral": u,
                 "falsos_positivos": sum(s >= u for s in ninguna) / len(ninguna) if ninguna else None,
                 "positivos_que_pasan": sum(s >= u for s in top1_pos) / len(top1_pos) if top1_pos else None}
                for u in UMBRALES]
    return {"por_ley": resumen, "metricas_articulo": metricas,
            "ninguna": {"casos": len(ninguna), "top1": sorted(ninguna), "umbrales": umbrales},
            "detalle": detalle}


def _pct(x):
    return "  —  " if x is None else f"{x:5.3f}"


def imprimir(res: dict, campo: str):
    print(f"\nRecall@{TOP_K} — consulta = {campo} (meta ≥ {META} por artículo)")
    print(f"{'ley':<15}{'casos':>6}{'(a) ley':>9}{'casos art':>11}{'(b) art':>9}{'IC 95 %':>16}{'nDCG@10':>9}{'MRR':>7}")
    orden = sorted(k for k in res["por_ley"] if k != "global") + ["global"]
    for g in orden:
        r = res["por_ley"][g]
        m = res.get("metricas_articulo", {}).get(g)
        ic = f"[{m['recall5_ic95'][0]:.3f},{m['recall5_ic95'][1]:.3f}]" if m else "—"
        print(f"{g:<15}{r['casos']:>6}{_pct(r['recall_ley']):>9}{r['casos_articulo']:>11}"
              f"{_pct(r['recall_articulo']):>9}{ic:>16}{_pct(m and m['ndcg10']):>9}{_pct(m and m['mrr']):>7}")
    n = res["ninguna"]
    print(f"\nCasos 'ninguna' ({n['casos']}): score top-1 de {_pct(min(n['top1'], default=None))}"
          f" a {_pct(max(n['top1'], default=None))}")
    print(f"{'umbral':>7}{'FP ninguna':>12}{'positivos ≥':>13}")
    for u in n["umbrales"]:
        print(f"{u['umbral']:>7.2f}{_pct(u['falsos_positivos']):>12}{_pct(u['positivos_que_pasan']):>13}")


# ---------------------------------------------------------------- latencia y costo
def estimar_tokens(textos: list[str]) -> int:
    return sum(len(t) // embed_sync.CHARS_POR_TOKEN + 1 for t in textos)


def medir_latencia(embedder, textos: list[str]) -> list[float]:
    """Latencia (ms) de vectorizar una consulta sola, sin las esperas por límites de la cuenta."""
    lat = []
    for t in textos:
        embed_sync.reiniciar_medicion()
        embedder([t])
        lat += embed_sync.MEDICION["latencias_ms"]
    return lat


def costo_estimado(proveedor: str, modelo: str, tokens: int, ms_total: float | None = None,
                   precios_path: Path = PRECIOS) -> dict:
    """Costo por tokens (modelos de API) o por tiempo de cómputo del job (modelos abiertos). null si se ignora el precio."""
    p = json.loads(precios_path.read_text()).get("modelos", {}).get(modelo, {})
    usd = None
    if p.get("usd_por_millon_tokens") is not None:
        usd = tokens / 1e6 * p["usd_por_millon_tokens"]
    elif p.get("computo_usd_por_hora") is not None and ms_total is not None:
        usd = ms_total / 3.6e6 * p["computo_usd_por_hora"]
    return {"usd": usd, "usd_por_millon_tokens": p.get("usd_por_millon_tokens"),
            "computo_usd_por_hora": p.get("computo_usd_por_hora"),
            "fuente": p.get("fuente"), "fecha_precio": p.get("fecha")}


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
              duracion_s: float, registro: Path = REGISTRO, parametros: dict | None = None,
              extra: dict | None = None, comando: str | None = None) -> dict:
    """Agrega la medición al registro JSONL y la devuelve."""
    entrada = {
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _commit(),
        "comando": comando,
        "medicion": f"recall@{TOP_K}",
        "parametros": {"campo_consulta": campo, "modelo": embed_sync.VOYAGE_MODELO,
                       "dims": embed_sync.DIMS, "input_type": "query", "top_k": TOP_K,
                       "coleccion": embed_sync.COLECCION, "filtro": "vigente=true", "meta": META,
                       **(parametros or {})},
        "dataset": {"sha256": hashlib.sha256(dataset).hexdigest(), "casos": casos},
        "corpus_articulos_vigentes": articulos_corpus,
        "duracion_s": round(duracion_s, 1),
        "por_ley": res["por_ley"],
        "metricas_articulo": res.get("metricas_articulo", {}),
        **(extra or {}),
        "ninguna": {"casos": res["ninguna"]["casos"], "top1_min": min(res["ninguna"]["top1"], default=None),
                    "top1_max": max(res["ninguna"]["top1"], default=None),
                    "umbrales": res["ninguna"]["umbrales"]},
        "detalle": res["detalle"],
    }
    registro.parent.mkdir(exist_ok=True)
    with registro.open("a") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    return entrada


def _config(args) -> dict:
    """Proveedor, modelo y dimensiones del corpus y de las consultas."""
    base = next((c for c in embed_sync.cargar_colecciones(solo_activas=False)
                 if c["nombre"] == args.coleccion), {})
    proveedor = args.proveedor or base.get("proveedor") or "voyage"
    modelo = args.modelo or base.get("modelo") or embed_sync.MODELOS[proveedor]
    dims = args.dims or base.get("dims") or embed_sync.DIMS
    return {"coleccion": args.coleccion, "proveedor": proveedor, "modelo": modelo, "dims": dims,
            "modelo_consulta": args.modelo_consulta or modelo}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--campo", default="texto_original", choices=["texto_original", "resumen_parafraseado"])
    ap.add_argument("--coleccion", default=embed_sync.COLECCION)
    ap.add_argument("--proveedor", choices=list(embed_sync.PROVEEDORES))
    ap.add_argument("--modelo", help="modelo del corpus (por defecto el de colecciones.json)")
    ap.add_argument("--modelo-consulta", help="modelo de las consultas si difiere del corpus (asimétrica)")
    ap.add_argument("--dims", type=int)
    ap.add_argument("--vectores-consulta", metavar="ARCHIVO|qdrant:COLECCION",
                    help="vectores de consulta precalculados (modelos abiertos calculados en Azure)")
    ap.add_argument("--muestra-latencia", type=int, default=20,
                    help="consultas sueltas para medir el P95 de la vectorización (0 = no medir)")
    ap.add_argument("--mapeo", choices=MAPEOS, default="concordancia",
                    help="candidatos de la Ley 19.628: 'concordancia' (numeración previa -> texto reformado del corpus) "
                         "o 'directo' (número citado tal cual; la definición anterior)")
    ap.add_argument("--solo-mapeo", action="store_true",
                    help="solo cuenta los casos con artículos mapeables (sin proveedor de embeddings)")
    args = ap.parse_args(argv)
    cfg = _config(args)

    inicio = time.monotonic()
    crudo = DATASET.read_bytes()
    casos = json.loads(crudo)["casos"]
    articulos_corpus = articulos_vigentes(cfg["coleccion"])
    positivos = [c for c in casos if c["ley_principal"] != "ninguna"]
    mapeables = defaultdict(int)
    for c in positivos:
        if normalizar_candidatos(c["articulos_candidatos"], articulos_corpus, args.mapeo)[0]:
            mapeables[c["ley_principal"]] += 1
    print(f"Corpus vigente: {len(articulos_corpus)} artículos. Casos con ley_principal: {len(positivos)}; "
          f"con artículos candidatos mapeables: {sum(mapeables.values())} ({dict(sorted(mapeables.items()))})")
    if args.solo_mapeo:
        return 0

    textos = [texto_consulta(c, args.campo) for c in casos]
    embed_sync.reiniciar_medicion()
    if args.vectores_consulta:
        vectores, ms, toks = cargar_vectores_externos(args.vectores_consulta, textos)
        lat = [m for m in ms if m is not None]
        tokens = sum(t for t in toks if t) or estimar_tokens(textos)
        origen_tokens = "medido" if any(toks) else "estimado"
        origen_lat = "job de Azure (una consulta por petición)"
    else:
        emb = embed_sync.crear_embedder(cfg["proveedor"], cfg["modelo_consulta"], cfg["dims"])
        embedder = None if (cfg["proveedor"], cfg["modelo_consulta"]) == ("voyage", embed_sync.VOYAGE_MODELO) \
            else (lambda t: emb(t, "query"))
        cache = ruta_cache(cfg["proveedor"], cfg["modelo_consulta"])
        vectores = embeber(textos, cache, embedder, cfg["modelo_consulta"], cfg["dims"])
        tokens_api = embed_sync.MEDICION["tokens"]
        tokens, origen_tokens = (tokens_api, "medido") if tokens_api else (estimar_tokens(textos), "estimado")
        lat, origen_lat = [], "sin medir"
        if args.muestra_latencia:
            guardadas = json.loads(LATENCIAS.read_text()) if LATENCIAS.exists() else {}
            clave = f"{cfg['proveedor']}|{cfg['modelo_consulta']}|{cfg['dims']}"
            lat = guardadas.get(clave, [])
            if len(lat) < args.muestra_latencia:
                emb_q = embedder or embed_sync.embed_consultas
                lat = medir_latencia(emb_q, textos[:args.muestra_latencia])
                guardadas[clave] = lat
                LATENCIAS.write_text(json.dumps(guardadas))
            origen_lat = f"{len(lat)} consultas sueltas"
    tops = buscar(vectores, coleccion=cfg["coleccion"])
    res = evaluar(casos, tops, articulos_corpus, args.mapeo)
    imprimir(res, args.campo)
    p95 = percentil(lat, 95)
    costo = costo_estimado(cfg["proveedor"], cfg["modelo_consulta"], tokens, sum(lat) if lat else None)
    print(f"\nP95 de la vectorización de una consulta: {p95 if p95 is None else round(p95)} ms ({origen_lat}); "
          f"tokens de las consultas: {tokens} ({origen_tokens}); costo estimado: {costo['usd']}")
    sufijo = "" if cfg["coleccion"] == embed_sync.COLECCION and cfg["modelo_consulta"] == cfg["modelo"] \
        else f"_{cfg['coleccion']}_{re.sub(r'[^A-Za-z0-9._-]', '-', cfg['modelo_consulta'])}"
    if args.mapeo != "concordancia":
        sufijo += f"_{args.mapeo}"
    salida = AQUI / "datos" / f"resultado_recall_{args.campo}{sufijo}.json"
    salida.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    registrar(res, campo=args.campo, dataset=crudo, articulos_corpus=len(articulos_corpus),
              casos=len(casos), duracion_s=time.monotonic() - inicio,
              parametros={"modelo": cfg["modelo"], "proveedor": cfg["proveedor"], "dims": cfg["dims"],
                          "coleccion": cfg["coleccion"], "modelo_consulta": cfg["modelo_consulta"],
                          "mapeo": args.mapeo, "vectores_consulta": args.vectores_consulta},
              extra={"latencia_consulta": {"p95_ms": p95, "muestras": len(lat), "origen": origen_lat},
                     "tokens_consultas": {"total": tokens, "origen": origen_tokens},
                     "costo_estimado": costo},
              comando="recall_retriever.py " + " ".join(argv if argv is not None else sys.argv[1:]))
    print(f"\nDetalle por caso: {salida.relative_to(AQUI.parent)}; registrado en {REGISTRO.relative_to(AQUI.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
