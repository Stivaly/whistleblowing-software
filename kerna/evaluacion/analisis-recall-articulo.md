# Análisis del recall@5 por artículo (PR-01)

Estado de la medición y de sus causas. Se calcula con `analisis_recall_articulo.py` (vectores ya guardados, coseno en memoria con el filtro `vigente=true`; reproduce al milésimo el recall registrado de cada candidato) y deja `datos/analisis_recall_articulo.json`. El informe comparativo es `informe-embeddings.md`. Consulta = `texto_original` salvo que se indique. Sin textos de denuncias.

## Resumen

- Ningún candidato llega a 0,80 por artículo. Con el mapeo corregido el mejor es `voyage-law-2` con 0,557 (antes 0,508); `voyage-4-large` pasa de 0,328 a 0,393.
- El texto por fragmento no es la única causa, y la mayor parte de la brecha no se cierra sin cambiar el corpus o la etiqueta:
  1. Solo 61 de los 91 casos con ley tienen algún artículo candidato en el corpus, y el 54 % de ellos (33 de 61) tiene un único candidato. Al azar se acertaría 6,4 %.
  2. Había un error de medición: el dataset cita la Ley 19.628 con la numeración previa a la Ley 21.719 y el corpus vigente trae el texto reformado. 17 de las 35 citas de esa ley apuntaban a otra materia (11 casos). Corregido con una concordancia.
  3. La Ley 20.393 (10 casos, 9 con el artículo 1 como único candidato) es inalcanzable por texto: el artículo 1 queda en los puestos 23 a 45 de 172 con `voyage-4-large` y 25 a 105 con `voyage-law-2`.
  4. Cuando falla, el top 5 trae otros artículos de la misma ley o de otra ley, casi nunca el vecino del candidato (4 a 11 %), y unos pocos fragmentos concentran los resultados (los 10 más frecuentes ocupan 37 % a 71 % del top 5 de las 113 consultas).
- Los cambios que no requieren re-vectorizar (fusión con BM25, centrado de vectores, enrutar por ley, k = 8 o 10) mueven el recall entre −0,08 y +0,20 según el modelo; ninguna combinación pasa de 0,66 (la meta es 0,80).

## 1. ¿Existen los candidatos en el corpus?

Corpus vigente: 145 fragmentos sustantivos (144 artículos; solo el artículo 2 de la Ley 19.628 va en dos partes), más 27 fragmentos no vigentes con vector (texto previo de la Ley 19.628, excluidos por el filtro). Sin vector hay 29 fragmentos no sustantivos (artículos modificatorios y promulgatorios).

| Ley del caso | Casos | Con candidato en el corpus | Citas (caso × artículo) | Citas en el corpus | Artículos distintos citados → en el corpus |
|---|---|---|---|---|---|
| 20.393 | 24 | 10 | 18 | 12 | 7 → 3 |
| 21.643 | 29 | 28 | 73 | 49 | 22 → 7 |
| 19.628-21.719 | 38 | 23 | 58 | 53 | 17 → 15 |
| Total | 91 | 61 (67 %) | 149 | 114 (77 %) | 46 → 25 |

Por qué 30 casos no se evalúan: 20 nombran la ley sin número de artículo (6 de la 20.393, 14 de la 19.628), 6 citan solo otros cuerpos (CP, Ley 19.913, Ley 19.496, Constitución, dictámenes), 4 citan artículos que el corpus no trae (el Código del Trabajo solo incluye los artículos que tocó la Ley Karin: 2, 154, 154 bis/ter, 211-A a 211-E; el dataset cita además, entre otros, 5, 22, 35, 41, 58, 63, 97, 153, 160, 161, 162, 177, 184, 420 y 485 a 489). Ninguna cita cae en los 29 fragmentos sin vector.

## 2. ¿El mapeo pierde o confunde artículos?

