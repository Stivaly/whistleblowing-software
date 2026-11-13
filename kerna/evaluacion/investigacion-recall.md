# Investigación: cómo subir recall@5 por artículo (2026-11-13)

Contexto: 3 leyes chilenas, 181 artículos, voyage-4-large + BM25 híbrido + multiconsulta + evaluador LLM + revisor.
Recall@5 por artículo hoy 0,55-0,64; hit@70 ≈ 0,97, es decir el cuello es el **orden**, no la cobertura.
Meta: ≥ 0,80. Fuentes: solo papers y documentación oficial. Las cifras son las leídas en la fuente; donde no pude
leer la tabla lo digo. Ningún resultado de otro idioma/corpus se traslada tal cual: hay que medirlo aquí.

## Hallazgos por técnica

### 1. Reranker LLM (listwise/pointwise) sobre el top-K del recuperador
- Fuentes: LegalMALR, 2026, <https://arxiv.org/html/2601.17692v1> (estatutos chinos, consultas de legos);
  Sun et al., *Is ChatGPT Good at Search?* (RankGPT), EMNLP 2023, <https://aclanthology.org/2023.emnlp-main.923/>;
  Taiwán LawFactsQA-TW, 2024, <https://arxiv.org/html/2410.11450>; RankZephyr, 2023, <https://arxiv.org/abs/2312.02724>.
- Resultado: LegalMALR, mismas 60 candidatas de un denso (Qwen3-Embedding-4B): reranker cross-encoder Qwen3-Reranker
  0,723 → reranker LLM zero-shot (Qwen-Max, lista JSON sin cadena de pensamiento) **0,810 recall@10** en STARD
  (+8,7 pts); en CSAID 0,553 → 0,633. Taiwán: reranking LLM (Breeze) sobre denso 0,348 → 0,472 recall@10 (humano).
  RankGPT/RankZephyr: listwise con modelos fuertes es competitivo con supervisados en BEIR (no pude leer las tablas).
- Aplicabilidad: **alta, y ya la tienen** (evaluador 3m). Lo que sugieren los papers es cambiar *cómo* se evalúa: ventana
  de ~30-40 candidatas, una sola pasada listwise con el *perfil de elementos* de cada artículo (no el texto completo) y
  salida de ranking, no de sí/no por artículo. Un LLM más fuerte pesa más que más candidatas.
- Costo/riesgo: medio (1 llamada por denuncia; riesgo de sesgo de posición → barajar y promediar 2 permutaciones).
- Medición: A/B del evaluador actual contra listwise-ranking con la misma lista, mismos sets, recall@5 y MRR.

### 2. Rerankers cross-encoder (voyage rerank-2.5, cohere rerank-3.5, bge-reranker-v2-m3)
- Fuentes: Voyage, *rerank-2.5*, 2025-08-11, <https://blog.voyageai.com/2025/08/11/rerank-2-5/> (NDCG@10 sobre 100
  candidatas): +7,94 % sobre Cohere Rerank v3.5, +1,85 % sobre rerank-2; **acepta instrucciones** en la consulta
  (+8,13 % en datasets de dominio, +11,48 % en reales), contexto 32 k. Docs: <https://docs.voyageai.com/docs/reranker>
  (hoy lista rerank-2.5 como legado y recomienda rerank-3). LegalBench-RAG, 2024, <https://arxiv.org/html/2408.10343v1>:
  Cohere general **no ayudó** (recall@64 61,06 % con reranker vs 62,22 % sin él, agregado) y en CUAD/ContractNLI empeoró.
  LegalMALR muestra que un cross-encoder (Qwen3-Reranker) queda 8 pts bajo un LLM listwise.
- Aplicabilidad: media. Voyage permite pasar la instrucción «los artículos aplicables a estos hechos, incluidos
  los de tipificación», útil para la 20.393; no hay cifras jurídicas propias de Voyage/bge-v2-m3 (no encontré papers).
- Costo: bajo (centavos por denuncia). Riesgo: el texto del artículo-lista largo diluye; el de LegalBench-RAG
  recuerda que un reranker genérico puede empeorar → solo adoptar si gana en nuestros sets.
