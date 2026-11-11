# Informe de la prueba comparativa de embeddings

Generado por `comparar_embeddings.py` a partir de `registro/recall_retriever.jsonl`. Sin textos de denuncias.

## Método

- Dataset: `datos/denuncias_publicas.json`, sha256 `26c4bb1c98c1e490…`; consulta = `texto_original`.
- Mismo corpus (fragmentos sustantivos vigentes de la BCN) y mismo texto por fragmento (`texto_embedding`) en cada colección; coseno; filtro `vigente=true`; top 5 (nDCG@10 y MRR sobre el top 10); 1024 dimensiones salvo EmbeddingGemma (768) y `voyage-law-2` (1024 fijas).
- Métrica principal: recall@5 por **artículo** (algún artículo candidato en el top 5; se evalúan solo los casos con candidatos mapeables al corpus). Meta 0.80 por artículo; por ley es dato secundario. IC de 95 % por bootstrap de casos (2000 remuestreos, semilla 20261110). Los candidatos del dataset son alternativas aceptables, así que recall@5 y hit rate@5 coinciden.
- Pares: diferencia de recall@5 con IC bootstrap pareado (mismos casos y remuestreos).
- Regla: si la diferencia de recall@5 es < 0.05 o los intervalos se superponen, desempata nDCG@10, luego P95 de la consulta y luego costo.
- Modelos abiertos: calculados dentro de Azure (job `job-kerna-eval-embeddings`, CPU); sus P95 son de CPU de 4 vCPU y su costo es de cómputo, no por token. Los de API miden la latencia de una consulta por petición.

## Resultados por candidato (nivel artículo)

| Candidato | Tipo | Casos | recall@5 [IC 95 %] | nDCG@10 | MRR | P@5 | recall ley | P95 consulta (ms) | Tokens | Costo (USD) | ¿Meta? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| voyage-4-large | nube | 61 | 0.328 [0.213, 0.443] | 0.189 | 0.162 | 0.098 | 0.934 | 674 | 204575 | — | no |
| voyage-law-2 | nube | 61 | 0.508 [0.377, 0.639] | 0.363 | 0.375 | 0.131 | 0.901 | 1893 | 184195 | 0.0221 | no |
| asimétrica: corpus voyage-4-large, consultas voyage-4-lite | nube | 61 | 0.279 [0.164, 0.393] | 0.204 | 0.175 | 0.085 | 0.934 | 682 | 165660 | — | no |
| BGE-M3 | abierto | 61 | 0.311 [0.197, 0.426] | 0.160 | 0.182 | 0.066 | 0.692 | 29782 | 123079 | 0.1501 | no |
| EmbeddingGemma 300M (768 dims) | abierto | 61 | 0.246 [0.148, 0.361] | 0.173 | 0.157 | 0.056 | 0.780 | 8523 | 102608 | 0.0594 | no |
| multilingual-e5-large-instruct | abierto | 61 | 0.279 [0.180, 0.393] | 0.198 | 0.150 | 0.082 | 0.923 | 1419 | 48453 | 0.0208 | no |

### Por ley

| Candidato | Ley | Casos art. | recall@5 artículo | nDCG@10 | recall@5 ley |
|---|---|---|---|---|---|
| voyage-4-large | 19.628-21.719 | 23 | 0.217 | 0.156 | 1.000 |
| voyage-4-large | 20.393 | 10 | 0.000 | 0.000 | 0.792 |
| voyage-4-large | 21.643 | 28 | 0.536 | 0.284 | 0.966 |
| voyage-law-2 | 19.628-21.719 | 23 | 0.391 | 0.225 | 1.000 |
| voyage-law-2 | 20.393 | 10 | 0.200 | 0.067 | 0.708 |
| voyage-law-2 | 21.643 | 28 | 0.714 | 0.583 | 0.931 |
| asimétrica: corpus voyage-4-large, consultas voyage-4-lite | 19.628-21.719 | 23 | 0.174 | 0.194 | 0.974 |
| asimétrica: corpus voyage-4-large, consultas voyage-4-lite | 20.393 | 10 | 0.000 | 0.000 | 0.875 |
| asimétrica: corpus voyage-4-large, consultas voyage-4-lite | 21.643 | 28 | 0.464 | 0.286 | 0.931 |
| BGE-M3 | 19.628-21.719 | 23 | 0.435 | 0.217 | 0.974 |
| BGE-M3 | 20.393 | 10 | 0.000 | 0.000 | 0.125 |
| BGE-M3 | 21.643 | 28 | 0.321 | 0.170 | 0.793 |
| EmbeddingGemma 300M (768 dims) | 19.628-21.719 | 23 | 0.087 | 0.063 | 0.921 |
| EmbeddingGemma 300M (768 dims) | 20.393 | 10 | 0.000 | 0.000 | 0.667 |
| EmbeddingGemma 300M (768 dims) | 21.643 | 28 | 0.464 | 0.325 | 0.690 |
| multilingual-e5-large-instruct | 19.628-21.719 | 23 | 0.174 | 0.139 | 0.974 |
| multilingual-e5-large-instruct | 20.393 | 10 | 0.000 | 0.000 | 0.750 |
| multilingual-e5-large-instruct | 21.643 | 28 | 0.464 | 0.318 | 1.000 |