- El analizador (`citas_a_articulos`) es correcto en lo sintáctico: "CT 211-A a 211-C" se expande a tres artículos; "17-19", "485-489", letras (`a)`), incisos y numerales se descartan bien; un artículo partido en varias partes cuenta una vez (`articulo_de` quita `-pN`); Ley 21.595 no es parte del corpus. Revisadas las 91 filas, no hay citas mal leídas.
- Error real: **numeración de la Ley 19.628**. El dataset cita el texto previo (arts. 2, 4, 6, 7, 9, 10, 11, 12, 17 a 19) y el corpus vigente trae el texto reformado por la Ley 21.719, donde solo coinciden los artículos 2, 17, 18 y 19. El 10 era "datos sensibles" y hoy es "forma de ejercer los derechos" (sensibles: 16); el 11 era seguridad (hoy 14 quinquies); el 12 era el derecho de acceso y rectificación (hoy 4 a 7). 17 de las 35 citas de la Ley 19.628 (49 %) apuntaban a otra materia y afectaban a 11 de los 23 casos evaluables de esa ley.
- Corrección: `recall_retriever.py --mapeo concordancia` (por defecto) traduce cada número previo a los artículos del texto reformado que tratan la misma materia (`CONCORDANCIA_19628`, hecha leyendo los títulos de ambos textos). `--mapeo directo` conserva la definición anterior. Los dos mapeos dejan 61 casos evaluables.

| Candidato | recall@5 `directo` (antes) | recall@5 `concordancia` (después) | Resumen: antes → después |
|---|---|---|---|
| voyage-4-large | 0,328 | 0,393 | 0,344 → 0,393 |
| voyage-law-2 | 0,508 | 0,557 | 0,492 → 0,525 |
| text-embedding-3-large (Azure OpenAI) | 0,279 | 0,311 | 0,262 → 0,311 |
| asimétrica (consultas voyage-4-lite) | 0,279 | 0,328 | 0,377 → 0,426 |
| BGE-M3 | 0,311 | 0,311 | 0,246 → 0,279 |
| EmbeddingGemma 300M | 0,246 | 0,230 | 0,148 → 0,148 |
| multilingual-e5-large-instruct | 0,279 | 0,279 | 0,295 → 0,262 |

Por ley (concordancia, `voyage-law-2`): 21.643 0,714; 19.628 0,522; 20.393 0,200. Con `voyage-4-large`: 0,536; 0,391; 0,000.

## 3. ¿Son demasiado específicos los candidatos?

- Candidatos por caso: media 1,87, mediana 1; 33 de 61 casos tienen un solo artículo aceptable. Recall esperado al azar con 5 artículos de 144: 6,4 % global (4,1 % en la 20.393, 6,0 % en la 21.643, 7,8 % en la 19.628).
- Los fragmentos largos partidos no explican nada: solo un artículo de 144 se parte (límite de 5.000 caracteres). Largo mediano de los candidatos 1.613 caracteres, del corpus 1.207. Fracción de pares (caso, candidato) que llega al top 5 según el largo del artículo: `voyage-4-large` 0,36 (< 1.500), 0,36 (1.500 a 2.999), 0,17 (≥ 3.000); `voyage-law-2` 0,21, 0,40, 0,61. Sin tendencia común.
- Artículos concretos: Ley 20.393 art. 1 (9 casos) queda en los puestos 23 a 45 con `voyage-4-large` y 25 a 105 con `voyage-law-2` de 172; solo enumera delitos por referencia a otras leyes y no usa el vocabulario de una denuncia (coimas, facturas falsas, lavado). CT art. 2 (20 pares, 4.179 caracteres, mezcla acoso sexual, laboral y violencia de terceros): puestos 1 a 128 con `voyage-4-large` (mediana 13; 3 de 20 en el top 5) y 1 a 23 con `voyage-law-2` (13 de 20 en el top 5). Ley 19.628 art. 2 (definiciones, 8 pares, en dos partes): puestos 11 a 43 con `voyage-4-large`, 1 a 21 con `voyage-law-2`.

## 4. ¿Qué recupera el top 5 cuando falla?

Proporción de los artículos distintos del top 5 en los casos que fallan (`voyage-4-large` / `voyage-law-2` / `text-embedding-3-large`): artículo vecino del candidato (mismo número base o contiguo) 5 % / 10 % / 6 %; otro artículo de la ley correcta 70 % / 62 % / 59 %; artículo de otra ley 24 % / 28 % / 35 %. Es decir, acierta la ley (recall por ley 0,85 a 0,93) y no el artículo.

