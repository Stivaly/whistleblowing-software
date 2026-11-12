# Revisor jurídico de Kerna: diseño

Estado: implementado detrás de `KERNA_REVISOR` (apagado por defecto), medido. Fecha: 2026-11-12.

## 1. Decisión: tercer agente, no repartir entre los dos actuales

La cadena tiene hoy dos agentes LLM después del retriever:

| Agente | Archivo | Trabajo | Sesgo deseado |
|---|---|---|---|
| Evaluador por IDs (variante 3) | `kerna/nucleo/kerna_nucleo/evaluador_ids.py` | Filtra y reordena 30–70 candidatos a top_k | Generoso: maximizar recall@5 |
| Generador | `prompts.SISTEMA_GENERADOR` | Elige ≤ 5 artículos, explica y cita | Redactar sin lenguaje resolutivo |

Se crea un **tercero, el revisor jurídico**, entre el generador y `validador.py`, porque:

1. **Objetivos opuestos.** El evaluador debe dejar pasar ante la duda (su meta es recall). Un revisor estricto dentro del
   evaluador bajaría el recall@5, que es el KPI obligatorio (0,80). Separados, cada uno se ajusta y mide por su lado.
2. **Contexto distinto.** El evaluador ve 70 candidatos con frases numeradas y usa `gpt-5-nano` por costo. El revisor ve
   solo ≤ 5 artículos, pero necesita conocimiento de ámbito, vigencia y sujeto de cada ley: cabe un modelo mejor.
3. **Medible aparte.** Su efecto se mide como precisión y como "no rompe recall" (ver §5), sin tocar las métricas del
   evaluador ya registradas.
4. **Falla segura.** Si el revisor falla o se agota el plazo, se entregan las sugerencias del generador marcadas
   "sin revisión jurídica" (mismo patrón que `_evaluar`).

Regla de oro del revisor: **anota antes que eliminar**. Solo veta un artículo con causal explícita de la lista §3.2; en
lo demás ajusta la confianza y agrega condiciones y alertas para el auditor.

## 2. Qué se sacó del Excel (solo características, no relatos)

Fuente: `kerna/evaluacion/datos/denuncias_publicas.xlsx`, hoja `casos`, 77 casos jurídicos (57 fallos, 15 noticias
CIPER, 3 DT, 2 CPLT); se excluyen los 36 de Reddit. Columnas usadas: `ley_principal`, `leyes_secundarias`,
`articulos_candidatos`, `submateria`, `rol_denunciante`, `es_caso_frontera`, `por_que_frontera`,
`resolucion_conocida`. No se leyó `texto_original`.

- Reparto: 25 datos personales, 22 Ley Karin, 22 Ley 20.393, 8 "ninguna" (controles de falso positivo). 32 de 77 son
  casos frontera. Rol del denunciante: desconocido 33, víctima 29, trabajador 8, testigo 5, cliente 2.
- Las fronteras se agrupan en **dimensiones de revisión** recurrentes; estas, y no los casos, alimentan al revisor:

| Dimensión | Patrón observado en las fronteras (generalizado) |
|---|---|
| Ámbito subjetivo / régimen | Relación estatutaria (FF.AA., Carabineros, funcionarios con estatuto propio, municipales) donde el CT no rige o rige solo por remisión; educación superior y escolar con leyes propias (21.369, convivencia escolar). |
| Sujeto responsable (20.393) | El imputado es persona natural o funcionario (malversación, cohecho de un juez, fraude al fisco de un parlamentario): la 20.393 exige persona jurídica que se beneficie y falla del modelo de prevención. |
| Naturaleza del procedimiento | Sanción administrativa (UAF, SMA, CPLT) vs. delito; tutela laboral general vs. procedimiento Ley Karin; conflicto colectivo/sindical vs. acoso individual; despido disciplinario o por necesidades de la empresa sin acoso. |
| Vigencia temporal | Hechos anteriores a la Ley Karin (1-ago-2024: antes se exigía reiteración); texto anterior de la 19.628 vs. texto reformado por la 21.719 (vigencia 1-dic-2026); ampliación de delitos base por la Ley 21.595. |
| Territorialidad | Hechos principales en el extranjero; relevancia chilena indirecta. |
| Posición del afectado | La empresa es la afectada o quien quiere tratar datos; no hay titular de datos afectado; conflicto vecinal entre particulares. |
| Norma aplicable fuera del corpus | Gran parte de lo citado es Código Penal (248–251 bis, 468, 470), Ley 19.913, Código Tributario 97 N°4, estatutos administrativos, Ley 20.285, Ley 19.496: el corpus solo tiene 20.393, 21.643 (+ CT modificado y estatutos públicos) y la 19.628 en su texto reformado por la 21.719 (la ley nueva de datos). |
| Ponderación de derechos | Transparencia vs. datos personales con criterios opuestos según el caso: no hay respuesta binaria, corresponde "requiere ponderación". |

