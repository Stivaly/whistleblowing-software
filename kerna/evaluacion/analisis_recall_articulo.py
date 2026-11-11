"""
Análisis de causa raíz del recall@5 por artículo (PR-01), sin llamar a ningún proveedor de embeddings.

Usa los vectores ya guardados (colecciones de Qdrant del corpus, cachés de consultas en datos/ y colecciones
`*_consultas` de los modelos abiertos) y busca por coseno en memoria con el mismo filtro vigente=true que el
retriever (se verifica contra el registro). Mide:

  1. existencia: cuántos artículos candidatos del dataset existen en el corpus vigente, por ley, y por qué faltan;
  2. mapeo: qué cambia entre el número citado tal cual (`directo`) y la concordancia de la Ley 19.628;
  3. especificidad: recall esperado por azar, candidatos por caso, largo de los fragmentos candidatos;
  4. qué recupera el top 5 cuando falla (artículo vecino, misma ley, otra ley) y qué fragmentos concentran el top 5;
  5. lectura de la métrica: "algún candidato" (hit) frente a cobertura, y k = 5, 8, 10;
  6. fragmentos no sustantivos (sin vector): ¿incluyen candidatos?;
  7. exploratorio sin re-vectorizar: BM25 léxico, fusión RRF con el vector y centrado de vectores.

Uso (desde kerna/):
  set -a; . pipeline_bcn/.env; set +a
  /usr/bin/python3 evaluacion/analisis_recall_articulo.py [--campo texto_original] [--salida datos/analisis_recall_articulo.json]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import recall_retriever as R  # noqa: E402
from recall_retriever import embed_sync  # noqa: E402

FRAGMENTOS = AQUI / "job_embeddings" / "datos" / "fragmentos.json"
NO_SUSTANTIVOS = AQUI / "datos" / "fragmentos_no_sustantivos.json"
CANDIDATOS = AQUI / "candidatos.json"
CLAVE_NUEVA_19628 = "141599@2026-12-01"
ALIAS = {"141599-2026-12-01": "L19628", "207436-karin": "CT", "1008668": "L20393", "1200096": "L21643",
         "1209272": "L21719"}


def corto(frag_id: str) -> str:
    for k, v in ALIAS.items():
        if frag_id.startswith(k):
            return v + frag_id[len(k):].replace("-art-", "#")
    return frag_id


# ---------------------------------------------------------------- datos
def _qdrant(ruta: str, cuerpo: dict, intentos: int = 6) -> dict:
    """embed_sync.qdrant con reintentos (el DNS del servidor falla de forma transitoria)."""
    for i in range(intentos):
        try:
            return embed_sync.qdrant(ruta, cuerpo, method="POST")
        except OSError:
            if i == intentos - 1:
                raise
            time.sleep(5 * (i + 1))


def cargar_puntos(coleccion: str) -> tuple[list[dict], np.ndarray]:
    pts, offset = [], None
    while True:
        body = {"limit": 128, "with_payload": True, "with_vector": True}
        if offset is not None:
            body["offset"] = offset
        out = _qdrant(f"/collections/{coleccion}/points/scroll", body)["result"]
        pts += out["points"]
        offset = out.get("next_page_offset")
        if offset is None:
            break
    pts = [p for p in pts if p["payload"].get("tipo") != "meta" and "fragmento_id" in p["payload"]]
    pts.sort(key=lambda p: p["payload"]["fragmento_id"])
    v = np.array([p["vector"] for p in pts], dtype=np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return [p["payload"] for p in pts], v


def vectores_consulta(cand: dict, textos: list[str]) -> np.ndarray:
    """Vectores de consulta ya guardados (nunca llama a un proveedor)."""
    if cand["proveedor"] == "local":
        v, _, _ = R.cargar_vectores_externos(f"qdrant:{cand['coleccion']}_consultas", textos)
    else:
        cache = json.loads(R.ruta_cache(cand["proveedor"], cand["modelo_consulta"]).read_text())
        faltan = [t for t in textos if R._clave(t, cand["modelo_consulta"], cand["dims"]) not in cache]
        if faltan:
            raise RuntimeError(f"{cand['id']}: {len(faltan)} consultas sin vector guardado")
        v = [cache[R._clave(t, cand["modelo_consulta"], cand["dims"])] for t in textos]
    q = np.array(v, dtype=np.float32)
    return q / np.linalg.norm(q, axis=1, keepdims=True)


# ---------------------------------------------------------------- búsqueda y métricas
def top_por_coseno(q: np.ndarray, v: np.ndarray, payloads: list[dict], k: int = 10) -> list[list[dict]]:
    vig = np.array([p.get("vigente") is True for p in payloads])
    sc = q @ v.T
    sc[:, ~vig] = -9
    tops = []
    for i in range(len(q)):
        o = np.argsort(-sc[i], kind="stable")[:k]
        tops.append([{"fragmento_id": payloads[j]["fragmento_id"], "id_norma": payloads[j]["id_norma"],
                      "score": float(sc[i, j])} for j in o])
    return tops


def metricas(casos, tops, arts, mapeo="concordancia") -> dict:
    res = R.evaluar(casos, tops, arts, mapeo)
    return {"global": res["metricas_articulo"]["global"], "por_ley": res["metricas_articulo"],
            "recall_ley": {k: v["recall_ley"] for k, v in res["por_ley"].items()}, "detalle": res["detalle"]}


def azar(n_corpus: int, n_cand: int, k: int = 5) -> float:
    """P(algún candidato entre k artículos distintos al azar)."""
    return 1 - math.comb(n_corpus - n_cand, k) / math.comb(n_corpus, k) if n_corpus - n_cand >= k else 1.0


# ---------------------------------------------------------------- BM25 (exploratorio)
_PARADAS = set("""de la el en y a los las del que se por con para un una al lo como su sus es o ser son sea este esta
estos estas esto ese esa eso mas pero sin sobre entre cuando donde quien cual cuyo cuya hay han fue era mi me le les
ya si no muy tambien porque hasta desde ha he habia tiene tienen tengo todo toda todos todas otro otra otros otras
mismo misma les nos ni asi cada cualquier""".split())


def tokens(texto: str) -> list[str]:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return [w[:6] for w in re.findall(r"[a-z0-9]{3,}", t) if w not in _PARADAS]


class BM25:
    def __init__(self, docs: list[str], k1=1.4, b=0.75):
        self.d = [Counter(tokens(t)) for t in docs]
        self.len = np.array([sum(c.values()) for c in self.d], dtype=float)
        self.avg = self.len.mean()
        df = Counter(w for c in self.d for w in c)
        n = len(docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.k1, self.b = k1, b

    def puntajes(self, consulta: str) -> np.ndarray:
        q = Counter(tokens(consulta))
        out = np.zeros(len(self.d))
        for w, qf in q.items():
            if w not in self.idf:
                continue
            for i, c in enumerate(self.d):
                f = c.get(w, 0)
                if f:
                    out[i] += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg)) \
                        * (1 + math.log(qf))
        return out


def tops_de_puntajes(sc: np.ndarray, payloads: list[dict], k: int = 10) -> list[list[dict]]:
    tops = []
    for fila in sc:
        o = np.argsort(-fila, kind="stable")[:k]
        tops.append([{"fragmento_id": payloads[j]["fragmento_id"], "id_norma": payloads[j]["id_norma"],
                      "score": float(fila[j])} for j in o])
    return tops


def rrf(*puntajes: np.ndarray, k: int = 60) -> np.ndarray:
    out = np.zeros_like(puntajes[0])
    for s in puntajes:
        rango = np.argsort(np.argsort(-s, axis=1, kind="stable"), axis=1)
        out += 1.0 / (k + rango + 1)
    return out


# ---------------------------------------------------------------- análisis
def existencia(casos, arts, no_sust_ids) -> dict:
    """Por ley: casos, casos con candidato citado, mapeable, y por qué faltan los demás."""
    out = {}
    for ley in ("20.393", "21.643", "19.628-21.719"):
        cs = [c for c in casos if c["ley_principal"] == ley]
        fila = {"casos": len(cs), "evaluables_directo": 0, "evaluables_concordancia": 0, "citas": 0,
                "citas_en_corpus": 0, "citas_distintas": set(), "en_corpus_distintas": set(),
                "sin_candidatos_por": Counter(), "citas_en_no_sustantivos": 0}
        for c in cs:
            texto = c["articulos_candidatos"]
            citados = R.aplicar_concordancia(R.citas_a_articulos(texto))
            dentro, fuera = R.normalizar_candidatos(texto, arts, "concordancia")
            dentro_d, _ = R.normalizar_candidatos(texto, arts, "directo")
            fila["evaluables_directo"] += bool(dentro_d)
            fila["evaluables_concordancia"] += bool(dentro)
            fila["citas"] += len(citados)
            fila["citas_en_corpus"] += len(dentro)
            fila["citas_distintas"] |= set(citados)
            fila["en_corpus_distintas"] |= dentro
            fila["citas_en_no_sustantivos"] += sum(1 for a in citados if a in no_sust_ids)
            if dentro:
                continue
            if citados:
                motivo = "cita artículos que el corpus no trae (p. ej. CT fuera de los modificados por la Ley Karin)"
            elif re.search(r"Ley\s+(20\.393|21\.643|19\.628|21\.719)(?!\d)", texto):
                motivo = "nombra la ley sin número de artículo"
            else:
                motivo = "solo cuerpos fuera del corpus (CP, Ley 19.913, Ley 19.496, Constitución, dictámenes…)"
            fila["sin_candidatos_por"][motivo] += 1
        fila["citas_distintas"] = len(fila["citas_distintas"])
        fila["en_corpus_distintas"] = len(fila["en_corpus_distintas"])
        fila["sin_candidatos_por"] = dict(fila["sin_candidatos_por"])
        out[ley] = fila
    return out


def mapeo_19628(casos, arts) -> dict:
    """Candidatos de la Ley 19.628: ¿tratan lo mismo con el número citado tal cual?"""
    iguales = {"2", "17", "18", "19"}
    pares_directo, cambian = 0, 0
    casos_afectados = 0
    for c in casos:
        if c["ley_principal"] != "19.628-21.719":
            continue
        cit = [a for a in R.citas_a_articulos(c["articulos_candidatos"]) if a.startswith(R.PREFIJO_19628 + "-art-")]
        num = [a.split("-art-", 1)[1] for a in cit]
        pares_directo += len(num)
        malos = [n for n in num if n in R.CONCORDANCIA_19628]
        cambian += len(malos)
        casos_afectados += bool(malos)
    return {"citas_de_la_ley_19628": pares_directo, "citas_que_apuntan_a_otra_materia": cambian,
            "casos_con_alguna_cita_a_otra_materia": casos_afectados, "numeros_que_coinciden": sorted(iguales),
            "concordancia": R.CONCORDANCIA_19628}


def clasificar_top(fid_top, cands, arts_por_norma, ley_normas):
    """vecino: mismo cuerpo y mismo número base o número contiguo a un candidato; misma_ley; otra_ley."""
    def base(a):
        m = re.search(r"-art-(t-)?(\d+)", a)
        return (a.split("-art-")[0], bool(m and m.group(1)), int(m.group(2))) if m else None

    bases = {base(c) for c in cands if base(c)}
    a = R.articulo_de(fid_top)
    b = base(a)
    if a in cands:
        return "candidato"
    if b and any(b[0] == x[0] and b[1] == x[1] and abs(b[2] - x[2]) <= 1 for x in bases):
        return "vecino"
    norma = int(a.split("-")[0])
    return "misma_ley" if norma in ley_normas else "otra_ley"


def fallos(detalle, arts, tops_n: int = 5) -> dict:
    """Qué hay en el top 5 de los casos que fallan."""
    cuenta, casos_f, hubs = Counter(), 0, Counter()
    for d in detalle:
        if not d.get("metricas") or d["acierto_articulo"]:
            continue
        casos_f += 1
        cands = set(d["candidatos"])
        ley_normas = R.LEYES[d["ley"]]
        vistos = []
        for f in d["top"][:tops_n]:
            a = R.articulo_de(f)
            if a in vistos:
                continue
            vistos.append(a)
            cuenta[clasificar_top(f, cands, None, ley_normas)] += 1
            hubs[corto(a)] += 1
    n = sum(cuenta.values())
    return {"casos_fallidos": casos_f, "resultados_distintos": n,
            "proporcion": {k: round(v / n, 3) for k, v in cuenta.items()} if n else {}, "mas_frecuentes": hubs.most_common(6)}


def reproduce_registro(registro, cand, campo, recall_directo) -> bool | None:
    """¿Coincide el recall@5 recalculado en memoria (mapeo directo) con el último registrado antes de la corrección?"""
    previas = [e for e in registro if e["parametros"].get("campo_consulta") == campo
               and e["parametros"].get("coleccion") == cand["coleccion"]
               and e["parametros"].get("modelo") == cand["modelo"]
               and e["parametros"].get("modelo_consulta", cand["modelo"]) == cand["modelo_consulta"]
               and e["parametros"].get("mapeo", "directo") == "directo"]
    if not previas:
        return None
    ultima = max(previas, key=lambda e: e["fecha"])
    return abs(ultima["metricas_articulo"]["global"]["recall5"] - recall_directo) < 1e-9


def por_largo(detalle, largos_art, cortes=(1500, 3000)) -> dict:
    """Fracción de pares (caso, artículo candidato) cuyo artículo llega al top 5, según el largo del artículo."""
    cubos = defaultdict(lambda: [0, 0])
    for d in detalle:
        if not d.get("metricas"):
            continue
        top5 = {R.articulo_de(f) for f in d["top"][:5]}
        for a in d["candidatos"]:
            n = largos_art.get(a, 0)
            cubo = f"<{cortes[0]}" if n < cortes[0] else (f"{cortes[0]}-{cortes[1] - 1}" if n < cortes[1] else f">={cortes[1]}")
            cubos[cubo][0] += a in top5
            cubos[cubo][1] += 1
    return {k: {"pares": n, "en_top5": round(h / n, 3)} for k, (h, n) in sorted(cubos.items())}


def oraculo_de_ley(casos, tops_amplios, arts) -> dict:
    """recall@5 por artículo si se buscara solo dentro de la ley correcta (ley_principal): techo de un enrutador por ley."""
    filtrados = []
    for caso, top in zip(casos, tops_amplios):
        ley = caso["ley_principal"]
        filtrados.append([t for t in top if ley in R.LEYES and t["id_norma"] in R.LEYES[ley]][:10] if ley in R.LEYES else top[:10])
    m = metricas(casos, filtrados, arts, "concordancia")
    return {"recall5": round(m["global"]["recall5"], 3), "cobertura5": round(m["global"]["cobertura5"], 3),
            "por_ley": {k: round(v["recall5"], 3) for k, v in m["por_ley"].items() if k != "global"}}


def costo_revectorizar(textos: list[str], chars_por_token: float, tpm=10000, rpm=3) -> dict:
    """Peticiones y minutos para vectorizar `textos` con Voyage con la lógica de embed_sync (lotes al 80 % del límite)."""
    lotes = embed_sync._lotes_por_tokens(textos, int(tpm * 0.8))
    espera = 0.0
    for lote in lotes:
        tokens = sum(len(t) for t in lote) / chars_por_token
        espera += max(60 / rpm, tokens * 60 / tpm)
    return {"peticiones": len(lotes), "tokens": int(sum(len(t) for t in textos) / chars_por_token),
            "minutos": round(espera / 60, 1)}


def concentracion(tops, k=5) -> dict:
    """Cuántas veces aparece cada fragmento en el top k de las 113 consultas (hubness)."""
    c = Counter(corto(R.articulo_de(f["fragmento_id"])) for t in tops for f in t[:k])
    total = sum(c.values())
    return {"distintos_en_top5": len(c), "diez_mas_frecuentes": c.most_common(10),
            "participacion_top10": round(sum(v for _, v in c.most_common(10)) / total, 3)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--campo", default="texto_original", choices=["texto_original", "resumen_parafraseado"])
    ap.add_argument("--salida", default=str(AQUI / "datos" / "analisis_recall_articulo.json"))
    args = ap.parse_args(argv)
    casos = json.loads(R.DATASET.read_text())["casos"]
    textos = [R.texto_consulta(c, args.campo) for c in casos]
    cands = [c for c in json.loads(CANDIDATOS.read_text())["candidatos"] if c["id"] not in ("qwen3-embedding-8b", "qwen3-embedding-4b")]
    no_sust = {f["id"] for f in json.loads(NO_SUSTANTIVOS.read_text())["fragmentos"]}
    frs = json.loads(FRAGMENTOS.read_text())
    texto_emb = {f["payload"]["fragmento_id"]: f["texto_embedding"] for f in frs}

    cache_col: dict[str, tuple] = {}
    out: dict = {"campo": args.campo}
    registro = [json.loads(l) for l in R.REGISTRO.read_text().splitlines() if l.strip()]

    # --- corpus y existencia
    pay0, v0 = cargar_puntos("normativa_cl")
    cache_col["normativa_cl"] = (pay0, v0)
    vigentes = [p for p in pay0 if p.get("vigente") is True]
    arts = {R.articulo_de(p["fragmento_id"]) for p in vigentes}
    largos = {p["fragmento_id"]: len(p["texto"]) for p in vigentes}
    largos_art: dict[str, int] = defaultdict(int)
    for f_id, n in largos.items():
        largos_art[R.articulo_de(f_id)] += n
    out["corpus"] = {"fragmentos_con_vector": len(pay0), "fragmentos_vigentes": len(vigentes), "articulos_vigentes": len(arts),
                     "articulos_en_varias_partes": len({R.articulo_de(p["fragmento_id"]) for p in vigentes
                                                          if re.search(r"-p\d+$", p["fragmento_id"])}),
                     "no_vigentes_con_vector": len(pay0) - len(vigentes), "sin_vector_no_sustantivos": len(no_sust),
                     "por_ley_vigentes": dict(Counter(corto(p["fragmento_id"]).split("#")[0] for p in vigentes))}
    out["existencia"] = existencia(casos, arts, no_sust)
    out["mapeo_19628"] = mapeo_19628(casos, arts)

    # candidatos por caso, azar y largo
    evaluables = []
    for c in casos:
        if c["ley_principal"] == "ninguna":
            continue
        dentro, _ = R.normalizar_candidatos(c["articulos_candidatos"], arts)
        if dentro:
            evaluables.append((c, dentro))
    cands_por_caso = [len(d) for _, d in evaluables]
    out["especificidad"] = {
        "casos_evaluables": len(evaluables),
        "candidatos_por_caso": {"media": round(float(np.mean(cands_por_caso)), 2), "mediana": float(np.median(cands_por_caso)),
                                "casos_con_un_solo_candidato": sum(1 for n in cands_por_caso if n == 1)},
        "recall_esperado_al_azar": {
            "global": round(float(np.mean([azar(len(arts), len(d)) for _, d in evaluables])), 3),
            **{ley: round(float(np.mean([azar(len(arts), len(d)) for c, d in evaluables if c["ley_principal"] == ley])), 3)
               for ley in ("20.393", "21.643", "19.628-21.719")}},
        "largo_candidatos_chars": {"mediana": float(np.median([largos[a] if a in largos else largos.get(a + "-p1", 0)
                                                               for _, d in evaluables for a in d])),
                                   "max": max(largos.get(a, largos.get(a + "-p1", 0)) for _, d in evaluables for a in d)},
        "largo_corpus_chars": {"mediana": float(np.median(list(largos.values()))), "max": max(largos.values())},
    }

    # --- por candidato: métricas con ambos mapeos, k, cobertura, fallos, concentración
    por_cand = {}
    exploratorio = {}
    bm25_cache: dict = {}
    for cand in cands:
        try:
            pay, v = cache_col.get(cand["coleccion"]) or cargar_puntos(cand["coleccion"])
            cache_col[cand["coleccion"]] = (pay, v)
            q = vectores_consulta(cand, textos)
        except Exception as e:  # noqa: BLE001  (candidato sin colección o sin consultas todavía)
            print(f"[{cand['id']}] omitido: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        tops = top_por_coseno(q, v, pay)
        tops_amplios = top_por_coseno(q, v, pay, k=len(pay))
        arts_c = {R.articulo_de(p["fragmento_id"]) for p in pay if p.get("vigente") is True}
        m_conc = metricas(casos, tops, arts_c, "concordancia")
        m_dir = metricas(casos, tops, arts_c, "directo")
        g = m_conc["global"]
        por_cand[cand["id"]] = {
            "directo": {k: m_dir["global"].get(k) for k in ("recall5", "casos_articulo", "hit8", "cobertura5")},
            "concordancia": {k: g.get(k) for k in ("recall5", "casos_articulo", "hit8", "hit10", "cobertura5", "cobertura8",
                                                   "cobertura10", "ndcg10", "mrr")},
            "recall5_por_ley_concordancia": {ley: round(m_conc["por_ley"][ley]["recall5"], 3)
                                             for ley in ("20.393", "21.643", "19.628-21.719")},
            "recall5_por_ley_directo": {ley: round(m_dir["por_ley"][ley]["recall5"], 3)
                                        for ley in ("20.393", "21.643", "19.628-21.719")},
            "fallos": fallos(m_conc["detalle"], arts_c), "concentracion_top5": concentracion(tops),
            "reproduce_el_registro_directo": reproduce_registro(registro, cand, args.campo, m_dir["global"]["recall5"]),
            "recall5_segun_largo_del_candidato": por_largo(m_conc["detalle"], largos_art),
            "con_oraculo_de_ley": oraculo_de_ley(casos, tops_amplios, arts_c),
        }
        # recall@5 por artículo candidato (qué candidatos nunca aparecen)
        hits = defaultdict(lambda: [0, 0])
        for d in m_conc["detalle"]:
            if not d.get("metricas"):
                continue
            top5 = {R.articulo_de(f) for f in d["top"][:5]}
            for a in d["candidatos"]:
                hits[corto(a)][0] += a in top5
                hits[corto(a)][1] += 1
        por_cand[cand["id"]]["candidato_en_top5"] = {a: f"{h}/{n}" for a, (h, n) in sorted(hits.items(), key=lambda x: -x[1][1])[:8]}

        # --- exploratorio: BM25, RRF, centrado (solo corpus vigente de este candidato)
        if cand["id"] in ("voyage-4-large", "voyage-law-2", "text-embedding-3-large", "bge-m3", "multilingual-e5-large-instruct"):
            idx = [i for i, p in enumerate(pay) if p.get("vigente") is True]
            pay_v = [pay[i] for i in idx]
            vv = v[idx]
            textos_doc = [texto_emb.get(p["fragmento_id"]) or p["texto"] for p in pay_v]
            clave_bm = tuple(p["fragmento_id"] for p in pay_v)
            if clave_bm not in bm25_cache:      # el léxico no depende del modelo: se calcula una vez por corpus
                bm = BM25(textos_doc)
                bm25_cache[clave_bm] = np.array([bm.puntajes(t) for t in textos])
            s_bm = bm25_cache[clave_bm]
            s_cos = q @ vv.T
            mu = vv.mean(axis=0)
            vc = vv - mu
            vc /= np.linalg.norm(vc, axis=1, keepdims=True)
            qc = q - mu
            qc /= np.linalg.norm(qc, axis=1, keepdims=True)
            s_cen = qc @ vc.T

            def r5(sc):
                mm = metricas(casos, tops_de_puntajes(sc, pay_v), arts_c, "concordancia")["global"]
                return {"recall5": round(mm["recall5"], 3), "hit8": round(mm["hit8"], 3), "cobertura5": round(mm["cobertura5"], 3)}
            exploratorio[cand["id"]] = {"vector": r5(s_cos), "bm25": r5(s_bm), "rrf_vector_bm25": r5(rrf(s_cos, s_bm)),
                                        "vector_centrado": r5(s_cen), "rrf_centrado_bm25": r5(rrf(s_cen, s_bm))}
    out["candidatos"] = por_cand
    out["exploratorio_sin_revectorizar"] = exploratorio

    # --- costo de re-vectorizar el corpus (estimación)
    chars_corpus = sum(len(texto_emb[p["fragmento_id"]]) for p in vigentes)
    reg = [json.loads(l) for l in R.REGISTRO.read_text().splitlines() if l.strip()]
    ratio = None
    for e in reg:
        if e["parametros"].get("modelo") == "voyage-law-2" and e["parametros"].get("campo_consulta") == "texto_original" \
                and (e.get("tokens_consultas") or {}).get("origen") == "medido":
            ratio = sum(len(t) for t in [R.texto_consulta(c, "texto_original") for c in casos]) / e["tokens_consultas"]["total"]
    cpt = ratio or 3.33
    docs = [texto_emb[p["fragmento_id"]] for p in vigentes if p["fragmento_id"] in texto_emb]
    resumen_chars = 420      # supuesto: resumen de materia de ~420 caracteres (~125 tokens) por fragmento
    con_resumen = [t + "x" * resumen_chars for t in docs]
    solo_resumen = ["x" * (resumen_chars + 120) for _ in docs]    # segundo punto por fragmento: resumen + encabezado corto
    out["costo_corpus"] = {
        "caracteres_texto_embedding": chars_corpus, "chars_por_token_medido": round(cpt, 2),
        "corpus_actual": costo_revectorizar(docs, cpt),
        "propuesta_encabezado_y_resumen_en_el_mismo_texto": costo_revectorizar(con_resumen, cpt),
        "propuesta_segundo_punto_con_el_resumen": costo_revectorizar(solo_resumen, cpt),
        "consultas_113": "sin costo: los vectores de consulta no dependen del texto del corpus y están en caché",
    }
    Path(args.salida).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=list))
    print(json.dumps(out, ensure_ascii=False, indent=1, default=list))
    return 0


if __name__ == "__main__":
    sys.exit(main())