Concentración: los 10 fragmentos más frecuentes ocupan 37 % del top 5 de las 113 consultas con los modelos de Voyage, 47 % con Azure OpenAI, 53 % con BGE-M3, 61 % con e5 y 71 % con EmbeddingGemma. En los casos de acoso (Ley 21.643) dominan CT 211-D, 211-E, 211-B bis y la Ley 19.628 art. 43, 45 y 46 (procedimiento y responsabilidad del funcionario infractor, vocabulario genérico de "infracción", "funcionario", "denuncia").

## 5. Lectura de la métrica y k

La métrica principal (algún candidato en el top 5) es la más indulgente. Para el mismo candidato, `concordancia`:

| Candidato | hit@5 | hit@8 | hit@10 | cobertura@5 | cobertura@8 | cobertura@10 |
|---|---|---|---|---|---|---|
| voyage-4-large | 0,393 | 0,410 | 0,459 | 0,287 | 0,311 | 0,344 |
| voyage-law-2 | 0,557 | 0,607 | 0,656 | 0,389 | 0,477 | 0,536 |
| text-embedding-3-large | 0,311 | 0,328 | 0,361 | 0,199 | 0,249 | 0,291 |
| asimétrica | 0,328 | 0,459 | 0,492 | 0,238 | 0,336 | 0,358 |
| BGE-M3 | 0,311 | 0,377 | 0,410 | 0,178 | 0,235 | 0,268 |
| EmbeddingGemma 300M | 0,230 | 0,426 | 0,459 | 0,145 | 0,277 | 0,298 |
| multilingual-e5-large-instruct | 0,279 | 0,344 | 0,443 | 0,186 | 0,281 | 0,373 |

Con recall verdadero (cobertura, fracción de los candidatos hallados) la lectura empeora en 0,09 a 0,17 puntos. Con k = 8 (lo que entrega el núcleo) se gana de 0,02 a 0,20 y con k = 10 de 0,05 a 0,23, pero ninguno pasa de 0,66. `voyage-4-large` y Azure OpenAI casi no mejoran al pasar de 5 a 8 (+0,02); los que más ganan (EmbeddingGemma, asimétrica) parten de una posición baja.

## 6. Mejoras que no requieren re-vectorizar (exploratorio, 61 casos)

recall@5 por artículo con los vectores existentes:

| Candidato | Vector solo | BM25 léxico | RRF vector + BM25 | Vector centrado | Solo la ley correcta (oráculo) |
|---|---|---|---|---|---|
| voyage-4-large | 0,393 | 0,344 | 0,443 | 0,443 | 0,426 |
| voyage-law-2 | 0,557 | 0,344 | 0,574 | 0,475 | 0,623 |
| text-embedding-3-large | 0,311 | 0,344 | 0,311 | 0,393 | 0,393 |
| BGE-M3 | 0,311 | 0,344 | 0,344 | 0,311 | 0,443 |
| multilingual-e5-large-instruct | 0,279 | 0,344 | 0,361 | 0,311 | 0,311 |

Un BM25 sin modelos (0,344) iguala a los vectores salvo a `voyage-law-2`. Enrutar por la ley correcta sube entre 0,03 y 0,20 según el modelo (el mejor queda en 0,62: el fallo es sobre todo dentro de la ley). La fusión y el centrado cambian el recall entre −0,08 y +0,08 de forma irregular. Son complementos posibles del retriever, no la solución.

## 7. Propuesta para `texto_embedding` (no aplicada)

Hoy: `"{referencia} — {nombre}. {jerarquía} > Artículo N[ (parte i/n)]. {texto}"`. El texto ya empieza con "Artículo N.-", de modo que el número se repite, la referencia puede ser un código sin contenido ("DFL 1") y nada dice de qué trata el artículo en el lenguaje de una denuncia.