## Comparación por pares (recall@5 por artículo)

| A | B | Casos | A − B | IC 95 % pareado | ¿Diferencia significativa? |
|---|---|---|---|---|---|
| voyage-4-large | voyage-law-2 | 61 | -0.180 | [-0.311, -0.066] | sí |
| voyage-4-large | asimetrica | 61 | +0.049 | [-0.016, +0.115] | no |
| voyage-4-large | bge-m3 | 61 | +0.016 | [-0.148, +0.164] | no |
| voyage-4-large | embeddinggemma-300m | 61 | +0.082 | [-0.033, +0.213] | no |
| voyage-4-large | multilingual-e5-large-instruct | 61 | +0.049 | [-0.049, +0.148] | no |
| voyage-law-2 | asimetrica | 61 | +0.230 | [+0.115, +0.344] | sí |
| voyage-law-2 | bge-m3 | 61 | +0.197 | [+0.066, +0.328] | sí |
| voyage-law-2 | embeddinggemma-300m | 61 | +0.262 | [+0.164, +0.377] | sí |
| voyage-law-2 | multilingual-e5-large-instruct | 61 | +0.230 | [+0.115, +0.361] | sí |
| asimetrica | bge-m3 | 61 | -0.033 | [-0.180, +0.115] | no |
| asimetrica | embeddinggemma-300m | 61 | +0.033 | [-0.082, +0.148] | no |
| asimetrica | multilingual-e5-large-instruct | 61 | +0.000 | [-0.082, +0.082] | no |
| bge-m3 | embeddinggemma-300m | 61 | +0.066 | [-0.066, +0.197] | no |
| bge-m3 | multilingual-e5-large-instruct | 61 | +0.033 | [-0.115, +0.180] | no |
| embeddinggemma-300m | multilingual-e5-large-instruct | 61 | -0.033 | [-0.148, +0.082] | no |

## Decisión

- **Nube**: voyage-law-2 (recall@5 0.508).
- **Local** (el mejor de los abiertos, aunque gane uno de nube): multilingual-e5-large-instruct (recall@5 0.279).
- Ningún candidato llega a la meta de 0.80 por artículo (el mejor: 0.508): revisar primero el texto que se vectoriza por fragmento.

Criterios aplicados:
- voyage-law-2 vs voyage-4-large: gana voyage-law-2 por nDCG@10 (recall@5 sin diferencia decisiva)
- asimetrica vs voyage-law-2: gana voyage-law-2 por nDCG@10 (recall@5 sin diferencia decisiva)
- bge-m3 vs voyage-law-2: gana voyage-law-2 por nDCG@10 (recall@5 sin diferencia decisiva)
- embeddinggemma-300m vs voyage-law-2: gana voyage-law-2 por recall@5
- multilingual-e5-large-instruct vs voyage-law-2: gana voyage-law-2 por nDCG@10 (recall@5 sin diferencia decisiva)

Entre los abiertos:
- embeddinggemma-300m vs bge-m3: gana embeddinggemma-300m por nDCG@10 (recall@5 sin diferencia decisiva)
- multilingual-e5-large-instruct vs embeddinggemma-300m: gana multilingual-e5-large-instruct por nDCG@10 (recall@5 sin diferencia decisiva)

## Candidatos no medidos

- text-embedding-3-large (Azure OpenAI): sin corrida registrada para este campo.
- Qwen3-Embedding 8B: sin corrida registrada para este campo.
- Qwen3-Embedding 4B (solo si el 8B no cabe): sin corrida registrada para este campo.

Pendiente: convertir los puntajes medidos a la escala de 1 a 5 (Tabla 28) para revisar la Tabla 9.
