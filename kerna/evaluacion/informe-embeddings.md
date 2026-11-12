# Informe de la prueba comparativa de embeddings

Generado por `comparar_embeddings.py` a partir de `registro/recall_retriever.jsonl`. Sin textos de denuncias.

## Método

- Dataset: `datos/denuncias_publicas.json`, sha256 `26c4bb1c98c1e490…`; consulta = `texto_original`.
- Mismo corpus (fragmentos sustantivos vigentes de la BCN) y mismo texto por fragmento (`texto_embedding`) en cada colección; coseno; filtro `vigente=true`; top 5 (nDCG@10 y MRR sobre el top 10); 1024 dimensiones salvo EmbeddingGemma (768) y `voyage-law-2` (1024 fijas).
- Métrica principal: recall@5 por **artículo** (algún artículo candidato en el top 5; se evalúan solo los casos con candidatos mapeables al corpus). Meta 0.80 por artículo; por ley es dato secundario. IC de 95 % por bootstrap de casos (2000 remuestreos, semilla 20261110). Los candidatos del dataset son alternativas aceptables, así que recall@5 y hit rate@5 coinciden. Mapeo de candidatos: `concordancia` (los artículos de la Ley 19.628 citados con la numeración previa a la Ley 21.719 se traducen al texto reformado que trae el corpus vigente). Ver `analisis-recall-articulo.md`.
- Pares: diferencia de recall@5 con IC bootstrap pareado (mismos casos y remuestreos).
- Regla: si la diferencia de recall@5 es < 0.05 o los intervalos se superponen, desempata nDCG@10, luego P95 de la consulta y luego costo.
- Modelos abiertos: calculados dentro de Azure (job `job-kerna-eval-embeddings`, CPU); sus P95 son de CPU de 4 vCPU y su costo es de cómputo, no por token. Los de API miden la latencia de una consulta por petición desde el servidor de desarrollo, cuyas esperas de DNS (múltiplos de 5 s) la inflan: el P95 de Azure OpenAI (mínimo 0,8 s, mediana 5,8 s) no es comparable con el de Voyage; repetirlo desde Azure antes de usarlo para decidir.

## Resultados por candidato (nivel artículo)

| Candidato | Tipo | Casos | recall@5 [IC 95 %] | nDCG@10 | MRR | P@5 | recall ley | P95 consulta (ms) | Tokens | Costo (USD) | ¿Meta? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| voyage-4-large | nube | 61 | 0.393 [0.262, 0.525] | 0.207 | 0.190 | 0.111 | 0.934 | 674 | 204575 | — | no |
| voyage-law-2 | nube | 61 | 0.557 [0.426, 0.689] | 0.385 | 0.399 | 0.141 | 0.901 | 1893 | 184195 | 0.0221 | no |
| text-embedding-3-large (Azure OpenAI) | nube | 61 | 0.311 [0.197, 0.426] | 0.181 | 0.167 | 0.079 | 0.846 | 15761 | 153814 | 0.0200 | no |
| asimétrica: corpus voyage-4-large, consultas voyage-4-lite | nube | 61 | 0.328 [0.213, 0.443] | 0.220 | 0.194 | 0.095 | 0.934 | 682 | 165660 | — | no |
| BGE-M3 | abierto | 61 | 0.311 [0.197, 0.426] | 0.166 | 0.173 | 0.069 | 0.692 | 29782 | 123079 | 0.1501 | no |
| EmbeddingGemma 300M (768 dims) | abierto | 61 | 0.230 [0.131, 0.344] | 0.169 | 0.153 | 0.052 | 0.780 | 8523 | 102608 | 0.0594 | no |
| multilingual-e5-large-instruct | abierto | 61 | 0.279 [0.180, 0.393] | 0.197 | 0.153 | 0.082 | 0.923 | 1419 | 48453 | 0.0208 | no |

### Por ley