- Medición: `recall_retriever.py` con rerank-2.5/rerank-3 sobre top-50 del híbrido, con y sin instrucción; también
  como filtro previo al LLM (50 → 20) para abaratar y dar mejor entrada al listwise.

### 3. Expansión de consulta (HyDE, query2doc, «el artículo que aplicaría»)
- Fuentes: HyDE, ACL 2023, <https://arxiv.org/abs/2212.10496> (cifras no leídas; afirma superar a Contriever y
  igualar a recuperadores afinados); query2doc, EMNLP 2023, <https://arxiv.org/html/2303.07678v2.pdf>: BM25 MRR@10
  18,4 → 21,4; DPR +1,4, E5+KD +0,8 MRR@10; baja en Scifact (−2,9); ganancias menguan con modelos fuertes. Taiwán
  (<https://arxiv.org/html/2410.11450>): sobre BGE-m3, generar **texto de artículo hipotético** (Statutory Article
  Expansion) 0,348 → 0,414-0,455 recall@10, mejor que expandir con una *respuesta* (0,359-0,430); en sintéticas
  0,469 → 0,578-0,615. Public Defenders, 2026, <https://arxiv.org/html/2601.14348>: en zero-shot ayuda a modelos
  pequeños y **perjudica a los grandes**.
- Aplicabilidad: **ya tienen multiconsulta con perfil/conductas** (variante 3m), que es esta técnica. Lo nuevo y
  respaldado es pedir explícitamente la redacción del artículo hipotético en lenguaje legal («tipifica...», «obliga
  a...») como consulta adicional, pesada junto al relato. Con voyage-4-large el techo es menor que con BGE-m3.
- Costo: bajo. Riesgo: alucinar números de artículo (usar solo el texto, no el número); ganancia pequeña con embedder fuerte.
- Medición: añadir una consulta «artículo hipotético» a multiconsulta; comparar recall@5 y hit@70.

### 4. Enriquecer los artículos (doc2query / contextual retrieval / preguntas sintéticas / conductas típicas)
- Fuentes: Anthropic, *Contextual Retrieval*, 2024, <https://www.anthropic.com/engineering/contextual-retrieval>:
  anteponer 50-100 tokens de contexto generados por LLM a cada fragmento: fallo top-20 5,7 % → 3,7 % (embeddings)
  → 2,9 % (+BM25) → 1,9 % (+reranker); 1,02 USD por millón de tokens de documento. JuriFindIT, EACL Findings 2026,
  <https://aclanthology.org/2026.findings-eacl.221.pdf> (según el resumen del buscador: una pregunta sintética por
  artículo es la mejor configuración y mejora BSARD; no pude leer las tablas). STARD, 2024,
  <https://arxiv.org/html/2406.15313v1>: consultas de legos sobre artículos son difíciles (R@5 0,52 con
  afinamiento humano). Public Defenders: la calidad del dato sintético decide.
- Aplicabilidad: **alta y es la que mejor encaja con el problema de 20.393 y artículos-lista**: cada artículo (o cada
  literal) lleva 3-6 «hechos típicos en lenguaje común» y la definición del tipo que lo activa. Se indexa para embedding
  y BM25 (campo aparte, así el texto legal sigue intacto). Es una vez por corpus (181 artículos): costo casi cero.
- Riesgo: contaminación si las descripciones se escriben mirando los casos de evaluación → escribirlas desde el texto
  legal solamente (regla de sesgo del relevo §0); el LLM puede inventar conductas ajenas al artículo (revisar a mano los
  arts. 1, 3, 4 de 20.393 y los de datos).
- Medición: `recall_retriever.py` con y sin campo enriquecido; foco en 20.393 (0,06-0,20) y datos.

### 5. Partir artículos-lista por literal (arts. 82/84 CT)
- Fuentes: LegalBench-RAG (<https://arxiv.org/html/2408.10343v1>) muestra que la estrategia de fragmentación mueve
  recall más que el reranker (RCTS vs ingenuo cambia sentido según dataset: no hay ganador universal); StrucChunk,
  2026, <https://arxiv.org/html/2610.26313> (fragmentación por estructura legal + BM25 + BGE-M3 + expansión de
  referencias cruzadas; cifras no leídas).
