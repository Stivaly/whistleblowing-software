# Alternativas para subir el recall@5 por artículo

Estado actual de las opciones evaluadas sobre el papel; ninguna está implementada ni medida. Base: `informe-embeddings.md` y `analisis-recall-articulo.md`. Ningún modelo corre en el host: todo por API o job de Azure.

## Punto de partida

- Recuperación hoy (`nucleo/kerna_nucleo/retriever.py`): embedding de la consulta (Voyage) + búsqueda vectorial en Qdrant, `top_k` = 8, filtro `vigente`; respaldo en servicio local. Luego el orquestador (`orquestador.py`) pasa los fragmentos a una cadena de LLM (Gemini) que clasifica y genera.
- Corpus: 145 fragmentos vigentes, ~72.000 tokens en total (cabe entero en el contexto de un LLM, y es estable, por lo que admite caché de prompt). 226 consultas (113 casos x 2 textos); 61 casos evaluables por artículo; 33 de ellos con un único candidato.
- Mejor embedding: `voyage-law-2` 0,557 [0,426; 0,689]. Meta 0,80. Ya medido sin re-vectorizar: BM25+RRF 0,574 (law-2) y 0,443 (voyage-4-large); enrutar por ley (oráculo) hasta 0,623; variantes de texto A y A+B (resumen) con text-embedding-3-large: 0,344 y 0,295 (no significativas).
- El fallo es dentro de la ley (acierta la ley 85-93 %, no el artículo), con artículos "hub" genéricos y artículos sin vocabulario de denuncia (Ley 20.393 art. 1, CT art. 2).
- Techo de la medición, independiente del método: 30 de 91 casos no son evaluables y los candidatos son un único artículo en 54 % de los casos, así que un sistema que sugiere artículos jurídicamente válidos pero no etiquetados cuenta como fallo. Cualquier mejora debe leerse junto con la revisión jurídica de 30 casos fallidos (pendiente en `analisis-recall-articulo.md` §7).

## Cuadro comparativo

Costos: USD por consulta, orden de magnitud, con ~300 tokens de consulta anonimizada. Los precios de LLM de Gemini no están verificados aquí (revisar la lista de precios vigente antes de decidir); los de rerank salen de búsqueda web (ver fuentes). Azure for Students: crédito fijo pequeño; los costos por consulta de abajo son despreciables frente al crédito para 226 consultas por corrida (centavos a pocos dólares), lo que limita es la cuota/rate limit (Voyage 3 peticiones/min en plan gratuito) y los modelos disponibles en la suscripción, no el precio.