| Candidato | Ley | Casos art. | recall@5 artículo | nDCG@10 | recall@5 ley |
|---|---|---|---|---|---|
| voyage-4-large | 19.628-21.719 | 23 | 0.391 | 0.204 | 1.000 |
| voyage-4-large | 20.393 | 10 | 0.000 | 0.000 | 0.792 |
| voyage-4-large | 21.643 | 28 | 0.536 | 0.284 | 0.966 |
| voyage-law-2 | 19.628-21.719 | 23 | 0.522 | 0.283 | 1.000 |
| voyage-law-2 | 20.393 | 10 | 0.200 | 0.067 | 0.708 |
| voyage-law-2 | 21.643 | 28 | 0.714 | 0.583 | 0.931 |
| text-embedding-3-large (Azure OpenAI) | 19.628-21.719 | 23 | 0.304 | 0.201 | 0.974 |
| text-embedding-3-large (Azure OpenAI) | 20.393 | 10 | 0.000 | 0.000 | 0.750 |
| text-embedding-3-large (Azure OpenAI) | 21.643 | 28 | 0.429 | 0.229 | 0.759 |
| asimétrica: corpus voyage-4-large, consultas voyage-4-lite | 19.628-21.719 | 23 | 0.304 | 0.236 | 0.974 |
| asimétrica: corpus voyage-4-large, consultas voyage-4-lite | 20.393 | 10 | 0.000 | 0.000 | 0.875 |
| asimétrica: corpus voyage-4-large, consultas voyage-4-lite | 21.643 | 28 | 0.464 | 0.286 | 0.931 |
| BGE-M3 | 19.628-21.719 | 23 | 0.435 | 0.232 | 0.974 |
| BGE-M3 | 20.393 | 10 | 0.000 | 0.000 | 0.125 |
| BGE-M3 | 21.643 | 28 | 0.321 | 0.170 | 0.793 |
| EmbeddingGemma 300M (768 dims) | 19.628-21.719 | 23 | 0.043 | 0.052 | 0.921 |
| EmbeddingGemma 300M (768 dims) | 20.393 | 10 | 0.000 | 0.000 | 0.667 |
| EmbeddingGemma 300M (768 dims) | 21.643 | 28 | 0.464 | 0.325 | 0.690 |
| multilingual-e5-large-instruct | 19.628-21.719 | 23 | 0.174 | 0.136 | 0.974 |
| multilingual-e5-large-instruct | 20.393 | 10 | 0.000 | 0.000 | 0.750 |
| multilingual-e5-large-instruct | 21.643 | 28 | 0.464 | 0.318 | 1.000 |

### Más allá del top 5

hit = algún candidato en el top k (la métrica principal con k = 5); cobertura = fracción de los candidatos que aparece (recall verdadero). El núcleo entrega 8 fragmentos al modelo.

| Candidato | hit@5 | hit@8 | hit@10 | cobertura@5 | cobertura@8 | cobertura@10 |
|---|---|---|---|---|---|---|
| voyage-4-large | 0.393 | 0.410 | 0.459 | 0.287 | 0.311 | 0.344 |
| voyage-law-2 | 0.557 | 0.607 | 0.656 | 0.389 | 0.477 | 0.536 |
| text-embedding-3-large (Azure OpenAI) | 0.311 | 0.328 | 0.361 | 0.199 | 0.249 | 0.291 |
| asimétrica: corpus voyage-4-large, consultas voyage-4-lite | 0.328 | 0.459 | 0.492 | 0.238 | 0.336 | 0.358 |
| BGE-M3 | 0.311 | 0.377 | 0.410 | 0.178 | 0.235 | 0.268 |
| EmbeddingGemma 300M (768 dims) | 0.230 | 0.426 | 0.459 | 0.145 | 0.277 | 0.298 |
| multilingual-e5-large-instruct | 0.279 | 0.344 | 0.443 | 0.186 | 0.281 | 0.373 |

### Efecto de la corrección del mapeo de candidatos (recall@5 por artículo)

| Candidato | Antes (`directo`) | Casos | Después (`concordancia`) | Casos |
|---|---|---|---|---|
| voyage-4-large | 0.328 | 61 | 0.393 | 61 |
| voyage-law-2 | 0.508 | 61 | 0.557 | 61 |
| text-embedding-3-large (Azure OpenAI) | 0.279 | 61 | 0.311 | 61 |
| asimétrica: corpus voyage-4-large, consultas voyage-4-lite | 0.279 | 61 | 0.328 | 61 |
| BGE-M3 | 0.311 | 61 | 0.311 | 61 |
| EmbeddingGemma 300M (768 dims) | 0.246 | 61 | 0.230 | 61 |
| multilingual-e5-large-instruct | 0.279 | 61 | 0.279 | 61 |

## Comparación por pares (recall@5 por artículo)