- Aplicabilidad: alta para 82/84 (13 literales). Cada literal como fragmento «hijo» que hereda el encabezado del
  artículo (contextual retrieval) y se agrega al artículo «padre» al devolver: el recall se mide por artículo.
- Costo: bajo (extractor); riesgo: más fragmentos pueden saturar el top-k con hermanos → deduplicar por artículo
  antes del evaluador (máx. 1 por artículo, quedarse con el mejor literal).
- Medición: recall de 82/84 antes/después; recall global y hit@70 para ver que no empeora el resto.

### 6. Recuperación jerárquica ley → artículo
- Fuentes: no hay papers que comparen «ley y luego artículo» frente a directo (la búsqueda no lo encontró);
  StrucChunk (arriba) usa estructura sección/capítulo. Domain-Partitioned Hybrid RAG for Legal Reasoning, 2026,
  <https://arxiv.org/pdf/2602.23371> (enrutado por dominio; evidencia débil, 70 % vs 37,5 % pass rate de un solo sistema).
- Aplicabilidad: con solo 3 leyes y 181 artículos el beneficio es pequeño; el problema (procedimiento sobre sustantivo
  dentro de la 20.393) es *dentro* de una ley. Más útil: una **etiqueta de rol** por artículo (sustantivo / sanción /
  procedimiento / definición) y una regla de diversidad por rol en la ventana del evaluador.
- Costo bajo, ganancia incierta. Medir solo si 1-5 no cierran 20.393.