| # | Alternativa | Costo por consulta | Latencia añadida (P95 SLA 15 s) | Esfuerzo | Ayuda a... |
|---|---|---|---|---|---|
| 1 | Clasificación directa por LLM con el catálogo en contexto | ~72k tokens de entrada: con Gemini flash-lite, del orden de 0,005-0,02 USD sin caché y ~10x menos con caché; con un modelo grande, 0,1-0,3 USD | 3-10 s (una llamada larga); riesgo en P95 si el modelo es grande | Bajo-medio: nuevo prompt + validar que cada id exista en el corpus; reutiliza el enrutador | Fallo dentro de la ley, artículos sin vocabulario |
| 2 | Reranker cross-encoder sobre top 20-30 (Voyage rerank-2.5, Cohere rerank 3.5) | Voyage rerank-2.5: 0,05 USD por millón de tokens (~0,0025 USD por petición de 100 documentos según su página); Cohere 3.5: ~2 USD por 1.000 búsquedas (fuente de terceros) | 0,3-1 s | Bajo: un paso entre `buscar` y `_armar`; subir `top_k` de recuperación a 30 | Reordenar cuando el artículo está en el top 10-30 |
| 3 | Búsqueda híbrida BM25 + denso con RRF | Sin costo de API (BM25 en memoria sobre 145 fragmentos) | <50 ms | Bajo: ya hay una implementación exploratoria; falta llevarla al retriever (Qdrant admite vectores dispersos o BM25 aparte) | Ganancia pequeña medida: +0,017 (law-2) a +0,05 |
| 4 | Expansión/reescritura de consulta con LLM (extraer hechos y conductas jurídicas; HyDE; multi-query) | Una llamada corta (~500 tokens de salida): ~0,0005-0,002 USD con modelo pequeño, más N embeddings | +1-3 s (una llamada; multi-query en paralelo) | Bajo-medio: paso previo en el orquestador; el texto de la denuncia sigue solo en memoria | Cierra la brecha de vocabulario denuncia vs. norma |
| 5 | Indexar por supuesto de hecho (resúmenes, preguntas generadas por artículo) | Una vez: 145 llamadas; luego igual que hoy | 0 | Ya probado en una forma (variante B, resumen en el mismo vector): sin mejora. Falta probar preguntas hipotéticas como puntos separados con agregación por máximo (B2) | Artículos sin vocabulario de denuncia |
| 6 | Retrieval jerárquico ley -> artículo | Un clasificador ley (LLM pequeño o el mismo embedding): ~0,001 USD | +0,5-2 s | Bajo-medio | Oráculo por ley: +0,03 a +0,20; techo 0,62 con law-2 |
| 7 | Agentic RAG (agente que itera búsquedas y verifica) | 3-6 llamadas LLM + embeddings: 0,01-0,1 USD | 10-30 s: no cabe en el P95 salvo con límite de 2 iteraciones | Alto: bucle, herramientas, control de costo y de tiempo | Casos multi-conducta |
| 8 | Grafo de referencias entre artículos | Sin costo por consulta | <10 ms | Medio: extraer remisiones del texto ("conforme al artículo X") de los 145 fragmentos; poco denso en este corpus | Hubs y artículos vecinos; la Ley 20.393 art. 1 remite a otras leyes que no están en el corpus |
| 9 | Fine-tuning de embeddings | Entrenamiento: horas de GPU en job de Azure; luego igual que hoy | 0 | Alto, y sin datos suficientes: 61 casos evaluables (hay que separar entrenamiento y prueba) | Poco viable con este volumen |

## Detalle por alternativa

### 1. Clasificación directa por LLM con el catálogo en contexto

- Idea: en vez de recuperar, poner los 145 fragmentos (o solo ley + artículo + título + resumen, unos 15-25k tokens) en el prompt y pedir al LLM los artículos aplicables con su justificación, con salida de esquema JSON restringida a ids válidos.
- Por qué ayudaría: elimina la brecha de vocabulario y el efecto hub; el modelo razona sobre el supuesto de hecho. Es lo que el flujo ya hace en el paso siguiente, pero hoy solo ve 8 fragmentos que el embedding eligió mal (recall@8 de 0,41-0,61).
- Variante barata: catálogo compacto (título + resumen de materia ya generado en `datos/resumenes_materia.json`) y luego el texto completo solo de los candidatos.
- Latencia: una llamada con 20-70k tokens de entrada en modelos flash tarda 2-8 s; cabe en 15 s con margen si la cadena existente no encadena varias llamadas largas. Medir P95 desde Azure.
- Evidencia: en recuperación legal con corpus pequeño y definido, los LLM con contexto largo igualan o superan a la recuperación densa en tareas de clasificación (ver LegalBench, tareas de aplicación de reglas); en LegalBench-RAG el cuello de botella es la recuperación de fragmentos precisos en corpus grandes, que aquí no aplica. Pérdida conocida: sesgo de posición en contexto largo; mitigar barajando el orden en dos pasadas o dividiendo el catálogo por ley.
- Riesgo: alucina artículos que no existen (validar contra el corpus, `validador.py` ya existe) y el costo escala con el catálogo si crece (CT, CP completos).

### 2. Reranker cross-encoder

