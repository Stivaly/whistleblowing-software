"""Configuración del núcleo desde variables de entorno (ver kerna/docs/contratos.md)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

CADENA_POR_DEFECTO = [
    {"modo": "oficial", "proveedor": "gemini", "modelo": "gemini-3.8-flash", "esquema": True, "sistema": True},
    {"modo": "respaldo", "proveedor": "gemini", "modelo": "gemini-3.5-flash-lite", "esquema": True, "sistema": True},
    {"modo": "local", "proveedor": "gemini", "modelo": "gemma-4-31b-it", "esquema": True, "sistema": True},
]


@dataclass
class Config:
    clientes: dict = field(default_factory=dict)  # {client_id: {"secreto_sha256", "cliente"}}
    jwt_secreto: str = ""
    gemini_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_esfuerzo: str = "low"
    voyage_api_key: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    coleccion: str = "normativa_cl"
    embedding: str = "voyage-4-large"
    dims: int = 1024
    local_url: str = ""
    local_token: str = ""
    top_k: int = 8
    rerank_modelo: str = ""        # vacío = sin reranking (rerank-2.5, rerank-2.5-lite de Voyage o bge-reranker-v2-m3 local)
    rerank_candidatos: int = 30
    evaluador: bool = False        # KERNA_EVALUADOR: agente evaluador LLM sobre los candidatos (apagado por defecto)
    evaluador_candidatos: int = 30
    evaluador_variante: str = "1"   # 1 y 2: citas literales; 3*: por identificadores con puntaje (evaluador_ids.py)
    hibrida: bool = False          # KERNA_HIBRIDA: BM25 + búsqueda densa fusionadas por RRF (apagado por defecto)
    hibrida_profundidad: int = 100
    hibrida_stemming: bool = True
    hibrida_extras: int = 0         # KERNA_HIBRIDA_EXTRAS: ver Retriever.extras_fusion (0 = fusión pura)
    multiquery: bool = False       # KERNA_MULTIQUERY: las conductas del perfil del evaluador por IDs (variante 3*) como consultas extra
    multiquery_max: int = 6
    multiquery_relato: bool = True  # conservar la consulta del relato completo junto a las conductas
    multiquery_peso_relato: float = 1.0
    enr_bm25: str = ""             # KERNA_ENR_BM25 (experimento enriquecimiento): "" | "concat" | "aparte" | "ambos"
    enr_coleccion_aparte: str = "" # KERNA_ENR_COLECCION_APARTE: colección con vectores del enriquecimiento solo (lista densa extra)
    enr_peso_aparte: float = 1.0   # KERNA_ENR_PESO_APARTE: peso en la fusión de las listas «aparte»
    enr_rol_factor: float = 1.0    # KERNA_ENR_ROL_FACTOR: multiplica el puntaje de fusión de artículos de rol procedimiento/sancion (1 = apagado)
    generador_completar: int = 0   # KERNA_GENERADOR_COMPLETAR=N: el resultado sigue el orden del evaluador y completa con él hasta N artículos (0 = apagado)
    generador_min_puntaje: int = 1  # KERNA_GENERADOR_MIN_PUNTAJE: puntaje mínimo del evaluador para completar un artículo que el generador omitió
    rerank_llm: bool = False       # KERNA_RERANK_LLM: reranker LLM listwise sobre la ventana de candidatas (apagado por defecto)
    rerank_llm_ventana: int = 35
    rerank_llm_fuente: str = "evaluador"  # KERNA_RERANK_LLM_FUENTE: evaluador | retriever (orden de la ventana de entrada)
    rerank_llm_voto_eval: float = 0.0     # KERNA_RERANK_LLM_VOTO_EVAL: peso del orden del evaluador como tercer ranking
    rerank_llm_criterios: bool = False    # KERNA_RERANK_LLM_CRITERIOS=1: agrega criterios por ley al prompt del reranker
    rerank_llm_permutaciones: int = 2     # KERNA_RERANK_LLM_PERMUTACIONES: 1-4 (entrada, invertida, rotada, rotada invertida)
    rerank_llm_voto_retriever: float = 0.0  # KERNA_RERANK_LLM_VOTO_RETRIEVER: peso del orden del retriever como ranking adicional
    revisor_sin_causales: tuple = ()  # KERNA_REVISOR_SIN_CAUSALES: causales de veto que el revisor no aplica (solo evaluación; vacío = todas)
    evaluador_votos: int = 1       # KERNA_EVALUADOR_VOTOS: pasadas independientes del evaluador por IDs (promedio de puntajes)
    revisor_votos: int = 1         # KERNA_REVISOR_VOTOS: llamadas independientes del revisor (1 = una sola, comportamiento original)
    revisor_veto_min: int = 0      # KERNA_REVISOR_VETO_MIN: vetos coincidentes (misma causal) necesarios para vetar; 0 = mayoría de los votos
    revisor_veto_cita: bool = False  # KERNA_REVISOR_VETO_CITA: un veto exige citar al menos una frase del artículo
    revisor_estricto: bool = False   # KERNA_REVISOR_ESTRICTO: criterio adicional «vetar solo con evidencia expresa»
    revisor: bool = False          # KERNA_REVISOR: revisor jurídico (confirma/condiciona/veta) tras la validación de citas
    concurrencia: int = 2
    umbral_similitud: float = 0.0
    cadena: list = field(default_factory=lambda: [dict(n) for n in CADENA_POR_DEFECTO])
    modelo_clasificador: str = "gemini-3.5-flash-lite"
    almacen: str = "memoria"
    tablas_url: str = ""
    tablas_conexion: str = ""
    plazo_global_s: float = 240.0
    corte_llamada_s: float = 30.0
    esperas_s: tuple = (1.0, 2.0, 4.0)
    max_texto: int = 60000
    max_articulos: int = 5

    @classmethod
    def desde_entorno(cls, env=None) -> "Config":
        e = os.environ if env is None else env
        c = cls()
        c.clientes = json.loads(e.get("KERNA_CLIENTES") or "{}")
        c.jwt_secreto = e.get("KERNA_JWT_SECRETO", "")
        c.gemini_api_key = e.get("GEMINI_API_KEY", "")
        c.azure_openai_endpoint = e.get("AZURE_OPENAI_ENDPOINT", "")
        c.azure_openai_key = e.get("AZURE_OPENAI_KEY", "")
        c.azure_openai_esfuerzo = e.get("KERNA_AZURE_OPENAI_ESFUERZO", c.azure_openai_esfuerzo)
        c.voyage_api_key = e.get("VOYAGE_API_KEY", "")
        c.qdrant_url = e.get("QDRANT_URL", "")
        c.qdrant_api_key = e.get("QDRANT_API_KEY", "")
        c.coleccion = e.get("KERNA_COLECCION", c.coleccion)
        c.embedding = e.get("KERNA_EMBEDDING", c.embedding)
        c.dims = int(e.get("KERNA_DIMS", c.dims))
        c.local_url = e.get("KERNA_LOCAL_URL", "")
        c.local_token = e.get("KERNA_LOCAL_TOKEN", "")
        c.top_k = int(e.get("KERNA_TOP_K", c.top_k))
        c.rerank_modelo = e.get("KERNA_RERANK_MODELO", c.rerank_modelo)
        c.rerank_candidatos = int(e.get("KERNA_RERANK_CANDIDATOS", c.rerank_candidatos))
        c.evaluador = e.get("KERNA_EVALUADOR", "").strip().lower() in ("1", "true", "si", "sí", "on")
        c.evaluador_candidatos = int(e.get("KERNA_EVALUADOR_CANDIDATOS", c.evaluador_candidatos))
        c.evaluador_variante = e.get("KERNA_EVALUADOR_VARIANTE", c.evaluador_variante)
        c.enr_bm25 = e.get("KERNA_ENR_BM25", "").strip().lower()
        c.enr_coleccion_aparte = e.get("KERNA_ENR_COLECCION_APARTE", "").strip()
        c.enr_peso_aparte = float(e.get("KERNA_ENR_PESO_APARTE", c.enr_peso_aparte))
        c.enr_rol_factor = float(e.get("KERNA_ENR_ROL_FACTOR", c.enr_rol_factor))
        c.generador_completar = int(e.get("KERNA_GENERADOR_COMPLETAR", c.generador_completar))
        c.generador_min_puntaje = int(e.get("KERNA_GENERADOR_MIN_PUNTAJE", c.generador_min_puntaje))
        c.rerank_llm = e.get("KERNA_RERANK_LLM", "").strip().lower() in ("1", "true", "si", "sí", "on")
        c.rerank_llm_ventana = int(e.get("KERNA_RERANK_LLM_VENTANA", c.rerank_llm_ventana))
        c.rerank_llm_fuente = e.get("KERNA_RERANK_LLM_FUENTE", c.rerank_llm_fuente).strip().lower()
        c.rerank_llm_voto_eval = float(e.get("KERNA_RERANK_LLM_VOTO_EVAL", c.rerank_llm_voto_eval))
        c.rerank_llm_criterios = e.get("KERNA_RERANK_LLM_CRITERIOS", "").strip().lower() in ("1", "true", "si", "sí", "on")
        c.rerank_llm_permutaciones = int(e.get("KERNA_RERANK_LLM_PERMUTACIONES", c.rerank_llm_permutaciones))
        c.rerank_llm_voto_retriever = float(e.get("KERNA_RERANK_LLM_VOTO_RETRIEVER", c.rerank_llm_voto_retriever))
        c.revisor_sin_causales = tuple(x.strip() for x in e.get("KERNA_REVISOR_SIN_CAUSALES", "").split(",") if x.strip())
        c.evaluador_votos = max(1, int(e.get("KERNA_EVALUADOR_VOTOS", c.evaluador_votos)))
        c.revisor_votos = max(1, int(e.get("KERNA_REVISOR_VOTOS", c.revisor_votos)))
        c.revisor_veto_min = int(e.get("KERNA_REVISOR_VETO_MIN", c.revisor_veto_min))
        c.revisor_veto_cita = e.get("KERNA_REVISOR_VETO_CITA", "").strip().lower() in ("1", "true", "si", "sí", "on")
        c.revisor_estricto = e.get("KERNA_REVISOR_ESTRICTO", "").strip().lower() in ("1", "true", "si", "sí", "on")
        c.revisor = e.get("KERNA_REVISOR", "").strip().lower() in ("1", "true", "si", "sí", "on")
        _si = ("1", "true", "si", "sí", "on")
        c.hibrida = e.get("KERNA_HIBRIDA", "").strip().lower() in _si
        c.hibrida_profundidad = int(e.get("KERNA_HIBRIDA_PROFUNDIDAD", c.hibrida_profundidad))
        c.hibrida_extras = int(e.get("KERNA_HIBRIDA_EXTRAS", c.hibrida_extras))
        c.hibrida_stemming = e.get("KERNA_HIBRIDA_STEMMING", "1").strip().lower() in _si
        c.multiquery = e.get("KERNA_MULTIQUERY", "").strip().lower() in _si
        c.multiquery_max = int(e.get("KERNA_MULTIQUERY_MAX", c.multiquery_max))
        c.multiquery_relato = e.get("KERNA_MULTIQUERY_RELATO", "1").strip().lower() in _si
        c.multiquery_peso_relato = float(e.get("KERNA_MULTIQUERY_PESO_RELATO", c.multiquery_peso_relato))
        c.modelo_clasificador = e.get("KERNA_MODELO_CLASIFICADOR", c.modelo_clasificador)
        c.plazo_global_s = float(e.get("KERNA_PLAZO_GLOBAL_S", c.plazo_global_s))
        c.corte_llamada_s = float(e.get("KERNA_CORTE_LLAMADA_S", c.corte_llamada_s))
        c.concurrencia = int(e.get("KERNA_CONCURRENCIA", c.concurrencia))
        c.umbral_similitud = float(e.get("KERNA_UMBRAL_SIMILITUD", c.umbral_similitud))
        if e.get("KERNA_CADENA"):
            c.cadena = json.loads(e["KERNA_CADENA"])
        c.almacen = e.get("KERNA_ALMACEN", c.almacen)
        c.tablas_url = e.get("KERNA_TABLAS_URL", "")
        c.tablas_conexion = e.get("KERNA_TABLAS_CONEXION", "")
        return c