### 7. Afinar embeddings con pares sintéticos hechos→artículo
- Fuentes: STARD (<https://arxiv.org/html/2406.15313v1>): afinar con ~1.000 pares reales R@100 0,649 (BM25) → 0,907;
  con datos sintéticos de GPT-4 (distilado) 0,798; afinar con otro estilo (CAIL formal) hunde a 0,328. Public Defenders:
  sintético ingenuo **−0,8 a −7,9** pts recall@5, sintético optimizado (generador afinado + filtro con reranker)
  **+2,6 a +5,2**. Bilingual BSARD/JuriFindIT apuntan a modestas ganancias.
- Aplicabilidad: **baja a corto plazo**: voyage-4-large es una API sin afinamiento propio; afinar un modelo abierto
  (bge-m3) implicaría host propio (regla: ningún modelo en el host). Y 181 artículos dan poca variedad. El valor está
  en reciclar las 150 sintéticas como **datos de few-shot / calibración**, no en entrenar embeddings.
- Riesgo: sobreajuste a los sets de evaluación. No recomendado ahora.

### 8. Fusión de rangos (RRF) y calibración
- Fuentes: comparaciones recientes (ej. <https://arxiv.org/html/2604.01733v1>) muestran RRF BM25+denso sobre ambos
  por separado; otro trabajo biomédico (<https://arxiv.org/pdf/2605.02520>) muestra que la fusión de pesos fijos no
  siempre gana al denso. No encontré cifras jurídicas.
- Aplicabilidad: ya hay híbrida; el cambio sería fusionar **todas las señales** (denso relato, denso perfil, denso
  artículo hipotético, BM25, rerank cross-encoder, puntaje del evaluador) con RRF o suma de rangos ponderada y
  ajustar pesos en desarrollo. Barato y sin llamadas nuevas.
- Medición: grid de pesos en desarrollo, congelar, medir en prueba/prueba2/prueba3.

### 9. Few-shot
- Fuentes: query2doc usa few-shot para generar pseudo-documentos (ver §3); COLIEE (NOWJ@COLIEE 2026,
  <https://arxiv.org/html/2607.16603>) combina denso + reranking por atención + razonamiento LLM few-shot (sin cifras leídas).
- Aplicabilidad: media. 3-5 ejemplos (relato → artículos con sus razones) por ley en el prompt del evaluador, tomados
  de casos **fuera** de los sets de medición (p. ej. 20 de las 150 sintéticas, excluidas luego de prueba3 y reportando
  sobre las restantes).
- Riesgo: fuga hacia el set; costo en tokens. Medición: evaluador con y sin ejemplos.

### 10. Clasificación multietiqueta supervisada como complemento
- Fuentes: PROSLEX, 2026, <https://arxiv.org/html/2608.08830v1> y NyayaRAG, 2025,
  <https://aclanthology.org/2025.ijcnlp-long.92.pdf> (quitar estatutos baja F1 63,96 → 57,53 en juicio multietiqueta).
  ILSIC, 2026, <https://arxiv.org/html/2602.00881>: afinar/RAG quedó bajo GPT-4.1 zero-shot en recall.
- Aplicabilidad: baja con ~100 casos etiquetados y 181 clases (≈ 1 ejemplo por clase). Solo un clasificador **por ley**
  (3 etiquetas) sirve como prior para el recuperador. No priorizar.

## Priorización (ganancia esperada / costo)

| # | Técnica | Ganancia esperada recall@5 | Costo | Riesgo | Prioridad |
|---|---|---|---|---|---|
| 1 | Enriquecer artículos con conductas típicas + contexto (técnica 4) y partir 82/84 por literal (5) | +0,05 a +0,10; sobre todo 20.393 y listas | bajo, único por corpus | medio (contaminación) | 1 |
| 2 | Reranker listwise LLM más fuerte sobre 30-40 candidatas, con perfil de artículo (1) | +0,05 a +0,10 (LegalMALR +8,7 pts R@10 frente a cross-encoder) | medio | bajo | 2 |
| 3 | Cross-encoder Voyage con instrucción como prefiltro 50 → 20 (2) | +0,02 a +0,05, o ahorro sin pérdida | bajo | medio (LegalBench-RAG) | 3 |
| 4 | Fusión RRF multiseñal con pesos ajustados (8) | +0,02 a +0,04 | muy bajo | bajo | 4 |
| 5 | Consulta «artículo hipotético» (3) | +0,01 a +0,04 (Taiwán +5 a +11 pts con BGE-m3; menos con embedder fuerte) | bajo | bajo | 5 |
| 6 | Few-shot del evaluador (9) | +0,01 a +0,05 | bajo-medio | fuga | 6 |
| 7 | Rol por artículo / diversidad (6) | incierta; 20.393 | bajo | bajo | condicional |
| 8 | Afinar embeddings (7), clasificador multietiqueta (10) | incierta, posible pérdida | alto | alto | no ahora |

Las ganancias son estimaciones mías a partir de las cifras citadas en otros corpus, no resultados medidos aquí.
Límite honesto: ninguna técnica sola lleva de 0,6 a 0,8; la meta exige combinar 1 + 2 + 3 + 4.

## Plan de 5 experimentos, en orden

Todos: sets desarrollo/prueba/prueba2/prueba3, etiqueta corregida, recall@5 por artículo, hit@70, MRR; registrar en
`registro-pruebas.md`; congelar decisiones en desarrollo y medir una vez en los demás.

1. **Línea base actual** (cadena 3m + híbrida + multiconsulta) repetida con corpus de 181, en los 4 sets; sirve de
   referencia y de IC. Sin código nuevo.
2. **Enriquecimiento de artículos** (3-6 hechos típicos en lenguaje común + rol + contexto de la ley, escritos desde el
   texto legal) como campo indexado aparte (embedding + BM25) y **partir 82/84 por literal** con deduplicación por
   artículo. Medir solo el retriever (`recall_retriever.py`) y 20.393/82/84.
3. **Reranker listwise** del evaluador: 30-40 candidatas, perfil de artículo, ranking de salida, 2 permutaciones;
   comparar contra el evaluador sí/no actual, con gpt-5-nano y gpt-5-mini (justifica el mini solo si gana).
4. **Cross-encoder Voyage (rerank-2.5/rerank-3) con instrucción** como prefiltro 50 → 20 antes del listwise, y como
   señal en una **fusión RRF** con pesos ajustados en desarrollo.
5. **Consulta «artículo hipotético» + few-shot** (ejemplos sacados de las sintéticas y excluidos del reporte), y solo
   si 20.393 sigue bajo 0,5, la regla de diversidad por rol.