- Idea: recuperar 20-30 con embedding+BM25 y reordenar con un cross-encoder que lee consulta y artículo juntos.
- Ayuda: los candidatos están en el top 10 más a menudo que en el top 5 (law-2: 0,557 -> 0,656 en hit@10); un reranker que mueva ese 10 % al top 5 es la mejora más barata. No ayuda si el artículo está más allá del puesto 30 (Ley 20.393 art. 1: puestos 23-105).
- Modelos: Voyage rerank-2.5 / 2.5-lite (32k de contexto, admite instrucciones, disponible también en el catálogo de Azure AI), Cohere rerank 3.5. Los artículos largos (hasta ~4.000 caracteres) caben.
- Evidencia: en LegalBench-RAG (Pipitone y Alami, 2024) se midió Cohere rerank con text-embedding-3-large; una síntesis secundaria afirma que el reranker genérico puede empeorar la precisión en el dominio legal (no verificado contra el artículo). En COLIEE los rerankers cross-encoder mejoran sobre BM25 cuando se afinan al dominio, pero BERT genérico puede quedar por debajo de BM25 (LeiBi, COLIEE 2022). Conclusión: probar, no suponer.

### 3. Híbrido BM25 + denso con RRF

- Ya medido (§6 de `analisis-recall-articulo.md`): +0,02 a +0,05. Se mantiene como componente barato del candidato de entrada a los pasos 2 y 4, no como solución. En COLIEE la combinación léxico + semántico es la práctica común (nigam@COLIEE-22, sección-weighted hybrid 2026) y un BM25 solo es una base difícil de superar, igual que aquí (0,344).

### 4. Expansión y reescritura de consulta

- HyDE: el LLM escribe el "artículo ideal" o el párrafo normativo que aplicaría; se vectoriza eso en lugar de la denuncia (simetriza lenguaje). Multi-query: 3-5 reformulaciones por conducta jurídica (p. ej. "acoso laboral por superior jerárquico", "tratamiento de datos sin consentimiento", "soborno a funcionario"), unión de resultados con RRF.
- Extraer hechos -> conductas jurídicas -> consulta por cada conducta: es el cambio que más ataca el caso de la Ley 20.393, porque nombra los delitos base (cohecho, lavado de activos) que sí aparecen en el vocabulario de la denuncia y en el texto del artículo.
- Evidencia: HyDE (Gao et al., 2022) mejora la recuperación sin datos de entrenamiento; multi-query y reformulación guiada por razonamiento ayudan en consultas largas y con jerga distinta. Hay que cuidar que el LLM no inyecte hechos: la consulta reescrita no debe persistirse (cifrado / solo memoria).

### 5. Indexar por supuesto de hecho

- La variante A+B (resumen de materia dentro del mismo vector) no subió el recall@5 (0,295 vs. 0,311) aunque sí nDCG@10 y cobertura@5. Falta probar: preguntas hipotéticas por artículo (3-5 consultas sintéticas que un denunciante haría) como puntos aparte con agregación por máximo, y generadas con revisión jurídica. Efecto esperado moderado; barato de probar con un solo modelo (text-embedding-3-large, ~1 minuto, ~0,01 USD por variante).

### 6. Jerárquico ley -> artículo

- Acierta la ley ya en 85-93 %. Pre-filtrar por ley (clasificador LLM o por embeddings a nivel ley) y buscar el artículo dentro: techo medido con oráculo 0,623 (law-2). Por sí sola no alcanza; combinada con 1 o 2 reduce el catálogo que ve el LLM (menos tokens, menos sesgo de posición).

### 7. Agentic RAG

- Un agente que busca, lee, vuelve a buscar y verifica sube el recall en consultas con varias conductas, pero con SLA P95 de 15 s solo cabe con máximo 2 iteraciones y un modelo rápido. Hasta no agotar 1, 2 y 4 el costo en complejidad y latencia no se justifica. Evidencia en COLIEE 2026 (NOWJ): pipelines de varias etapas (filtro, denso, reranker generativo, clasificador) son los competitivos, pero en recuperación de casos, no de artículos.