| A | B | Casos | A − B | IC 95 % pareado | ¿Diferencia significativa? |
|---|---|---|---|---|---|
| voyage-4-large | voyage-law-2 | 61 | -0.164 | [-0.295, -0.033] | sí |
| voyage-4-large | text-embedding-3-large | 61 | +0.082 | [-0.016, +0.197] | no |
| voyage-4-large | asimetrica | 61 | +0.066 | [+0.000, +0.148] | no |
| voyage-4-large | bge-m3 | 61 | +0.082 | [-0.066, +0.246] | no |
| voyage-4-large | embeddinggemma-300m | 61 | +0.164 | [+0.033, +0.295] | sí |
| voyage-4-large | multilingual-e5-large-instruct | 61 | +0.115 | [+0.016, +0.230] | sí |
| voyage-law-2 | text-embedding-3-large | 61 | +0.246 | [+0.131, +0.393] | sí |
| voyage-law-2 | asimetrica | 61 | +0.230 | [+0.098, +0.361] | sí |
| voyage-law-2 | bge-m3 | 61 | +0.246 | [+0.115, +0.393] | sí |
| voyage-law-2 | embeddinggemma-300m | 61 | +0.328 | [+0.213, +0.443] | sí |
| voyage-law-2 | multilingual-e5-large-instruct | 61 | +0.279 | [+0.180, +0.393] | sí |
| text-embedding-3-large | asimetrica | 61 | -0.016 | [-0.098, +0.066] | no |
| text-embedding-3-large | bge-m3 | 61 | +0.000 | [-0.148, +0.148] | no |
| text-embedding-3-large | embeddinggemma-300m | 61 | +0.082 | [-0.049, +0.197] | no |
| text-embedding-3-large | multilingual-e5-large-instruct | 61 | +0.033 | [-0.049, +0.115] | no |
| asimetrica | bge-m3 | 61 | +0.016 | [-0.131, +0.164] | no |
| asimetrica | embeddinggemma-300m | 61 | +0.098 | [-0.033, +0.230] | no |
| asimetrica | multilingual-e5-large-instruct | 61 | +0.049 | [-0.033, +0.148] | no |
| bge-m3 | embeddinggemma-300m | 61 | +0.082 | [-0.049, +0.213] | no |
| bge-m3 | multilingual-e5-large-instruct | 61 | +0.033 | [-0.115, +0.180] | no |
| embeddinggemma-300m | multilingual-e5-large-instruct | 61 | -0.049 | [-0.164, +0.066] | no |

## Decisión

- **Nube**: voyage-law-2 (recall@5 0.557).
- **Local** (el mejor de los abiertos, aunque gane uno de nube): multilingual-e5-large-instruct (recall@5 0.279).
- Ningún candidato llega a la meta de 0.80 por artículo (el mejor: 0.557): revisar primero el texto que se vectoriza por fragmento (causa raíz y propuesta: `analisis-recall-articulo.md`).

Criterios aplicados:
- voyage-law-2 vs voyage-4-large: gana voyage-law-2 por nDCG@10 (recall@5 sin diferencia decisiva)
- text-embedding-3-large vs voyage-law-2: gana voyage-law-2 por nDCG@10 (recall@5 sin diferencia decisiva)
- asimetrica vs voyage-law-2: gana voyage-law-2 por nDCG@10 (recall@5 sin diferencia decisiva)
- bge-m3 vs voyage-law-2: gana voyage-law-2 por nDCG@10 (recall@5 sin diferencia decisiva)
- embeddinggemma-300m vs voyage-law-2: gana voyage-law-2 por recall@5
- multilingual-e5-large-instruct vs voyage-law-2: gana voyage-law-2 por recall@5

Entre los abiertos:
- embeddinggemma-300m vs bge-m3: gana embeddinggemma-300m por nDCG@10 (recall@5 sin diferencia decisiva)
- multilingual-e5-large-instruct vs embeddinggemma-300m: gana multilingual-e5-large-instruct por nDCG@10 (recall@5 sin diferencia decisiva)

## Candidatos no medidos

- Qwen3-Embedding 8B: no cabe en el job de Azure (4 vCPU, 8 GiB, sin GPU): Ollama responde 500 al cargarlo.
- Qwen3-Embedding 4B (solo si el 8B no cabe): en el job de Azure (4 vCPU, 8 GiB, sin GPU) no termina los 145 fragmentos y las 226 consultas en 60 min (dos intentos); a esa velocidad tampoco cumpliría la latencia de consulta.