Control de sesgo: el revisor **no recibe** casos, ids, resúmenes ni resoluciones del Excel. Sus criterios se redactan
desde el texto de las leyes (artículos de ámbito, definiciones, vigencias) y sus ejemplos son inventados, como ya hace
`evaluador_ids._EJEMPLOS`. La tabla de arriba solo dice *qué dimensiones* revisar; queda en este documento y nunca en
un prompt. Como las dimensiones salieron del mismo set, el set ya no es ciego para el diseño: ver §5.3.

## 3. Especificación del revisor

### 3.1 Entrada y salida

Entrada: hechos H1..Hn (la misma segmentación de `evaluador_ids.segmentar_hechos`, ya anonimizada), perfil extraído por
el evaluador (conductas, partes, relación laboral, datos personales, posibles delitos) y las ≤ 5 sugerencias del
generador con el texto completo de su artículo segmentado en frases A<k>.<j>. Fecha de los hechos si la denuncia la
trae (campo opcional; nunca inferida).

Salida (JSON schema estricto, por IDs, sin copiar texto):

```json
{"revisiones":[{"candidato":"A1","dictamen":"confirma|condiciona|veta",
  "causal_veto":null,"condiciones":["ambito_regimen","vigencia","sujeto",...],
  "hecho_ids":["H2"],"frase_ids":["A1.3"],"confianza_ajustada":0.0-1.0}],
 "alertas":["fuera_de_corpus:penal","fuera_de_corpus:administrativo","requiere_ponderacion",
            "hechos_insuficientes","posible_otra_via"]}
```

Las guardias en código son las de `evaluador_ids` (IDs existentes, frases del propio candidato; un veto sin causal ni
hecho se convierte en "condiciona").

### 3.2 Causales de veto (lista cerrada)

1. El régimen de la relación excluye la norma (p. ej. CT a relación estatutaria sin remisión expresa).
2. Falta el sujeto que la norma exige (20.393 sin persona jurídica beneficiada).
3. Los hechos son anteriores a la vigencia del texto citado y la norma no es retroactiva.
4. La conducta descrita es de otra naturaleza que el supuesto del artículo (despido por necesidades de la empresa
   presentado como acoso, sin hechos de acoso).
5. Los hechos ocurren íntegramente fuera de Chile sin conexión con la persona jurídica chilena.

Todo lo demás es "condiciona" con su condición, para que el auditor decida.

### 3.3 "Skills": conocimiento por ley, cargado según los candidatos

En vez de un prompt monolítico, un archivo de criterios por familia normativa en
`kerna/nucleo/kerna_nucleo/revisor/criterios/`, versionado y con revisión de un abogado:

- `ley_karin.md` — ámbito (CT, remisiones a estatutos), definiciones del art. 2 (un solo acto basta desde 2024),
  211-A a 211-E (protocolo, medidas de resguardo, plazos, rol de la DT), diferencia con tutela 485 y con conflictos
  colectivos, vigencia 1-ago-2024.
- `ley_20393.md` — requisitos de imputación (delito base del catálogo, interés o provecho de la persona jurídica,
  falla del modelo de prevención), catálogo ampliado por la 21.595, canal de denuncias del modelo, persona natural vs.
  jurídica.
- `datos_personales.md` — Ley 19.628 reformada por la 21.719 (ley nueva de datos; el corpus solo trae el texto
  reformado, vigente desde 1-dic-2026) y la fecha de corte, dato sensible, consentimiento, derechos del titular,
  deberes de seguridad, relación con 20.285 y con CT 154 ter / videovigilancia laboral.
- `transversal.md` — causales §3.2, lenguaje no resolutivo, lista de normas fuera del corpus que se señalan como alerta.

Se cargan solo los archivos de las leyes presentes entre los candidatos (divulgación progresiva: menos tokens y menos
distracción). Es el mismo principio que las skills de Claude, implementado como texto en el prompt porque el núcleo
llama a modelos por API, no a Claude Code.