### 8. Grafo de referencias

- Útil para expandir un artículo recuperado a los que remite o lo remiten (p. ej. CT 211-A ... 211-E, Ley 20.393 art. 1 -> delitos de otras leyes). Costo por consulta nulo, pero el corpus actual no incluye las leyes remitidas y los fallos son por vocabulario, no por falta de vecinos (solo 4-11 % del top 5 que falla son vecinos del candidato). Prioridad baja.

### 9. Fine-tuning de embeddings

- Con 61 casos evaluables y 1,87 candidatos por caso hay unos 114 pares: insuficiente para ajustar un modelo y además agota el set de prueba. Datos sintéticos (preguntas generadas por artículo, punto 5) permitirían entrenar sin tocar los casos reales, pero requiere un job de GPU en Azure y es el último recurso. En legal retrieval los embeddings afinados con pares sintéticos suelen ganar varios puntos (práctica general), sin garantía aquí.

## Recomendación: orden de prueba

Todas las pruebas usan las 226 consultas ya guardadas, el mapeo `concordancia` y el mismo cálculo de `recall_retriever.py` (recall@5 por artículo, IC 95 % bootstrap pareado contra `voyage-law-2` base 0,557), y se registran en `registro/recall_retriever.jsonl` con fecha, commit y parámetros. Para los pasos con LLM: temperatura 0, modelo fijo, y registrar tokens y P95 desde Azure.

1. LLM con catálogo compacto en contexto (alt. 1), usando título + resumen de materia por fragmento y devolviendo hasta 5 ids ordenados. Es la que más puede acercarse a 0,80, es la más simple (una llamada) y tiene la medición más limpia: recall@5 sobre los ids devueltos. Medir también con catálogo completo (72k tokens) y con orden barajado para estimar el sesgo de posición.
2. Reranker sobre top 30 de `voyage-law-2` + BM25 (alt. 2 + 3). Dos modelos (Voyage rerank-2.5 y Cohere 3.5), comparar contra el LLM de 1; si el hit@30 es alto y el reranker lo sube a 0,70+, es la ruta más barata y rápida.
3. Reescritura por conductas jurídicas + multi-query (alt. 4) delante del retriever existente, fusionando con RRF. Mide si el recuperador mejora por sí solo; combinable con 2.
4. Pre-filtro por ley (alt. 6) como reductor del catálogo para 1 y 2.
5. Preguntas hipotéticas por artículo (alt. 5, B2) solo si 1-3 no llegan.
6. Agentic, grafo y fine-tuning: solo si lo anterior deja casos concretos sin resolver.

Criterios de decisión: pasa quien suba recall@5 por artículo >= 0,05 con IC pareado que excluya 0, con P95 de extremo a extremo (retrieval + LLM de clasificación existente) < 15 s medido desde Azure y costo por consulta registrado. Antes de interpretar cualquier resultado, hacer la revisión jurídica de los casos fallidos y decidir qué texto de la Ley 19.628 mide el dataset, porque el techo de 0,80 puede depender de la etiqueta y no del método.

## Fuentes

- LegalBench-RAG (Pipitone y Alami, 2024): https://arxiv.org/abs/2408.10343
- COLIEE 2022, nigam: https://arxiv.org/pdf/2204.07853
- COLIEE 2022, LeiBi: https://arxiv.org/pdf/2205.13351
- COLIEE 2026, NOWJ: https://arxiv.org/pdf/2607.16603
- Precios de rerank (Voyage): https://docs.voyageai.com/pricing ; Cohere (tercero, sin verificar): https://apicostcalc.com/cohere-vs-voyage-vs-jina-rerank-cost-calculator.html
- HyDE (Gao et al., 2022), RRF (Cormack et al., 2009): de conocimiento previo, no consultados en esta sesión.
- Costos de LLM (Gemini) y Azure for Students: órdenes de magnitud sin verificar.