## Calidad de recuperación medida, en escala de 1 a 5

Regla: interpolación lineal del recall@5 por artículo, de 1 (recall 0) a 5 (recall igual a la meta de 0.80), redondeada al entero más cercano; el 5 se reserva a quien cumple la meta (5: ≥ 0.80; 4: ≥ 0.50; 3: ≥ 0.30; 2: ≥ 0.10; 1: < 0.10). Reemplaza al puntaje de calidad basado en cifras del proveedor al recalcular el análisis ponderado del modelo de embeddings.

| Candidato | recall@5 artículo | Puntaje |
|---|---|---|
| voyage-4-large | 0.393 | 3 |
| voyage-law-2 | 0.557 | 4 |
| text-embedding-3-large (Azure OpenAI) | 0.311 | 3 |
| asimétrica: corpus voyage-4-large, consultas voyage-4-lite | 0.328 | 3 |
| BGE-M3 | 0.311 | 3 |
| EmbeddingGemma 300M (768 dims) | 0.230 | 2 |
| multilingual-e5-large-instruct | 0.279 | 2 |

## Reranker sobre el top 30

- Implementado en el retriever del núcleo, desactivado por defecto: `KERNA_RERANK_MODELO` (vacío = sin reranking; `rerank-2.5` o `rerank-2.5-lite` por API de Voyage, o `bge-reranker-v2-m3`, cross-encoder abierto BAAI/bge-reranker-v2-m3 que corre en CPU dentro del contenedor del núcleo) y `KERNA_RERANK_CANDIDATOS` (30). Con el modelo definido, el retriever pide 30 candidatos a Qdrant, los reordena (consulta = texto anonimizado, documento = `texto` del fragmento) y entrega los `top_k` primeros (8). El umbral de similitud sigue midiendo el coseno del embedding. Si el rerank falla, conserva el orden del embedding. La imagen del núcleo trae el modelo (`/opt/bge-reranker-v2-m3`, `KERNA_BGE_RUTA`) y `sentence-transformers` con torch CPU.
- Medición: `medir_rerank.py` (mapeo `concordancia`, 61 casos evaluables, IC pareado con semilla 20261110). Los rerankers abiertos corren en el job de Azure (`MODELOS=bge-reranker-v2-m3`, 4 vCPU, 8 GiB): `--accion preparar` deja los candidatos en `job_embeddings/datos/rerank_candidatos.json`, el job deja el orden en Qdrant (`normativa_cl_eval_rerank_<reranker>_<base>`) y `medir_rerank.py` lo lee.
- bge-reranker-v2-m3 sobre voyage-4-large (texto_original, 91 consultas con ley, top 30 a top 8): recall@5 por artículo 0,344 (base 0,393; diferencia -0,049, IC 95 % pareado [-0,164, 0,066]); hit@8 0,410 (igual); nDCG@10 0,207 (igual); MRR 0,189 (base 0,190). Techo (hit@30): 0,754. Tiempo de rerank por consulta: mediana 39,6 s, P95 40,2 s (CPU de 4 vCPU, 30 fragmentos de hasta 512 tokens). No mejora el recall y queda desactivado. La meta de recall@5 por artículo >= 0,80 no se alcanza: 0,393 con voyage-4-large (faltan 0,41), 0,344 con este reranker (faltan 0,46).
- Reranker de Voyage (`rerank-2.5`, `rerank-2.5-lite`): sin resultados. La cuenta gratuita (3 RPM, 10 K TPM) responde 429 siempre, porque una petición con 30 fragmentos supera los 10 K TPM.

## Agente evaluador LLM sobre el top 30