## 4. Qué falta según el material RAG (y qué ya está)

| Estrategia del material | En Kerna hoy | Qué hacer | Prioridad |
|---|---|---|---|
| Densa + umbral + top-k | Sí (Voyage, Qdrant) | — | — |
| Validación de citas / grounding | Sí (`validador.py`, citas por ID) | — | — |
| Inyección de prompt indirecta | Sí (delimitación de datos) | Repetir en el revisor | — |
| CRAG / evaluador | Sí (evaluador por IDs) | El revisor completa el lazo correctivo | Alta |
| **Búsqueda híbrida BM25 + RRF** | No | Los denunciantes no nombran leyes; BM25 aporta por términos concretos del relato que coinciden con el texto legal (licencia, cotizaciones, cámaras, factura, soborno) y que el embedding diluye en relatos largos, y suma candidatos distintos para el evaluador. RRF no requiere calibrar α. | Alta |
| **Reescritura / multi-query por conducta** | No (el perfil de conductas existe, pero no se usa para buscar) | Buscar también con cada conducta del perfil y fusionar con RRF | Alta |
| CAG / catálogo completo | No | Descartado: el corpus crecerá. Al LLM se le envían solo las leyes en juego con sus artículos. | — |
| **Metadatos y filtros** | Parcial | Agregar `vigente_desde`/`vigente_hasta` y `ambito` por fragmento; el revisor los usa para la causal 3 sin depender del LLM | Media |
| RAG modular / enrutador por ley | No | Pre-filtro por ley con el clasificador existente (recall@5 por ley ya es 0,88–0,92) | Media |
| Lost in the middle | Riesgo en el evaluador (70 candidatos) | Medir con orden barajado; partir en lotes | Media |
| Grafo de referencias | No | CT 211-A..E y 20.393 art. 1 → delitos remitidos; útil cuando el corpus incluya las leyes remitidas | Baja |
| Evaluación de generación (fidelidad, LLM juez) | No | Medir fidelidad de las explicaciones del generador y del revisor; validar el juez con un abogado | Media |
| Self-RAG, RAPTOR, GraphRAG, multimodal, conversacional | No aplica | Corpus chico, preguntas puntuales, texto plano, sin chat | — |
| **Set de evaluación** | Incluye casos fuera del alcance | Decidido: triage de casos (no se amplía el corpus). Los casos sin relación con las leyes del corpus salen de la medición; el revisor igual alerta "fuera de corpus". | Alta |

## 5. Cómo se mide sin sesgar (decidido 2026-11-12)

1. **Triage** de los 113 casos: en alcance, control ("ninguna") o fuera de alcance. Solo se miden los dos primeros.
2. **Particiones:** casos jurídicos en alcance = desarrollo (se ajustan criterios mirando sus errores); Reddit en
   alcance = prueba. No se crean casos nuevos.
3. **Métricas:** recall@5 por artículo después del revisor (no puede bajar más de 0,02, IC pareado), precisión,
   vetos correctos en controles. Todo registrado en `kerna/evaluacion/registro`.
4. **Revisión jurídica:** la hace el equipo (es una demo), apoyado en investigación.

## 6. Decisiones tomadas

- Triage de casos en vez de ampliar el corpus.
- Modelo del revisor: `gpt-5-nano` hasta que una medición justifique `gpt-5-mini`.
- Nunca enviar el corpus completo al LLM.

## 7. Resultados (2026-11-12, gpt-5-nano, etiqueta corregida, corpus de 177 artículos)

| | Desarrollo (42 / 8 controles) | Prueba Reddit (13 / 16 controles) |
|---|---|---|
| hit@5 antes → después del revisor | 0,500 → 0,500 | 0,462 → 0,462 |
| Precisión@5 | 0,261 → 0,282 | 0,224 → 0,224 |
| Dictámenes (confirma/condiciona/veta) | 8 / 121 / 12 | 2 / 73 / 3 |
| Vetos incorrectos sobre esperados | 0 | 0 |

- No rompe el recall y no veta esperados, pero condiciona el 86 % y casi no limpia los controles.
- Siguiente palanca: el orden del evaluador (hit@70 ≈ 0,97) y afinar cuándo el revisor confirma.
- Detalle: `kerna/evaluacion/registro/revisor-20261112*.json` y `kerna/evaluacion/triage-casos.md`.