| Cambio | Por qué (observado) | Efecto esperado | Costo en Voyage (3 peticiones/min, 10.000 tokens/min) |
|---|---|---|---|
| A. Encabezado limpio: `Ley N (nombre corto) · Art. N · <título del artículo> · materias BCN`; sin "Artículo N" repetido ni "DFL 1" | Hubs genéricos (§4) y títulos que ya están en el texto pero diluidos en 1.200 caracteres | Pequeño; reduce hubs | Neutro: ~72.000 tokens, 11 peticiones, ~7 min por modelo |
| B. Resumen de materia por fragmento (2 a 3 líneas, ~420 caracteres, en el lenguaje de una denuncia: "quien pague coimas…", "acoso por parte de clientes…"), generado una vez al extraer, con su hash y revisión jurídica. Dos formas: B1 dentro del mismo texto; B2 como segundo punto del mismo `fragmento_id` (se agrega por máximo) | Art. 1 de la 20.393 (rango 23 a 105) y art. 2 del CT (mediana 14) no comparten vocabulario con la consulta; el 54 % de los casos tiene un solo candidato, así que un artículo que no se acerca no se compensa | Es la única palanca dirigida a las causas 3 y 4; magnitud no estimable sin medir | B1: ~90.000 tokens, 14 peticiones, ~9 min. B2: ~23.500 tokens, 4 peticiones, ~2,5 min. El resumen lo genera un LLM por API (145 fragmentos, centavos) |
| C. Partir artículos de más de 1.500 caracteres por inciso o letra, con encabezado y resumen repetidos y 150 caracteres de solapamiento | CT art. 2 mezcla tres conceptos; la Ley 19.628 art. 2 se parte en un punto arbitrario | Incierto: el largo no mostró efecto (§3); sube de 145 a ~211 fragmentos | ~80.000 tokens, ~13 peticiones, ~8 min |

Orden recomendado: probar A, A+B1, B2 y C sobre `text-embedding-3-large` (Azure OpenAI no tiene el límite de Voyage: ~1 minuto y ~0,01 USD por variante, en colecciones `normativa_cl_eval_*` aparte) y pasar a Voyage solo las ganadoras. Las 113 consultas no se vuelven a vectorizar (están en caché). Re-vectorizar el corpus con dos modelos de Voyage (`voyage-4-large`, `voyage-law-2`) cuesta, para A+B1, ~18 minutos de espera efectiva; los modelos abiertos requieren una pasada del job de Azure (~37 minutos para los tres).

Antes de elegir modelo conviene además: (1) revisión jurídica de 30 casos fallidos para saber cuántos de los artículos recuperados son relevantes aunque no estén etiquetados (el dataset fija un único candidato en 33 de 61 casos, así que 0,80 puede ser inalcanzable con esa etiqueta); (2) decidir qué texto de la Ley 19.628 mide el dataset (el reformado, vigente desde el 2026-12-01, o el previo, que rige hasta entonces); (3) ampliar el corpus con los artículos del Código del Trabajo y del Código Penal que el dataset cita, o excluir esos casos de la meta.

## Azure OpenAI

`embed_sync.py --proveedor azure-openai` falló por dos causas del lado del cliente, ambas corregidas en `pipeline_bcn/embed_sync.py`:

- Errores transitorios de red (DNS del servidor de desarrollo: `Temporary failure in name resolution`) que la función no reintentaba; ahora reintenta errores de red, timeouts y HTTP 5xx con espera creciente (HTTP 429 ya se reintentaba).
- Las consultas de `texto_original` pueden medir 30.000 caracteres y Azure OpenAI rechaza con HTTP 400 los textos de más de 8.191 tokens; ahora se recortan a 22.000 caracteres (Voyage trunca por defecto).

Con eso, la colección `normativa_cl_eval_text-embedding-3-large` quedó con 172 fragmentos (145 vigentes) a 1.024 dimensiones y se midió con ambos campos: `texto_original` 0,311 (antes de la concordancia 0,279) y `resumen_parafraseado` 0,311 (0,262). El P95 de consulta de ese candidato (15,8 s) está inflado por esperas de DNS en múltiplos de 5 s (mínimo 0,8 s): no es comparable con el de Voyage y debe repetirse desde Azure.