- Implementado en el núcleo (`nucleo/kerna_nucleo/evaluador.py`), apagado por defecto: `KERNA_EVALUADOR` (1/true para encender), `KERNA_EVALUADOR_CANDIDATOS` (30) y `KERNA_EVALUADOR_VARIANTE` (1 o 2). Con el evaluador encendido el retriever pide 30 candidatos; el orquestador, antes del agente final, envía la denuncia anonimizada y los candidatos al LLM, que responde por candidato `{id, aplica, confianza, hecho_citado, frase_articulo}`, y entrega los 8 primeros al agente final: los que aplican por confianza (desempate por orden del retriever) y, para completar, el resto en el orden del retriever.
- Guardias en código: solo ids de los candidatos; `hecho_citado` literal en la denuncia y `frase_articulo` literal en el artículo (ignora mayúsculas, espacios y comillas; con elipsis cada tramo debe ser literal), si no, la evaluación de ese candidato se descarta; JSON inválido, un reintento y luego se conserva el orden del retriever; "ninguno aplica" permitido. Sin caché ni registro del texto de la denuncia en el núcleo.
- Medición: `medir_evaluador.py` (voyage-4-large, 61 casos evaluables por artículo, mapeo `concordancia`, IC pareado con semilla 20261110). Solo los 61 casos con candidatos mapeables se envían al LLM; el resto no entra en las métricas por artículo.
- Resultado, variante de prompt 1, N = 30, una llamada por consulta (61 llamadas): recall@5 por artículo 0,393 -> 0,557 [0,426; 0,672]; diferencia pareada +0,164 [+0,066; +0,262]. hit@8 0,410 -> 0,557; nDCG@10 0,207 -> 0,404; MRR 0,190 -> 0,439. Meta 0,80: faltan 0,243; no se alcanza. El mismo valor que el mejor embedding (voyage-law-2, 0,557) pero aplicable sobre la colección de producción.
- Techo: con N = 30 el artículo candidato está entre los candidatos en el 75,4 % de los casos (hit@10 45,9 %, hit@50 88,5 %, hit@70 91,8 %, hit@100 96,7 %), así que con N = 30 la meta 0,80 es inalcanzable aunque el evaluador fuera perfecto; haría falta N >= 50. El evaluador recupera 0,557 de 0,754 (74 % de lo recuperable).
- Costo y tamaño: 12.978 tokens de entrada y 2.043 de salida por consulta; mediana de 4,9 s y P95 de 8,3 s por llamada. Costo en USD no calculado (precios de lista de Gemini sin verificar; el plan gratuito no cobra).
- Modelo: la cadena configurada (`gemini-3.8-flash` -> flash-lite -> gemma) no sirvió para medir: `gemini-3.8-flash` responde 503/429 y el plan gratuito de la clave limita a 20 peticiones por día y por modelo. Las 61 respuestas salieron de `gemini-3.5-flash-lite` (29), `gemini-3.1-flash-lite` (31) y `gemini-3-flash-preview` (1), con cuota agotada para el resto del día; mezcla de modelos pequeños, que puede subestimar lo que daría un modelo mayor.
- Sin medir: variante de prompt 2 y N = 50. Se intentó la variante 2 (5 respuestas de 61) y se detuvo: la cuota diaria de todos los modelos Gemini del plan gratuito estaba agotada y gemma-4-31b-it tarda decenas de segundos por llamada. Requiere una clave de pago de Gemini o un modelo en Azure (los modelos GPT del recurso `oai-kerna-dev` no tienen cuota regional asignada).
- Producción: ENCENDIDO con Azure OpenAI `gpt-5-nano` (despliegue GlobalStandard del recurso `oai-kerna-dev-g6mzy`, 250K TPM), N = 70 candidatos, variante 1, anonimizando antes de buscar y evaluar. Cadena del núcleo: `gpt-5-nano` (oficial, también clasificador) -> Gemini (respaldo). Plazo global 420 s y corte por llamada 150 s (`KERNA_PLAZO_GLOBAL_S`, `KERNA_CORTE_LLAMADA_S`). Proveedor `azure-openai` en `proveedores/azure_openai.py` (clave y endpoint desde Key Vault).
- Medición con gpt-5-nano (texto anonimizado, 61 casos): recall@5 por artículo 0,393 -> 0,426 (variante 1, N=70); variante 2 N=70 0,377; variante 1 N=50 0,377; sin anonimizar 0,410. nDCG@10 0,217 -> 0,267 y MRR 0,195 -> 0,295 (pareadas con IC sobre 0). No llega a 0,80. Menos que gemini-3.5-flash-lite en N=30 (0,557, sin anonimizar): nano marca pocos artículos como aplicables y se descartan muchas citas no literales. Costo real ~0,15 USD por corrida de 61 casos (~26.000 tokens de entrada por consulta).
- `gpt-5-mini` también está desplegado (50K TPM) y no se usa.
