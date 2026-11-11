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

- Qwen3-Embedding 8B: sin corrida registrada para este campo.
- Qwen3-Embedding 4B (solo si el 8B no cabe): sin corrida registrada para este campo.

Pendiente: convertir los puntajes medidos a la escala de 1 a 5 (Tabla 28) para revisar la Tabla 9.
