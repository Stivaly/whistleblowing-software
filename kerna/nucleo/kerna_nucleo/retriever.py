"""Recuperación: nube (Voyage + Qdrant) con respaldo en el servicio local."""
from __future__ import annotations

import asyncio

from dataclasses import dataclass, field

from kerna_comun import telemetria

from .bm25 import RRF_K, IndiceBM25, rrf
from .proveedores import ErrorProveedor
from .proveedores.bge_reranker import es_bge


class RecuperacionFallida(Exception):
    """Fallaron la nube y el servicio local."""


@dataclass
class Recuperacion:
    fragmentos: list[dict]
    recuperacion: str  # "nube" | "local"
    embedding: str
    coleccion: str
    version_corpus: int
    mejor_puntaje: float
    tokens_embedding: int = 0
    tokens_rerank: int = 0
    reranker: str = ""


class Retriever:
    def __init__(self, voyage, qdrant, local, coleccion: str, embedding: str, top_k: int, umbral: float,
                 esperas_429=(3.0, 8.0, 15.0), dormir=None,
                 rerank_modelo: str = "", rerank_candidatos: int = 30, reranker_local=None,
                 hibrida: bool = False, hibrida_profundidad: int = 100, hibrida_stemming: bool = True,
                 k_rrf: int = RRF_K, multiquery_relato: bool = True, peso_relato: float = 1.0,
                 extras_fusion: int = 0, enr_bm25: str = "", coleccion_aparte: str = "", peso_aparte: float = 1.0,
                 rol_factor: float = 1.0):
        self._reranker_local = reranker_local
        self._voyage, self._qdrant, self._local = voyage, qdrant, local
        self.coleccion, self.embedding, self.top_k, self.umbral = coleccion, embedding, top_k, umbral
        # Reranking por API (desactivado con rerank_modelo vacío): recupera `rerank_candidatos` y se queda con top_k.
        self.rerank_modelo, self.rerank_candidatos = rerank_modelo, max(rerank_candidatos, top_k)
        self._esperas_429, self._dormir = tuple(esperas_429), dormir or asyncio.sleep
        # Búsqueda híbrida (KERNA_HIBRIDA): BM25 sobre los fragmentos vigentes fusionado con la densa por RRF.
        self.hibrida, self.hibrida_profundidad, self.hibrida_stemming, self.k_rrf = (
            hibrida, hibrida_profundidad, hibrida_stemming, k_rrf)
        # Con consultas adicionales: ¿se conserva la consulta del relato completo? ¿con qué peso en la fusión?
        self.multiquery_relato, self.peso_relato = multiquery_relato, peso_relato
        # extras_fusion > 0: los k - extras primeros de la densa del relato quedan siempre entre los candidatos y la
        # fusión aporta hasta `extras` nuevos (la fusión pura desplaza candidatos densos que el evaluador necesita).
        self.extras_fusion = extras_fusion
        # Experimento de enriquecimiento (colección con campos `enriquecimiento`, `rol`, `articulo_id`, `literal`):
        # texto del BM25 ("concat" suma el enriquecimiento al texto; "aparte" agrega un índice solo del enriquecimiento;
        # "ambos"), lista densa extra de una colección con los vectores del enriquecimiento solo, y factor de
        # puntaje para los artículos de rol procedimiento/sanción. Todo apagado por defecto.
        self.enr_bm25, self.coleccion_aparte, self.peso_aparte, self.rol_factor = (
            enr_bm25, coleccion_aparte, peso_aparte, rol_factor)
        self._indice_enr: IndiceBM25 | None = None
        self._indice: tuple[int, IndiceBM25, dict[str, dict]] | None = None   # (version_corpus, índice, payloads)
        self._cerrojo_indice = asyncio.Lock()

    async def recuperar(self, texto: str, consultas: list[str] | tuple = ()) -> Recuperacion:
        """`consultas`: frases breves adicionales (conductas del perfil; KERNA_MULTIQUERY), fusionadas por RRF con la
        consulta del relato completo. Solo se usan en la recuperación de la nube (el servicio local usa el relato)."""
        try:
            return await self._nube_con_reintento(texto, tuple(consultas))
        except ErrorProveedor as e:
            telemetria.evento("recuperacion_nube_fallida", proveedor=e.proveedor, codigo=str(e.codigo or "silencio"))
        try:
            return await self._respaldo(texto)
        except ErrorProveedor as e:
            telemetria.evento("recuperacion_local_fallida", proveedor=e.proveedor, codigo=str(e.codigo or "silencio"))
            raise RecuperacionFallida() from None

    async def _nube_con_reintento(self, texto: str, consultas: tuple = ()) -> Recuperacion:
        """El límite de peticiones del proveedor (429) se espera y se reintenta; lo demás pasa al respaldo local."""
        for espera in self._esperas_429:
            try:
                return await self._nube(texto, consultas)
            except ErrorProveedor as e:
                if e.codigo != 429:
                    raise
                telemetria.evento("recuperacion_nube_espera", proveedor=e.proveedor, codigo="429", espera_s=espera)
                await self._dormir(espera)
        return await self._nube(texto, consultas)

    async def _nube(self, texto: str, consultas: tuple = ()) -> Recuperacion:
        k = self.rerank_candidatos if self.rerank_modelo else self.top_k
        if self.hibrida or consultas:
            rec = await self._nube_fusionada(texto, consultas, k)
        else:
            vector, tokens = await self._voyage.embed_consulta(texto)
            puntos = await self._qdrant.buscar(self.coleccion, vector, k)
            version = await self._qdrant.version_corpus(self.coleccion)
            rec = self._armar(puntos, "nube", self.embedding, self.coleccion, version, tokens, limite=k)
        if self.rerank_modelo and len(rec.fragmentos) > 1:
            await self._reordenar(texto, rec)
        else:
            rec.fragmentos = rec.fragmentos[: self.top_k]
        return rec

    async def _nube_fusionada(self, texto: str, consultas: tuple, k: int) -> Recuperacion:
        """Una lista densa por consulta (relato y frases) y, con `hibrida`, una lista BM25 por consulta; todas se
        fusionan por RRF. El puntaje que se conserva es el coseno de la mejor búsqueda densa (el umbral sigue
        significando lo mismo); `puntaje_rrf` guarda el de la fusión."""
        relato = self.multiquery_relato or not consultas
        textos = ([texto] if relato else []) + list(consultas)
        pesos_t = ([self.peso_relato] if relato and consultas else [1.0] if relato else []) + [1.0] * len(consultas)
        if consultas:
            vectores, tokens = await self._voyage.embed_consultas(textos)
        else:
            vector, tokens = await self._voyage.embed_consulta(texto)
            vectores = [vector]
        prof = max(k, self.hibrida_profundidad)
        resultados = await asyncio.gather(*[self._qdrant.buscar(self.coleccion, v, prof) for v in vectores])
        version = await self._qdrant.version_corpus(self.coleccion)
        densas = [self._armar(p, "nube", self.embedding, self.coleccion, version, 0, limite=prof).fragmentos
                  for p in resultados]
        aparte: list[list[dict]] = []
        if self.coleccion_aparte:
            res_a = await asyncio.gather(*[self._qdrant.buscar(self.coleccion_aparte, v, prof) for v in vectores])
            aparte = [self._armar(p, "nube", self.embedding, self.coleccion_aparte, version, 0, limite=prof).fragmentos
                      for p in res_a]
        indice = await self._indice_lexico(version) if self.hibrida else None
        docs: dict[str, dict] = {}
        rankings: list[list[str]] = []
        pesos: list[float] = []
        for i, t in enumerate(textos):
            pesos += [pesos_t[i]] * (2 if indice else 1)
            for f in densas[i]:
                docs.setdefault(f["fragmento_id"], f)
            rankings.append([f["fragmento_id"] for f in densas[i]])
            if indice:
                rankings.append([ident for ident, _ in indice[1].buscar(t, prof)])
                if self._indice_enr is not None:
                    rankings.append([ident for ident, _ in self._indice_enr.buscar(t, prof)])
                    pesos.append(pesos_t[i] * self.peso_aparte)
            if aparte:
                for f in aparte[i]:
                    docs.setdefault(f["fragmento_id"], f)
                rankings.append([f["fragmento_id"] for f in aparte[i]])
                pesos.append(pesos_t[i] * self.peso_aparte)
        coseno: dict[str, float] = {}
        for lista in densas:
            for f in lista:
                coseno[f["fragmento_id"]] = max(coseno.get(f["fragmento_id"], 0.0), float(f.get("puntaje", 0)))
        frags = []
        fusion = rrf(rankings, self.k_rrf, pesos)
        if self.rol_factor != 1.0:
            def _rol(i):
                return ((docs.get(i) or (indice[2].get(i) if indice else None)) or {}).get("rol", "")
            fusion = sorted(((i, p * (self.rol_factor if _rol(i) in ("procedimiento", "sancion") else 1.0))
                             for i, p in fusion), key=lambda x: -x[1])
        if 0 < self.extras_fusion < k and relato and densas:
            fijos = {f["fragmento_id"] for f in densas[0][: k - self.extras_fusion]}
            nuevos = [i for i, _ in fusion if i not in fijos][: self.extras_fusion]
            fusion = [x for x in fusion if x[0] in fijos or x[0] in set(nuevos)]
        vistos: set[str] = set()
        for ident, p_rrf in fusion:
            if len(frags) >= k:
                break
            base = docs.get(ident) or (indice[2].get(ident) if indice else None)
            if base:
                if base.get("literal"):      # fragmentos por literal: un solo literal (el mejor) por artículo
                    if base.get("articulo_id") in vistos:
                        continue
                    vistos.add(base.get("articulo_id"))
                frags.append(dict(base, vigente=True, puntaje=coseno.get(ident, 0.0), puntaje_rrf=p_rrf))
        mejor = max((f["puntaje"] for f in frags), default=0.0)
        return Recuperacion(frags, "nube", self.embedding, self.coleccion, version, mejor, tokens)

    async def _indice_lexico(self, version: int):
        """Índice BM25 de los fragmentos vigentes, obtenido de Qdrant (scroll) y reconstruido si cambia la versión
        del corpus. Si no se puede obtener, la recuperación sigue solo con la búsqueda densa."""
        async with self._cerrojo_indice:
            if self._indice is None or self._indice[0] != version:
                try:
                    puntos = await self._qdrant.fragmentos_vigentes(self.coleccion)
                except ErrorProveedor as e:
                    telemetria.evento("hibrida_sin_indice", proveedor=e.proveedor, codigo=str(e.codigo or "silencio"))
                    return None
                docs = {p["fragmento_id"]: dict(p) for p in puntos
                        if p.get("vigente") is not False and p.get("tipo") != "meta" and p.get("fragmento_id")}
                concat = self.enr_bm25 in ("concat", "ambos")
                indice = IndiceBM25(((i, (d.get("texto") or "") + (" " + d.get("enriquecimiento", "") if concat else ""))
                                     for i, d in docs.items()), stemming=self.hibrida_stemming)
                self._indice_enr = (IndiceBM25(((i, d.get("enriquecimiento") or "") for i, d in docs.items()),
                                               stemming=self.hibrida_stemming)
                                    if self.enr_bm25 in ("aparte", "ambos") else None)
                self._indice = (version, indice, docs)
            return self._indice

    async def _reordenar(self, texto: str, rec: Recuperacion) -> None:
        """Reordena con el reranker; si falla, conserva el orden del embedding (top_k primeros)."""
        try:
            motor = self._reranker_local if self._reranker_local and es_bge(self.rerank_modelo) else self._voyage
            orden, tokens = await motor.rerank(texto, [f.get("texto", "") for f in rec.fragmentos],
                                                      self.rerank_modelo, self.top_k)
        except ErrorProveedor as e:
            telemetria.evento("rerank_fallido", proveedor=e.proveedor, codigo=str(e.codigo or "silencio"))
            rec.fragmentos = rec.fragmentos[: self.top_k]
            return
        frags = [dict(rec.fragmentos[i], puntaje_embedding=rec.fragmentos[i].get("puntaje", 0), puntaje=s)
                 for i, s in orden if 0 <= i < len(rec.fragmentos)][: self.top_k]
        rec.fragmentos, rec.tokens_rerank, rec.reranker = frags, tokens, self.rerank_modelo

    async def _respaldo(self, texto: str) -> Recuperacion:
        d = await self._local.buscar(texto, self.top_k)
        return self._armar(d["fragmentos"], "local", str(d.get("modelo", "")), str(d.get("coleccion", "")),
                           int(d.get("version_corpus", 0) or 0), 0)

    def _armar(self, puntos, recuperacion, embedding, coleccion, version, tokens, limite=None) -> Recuperacion:
        frags = [p for p in puntos if p.get("vigente") is not False and p.get("tipo") != "meta"
                 and p.get("fragmento_id")]
        frags = [dict(p, vigente=True) for p in frags][: limite or self.top_k]
        mejor = max((float(p.get("puntaje", 0)) for p in frags), default=0.0)
        return Recuperacion(frags, recuperacion, embedding, coleccion, version, mejor, tokens)
