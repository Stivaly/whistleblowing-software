# Investigación: cómo diseñar el indicador y el bloque de un asistente de IA en una herramienta de trabajo

Uso interno y reutilizable. Todas las fuentes se consultaron el **2026-11-10**. Este documento recoge lo que
dicen las fuentes y deriva principios; la propuesta concreta para Kerna está en `propuesta-bloque-kerna.md`.

Convención: cada afirmación lleva el código de su fuente entre corchetes (`[S12]`). Lo que no tiene respaldo se marca
**supuesto**. "Leída" quiere decir que se abrió la página y se leyó su contenido; las excepciones están en la tabla.

## 1. Fuentes y estado de lectura

### 1.1 Guías de diseño

| Cód. | Fuente | URL | Estado |
|---|---|---|---|
| S1 | Microsoft, HAX Toolkit: biblioteca de las 18 *Guidelines for Human-AI Interaction* (solo los títulos) | https://www.microsoft.com/en-us/haxtoolkit/library/ | Leída (títulos). La página de las pautas (`/ai-guidelines/`) no trae el texto de cada una (está en un póster) |
| S2 | Google PAIR, *People + AI Guidebook*: Explainability + Trust | https://pair.withgoogle.com/chapter/explainability-trust/ | Leída |
| S3 | Google PAIR: Feedback + Control | https://pair.withgoogle.com/chapter/feedback-controls/ | Leída |
| S4 | Google PAIR: Errors + Graceful Failure | https://pair.withgoogle.com/chapter/errors-failing/ | Leída |
| S5 | Nielsen Norman Group, *Tooltip Guidelines* | https://www.nngroup.com/articles/tooltip-guidelines/ | Leída |
| S6 | NN/g, *Progress Indicators Make a Slow System Less Insufferable* | https://www.nngroup.com/articles/progress-indicators/ | Leída |
| S7 | NN/g, *Explainable AI in Chat Interfaces* | https://www.nngroup.com/articles/explainable-ai/ | Leída |
| S8 | NN/g, *When Should We Trust AI? Magic-8-Ball Thinking and AI Hallucinations* | https://www.nngroup.com/articles/ai-magic-8-ball/ | Leída |
| S9 | NN/g, *The Sparkles Icon Problem* | https://www.nngroup.com/articles/ai-sparkles-icon-problem/ | Leída |
| S10 | Apple, Human Interface Guidelines: Generative AI (cambio del 8-jun-2026) | https://developer.apple.com/design/human-interface-guidelines/generative-ai | Leída (versión `.md` de la misma página) |
| S11 | Apple, Human Interface Guidelines: Machine learning | https://developer.apple.com/design/human-interface-guidelines/machine-learning | Leída (versión `.md`) |
| S12 | Google, Material Design 3 | https://m3.material.io/ | **No se pudo leer**: las páginas se generan en el navegador y la herramienta solo recibió el título. Una búsqueda no mostró una guía de IA propia de Material 3 |
| S13 | IBM Carbon, AI label (uso) | https://carbondesignsystem.com/components/ai-label/usage/ | Leída |
| S14 | IBM Carbon, AI label (accesibilidad) | https://carbondesignsystem.com/components/ai-label/accessibility/ | Leída |
| S15 | IBM Carbon for AI (principios) | https://carbondesignsystem.com/guidelines/carbon-for-ai/ | Leída |
| S16 | AWS Cloudscape, Gen AI: iconografía | https://cloudscape.design/gen-ai/foundation/iconography/ | Leída |
| S17 | Wikimedia Codex, guía de asistencia por máquina | https://doc.wikimedia.org/codex/main/style-guide/machine-assistance.html | Leída |

### 1.2 Accesibilidad

| Cód. | Fuente | URL | Estado |
|---|---|---|---|
| S18 | W3C, WCAG 2.2, Understanding 1.4.13 Content on Hover or Focus | https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html | Leída |
| S19 | WCAG 2.2, 1.4.1 Use of Color | https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html | Leída |
| S20 | WCAG 2.2, 1.4.3 Contrast (Minimum) | https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html | Leída |
| S21 | WCAG 2.2, 1.4.11 Non-text Contrast | https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html | Leída |
| S22 | WCAG 2.2, 2.3.3 Animation from Interactions | https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html | Leída |
| S23 | WCAG 2.2, 2.2.2 Pause, Stop, Hide | https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html | Leída |
| S24 | W3C, ARIA Authoring Practices Guide: patrón Tooltip | https://www.w3.org/WAI/ARIA/apg/patterns/tooltip/ | Leída. El propio APG avisa de que el patrón está en elaboración y sin consenso del grupo |
| S25 | MDN, `prefers-reduced-motion` | https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion | Leída hasta el carácter 100.000 de 130.036 (lo restante son tablas de compatibilidad) |

### 1.3 Regulación y estándares

| Cód. | Fuente | URL | Estado |
|---|---|---|---|
| S26 | Reglamento (UE) 2024/1689 (Ley de IA), art. 13 | https://artificialintelligenceact.eu/article/13/ | Leída. Es un sitio de referencia no oficial del texto; la versión de EUR-Lex (`https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689`) solo pudo leerse hasta el considerando 56 |
| S27 | Ley de IA, art. 14 (supervisión humana) | https://artificialintelligenceact.eu/article/14/ | Leída (mismo sitio) |
| S28 | Ley de IA, art. 50 (obligaciones de transparencia) | https://artificialintelligenceact.eu/article/50/ | Leída (mismo sitio) |
| S29 | Ley de IA, anexo III | https://artificialintelligenceact.eu/annex/3/ | Leída (mismo sitio) |
| S30 | ISO/IEC 42001:2023 | https://www.iso.org/standard/81230.html | **No se pudo abrir** (403). El texto de la norma es de pago |
| S31 | Modulos, resumen de los anexos de ISO/IEC 42001 (fuente secundaria) | https://docs.modulos.ai/frameworks/iso-42001/annexes-a-d.html | Leída; solo da los nombres de los controles (A.8.2 a A.8.5, A.9.2 a A.9.4), no su redacción |
| S32 | SEC (EE. UU.), comunicado 2024-36, "AI washing" | https://www.sec.gov/newsroom/press-releases/2024-36 | Leída |

### 1.4 Estudios académicos y de investigación

| Cód. | Fuente | URL | Estado |
|---|---|---|---|
| A1 | Bansal et al., *Does the Whole Exceed its Parts? The Effect of AI Explanations on Complementary Team Performance*, CHI 2021 | https://arxiv.org/abs/2006.14779 | Resumen leído (arXiv) |
| A2 | Buçinca, Malaya, Gajos, *To Trust or to Think: Cognitive Forcing Functions Can Reduce Overreliance on AI in AI-assisted Decision-making*, CSCW 2021 (DOI 10.1145/3449287 enlazado en arXiv) | https://arxiv.org/abs/2102.09692 | Resumen leído (arXiv) |
| A3 | Vasconcelos et al., *Explanations Can Reduce Overreliance on AI Systems During Decision-Making*, CSCW 2023 | https://arxiv.org/abs/2212.06823 | Resumen leído (arXiv) |
| A4 | Zhang, Liao, Bellamy, *Effect of Confidence and Explanation on Accuracy and Trust Calibration in AI-Assisted Decision Making* (arXiv enlaza el DOI 10.1145/3351095.3372852, de FAT* 2020) | https://arxiv.org/abs/2001.02114 | Resumen leído (arXiv) |
| A5 | Lai y Tan, *On Human Predictions with Explanations and Predictions of Machine Learning Models*, FAT* 2019 | https://arxiv.org/abs/1811.07901 | Resumen leído (arXiv) |
| A6 | Magesh et al., *Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools* (Stanford) | https://arxiv.org/abs/2405.20362 | Resumen leído (arXiv; la página no indica revista) |
| A7 | Ding et al., *Citations and Trust in LLM Generated Responses*, AAAI 2025 | https://arxiv.org/abs/2501.01303 | Resumen leído (arXiv) |
| A8 | Kim, Liao, Vorvoreanu, Ballard, Wortman Vaughan, *"I'm Not Sure, But...": Examining the Impact of LLMs' Uncertainty Expression on User Reliance and Trust*, FAccT 2024 | https://arxiv.org/abs/2405.00623 | Resumen leído (arXiv) |
| A9 | Passi y Vorvoreanu, *Overreliance on AI: Literature Review*, Microsoft Research MSR-TR-2022-12 (~60 estudios); y el marco derivado de Microsoft Learn | https://www.microsoft.com/en-us/research/publication/overreliance-on-ai-literature-review/ y https://learn.microsoft.com/en-us/ai/playbook/technology-guidance/overreliance-on-ai/overreliance-on-ai | Leídas ambas páginas (resumen del informe y marco completo) |
| A10 | Dietvorst, Simmons, Massey, *Algorithm Aversion*, J. of Experimental Psychology: General 144(1), 2015 | https://faculty.wharton.upenn.edu/wp-content/uploads/2016/11/20-Dietvorst-Simmons-Massey-2015.pdf | **El PDF no era legible** (texto comprimido). Lo que se cita sale del resumen que devolvió una búsqueda y de la reseña de Chicago Booth (https://www.chicagobooth.edu/review/2020/october/even-when-algorithms-outperform-humans-people-often-reject-them, leída). La página del repositorio de Penn dio 403 |
| A11 | Logg, Minson, Moore, *Algorithm appreciation*, Organizational Behavior and Human Decision Processes 151, 2019 | https://econpapers.repec.org/RePEc:eee:jobhdp:v:151:y:2019:i:c:p:90-103 | Resumen leído (el PDF de eScholarship no era legible) |
| A12 | Cicek, Gursoy, Lu, estudio sobre mencionar "inteligencia artificial" en descripciones de productos, *Journal of Hospitality Marketing & Management* (2024) | https://news.wsu.edu/press-release/2024/07/30/using-the-term-artificial-intelligence-in-product-descriptions-reduces-purchase-intentions/ | Leído el **comunicado de prensa** de la universidad, no el artículo |
| A13 | Weisz et al., *Design Principles for Generative AI Applications*, CHI 2024 | https://arxiv.org/abs/2401.14484 | Resumen leído; la página no lista los seis principios |

Resumen: se leyeron 43 de las 45 fuentes codificadas (más dos páginas auxiliares: Chicago Booth y Microsoft Learn); no se pudieron abrir S12 (Material), S30 (ISO/IEC 42001, solo secundaria S31) y el texto
legible de A10 (Dietvorst); S1, A10, A12, S26-S29 y S31 se leyeron con las limitaciones indicadas.

## 2. Hallazgos por tema

### 2.1 Comunicar estado y progreso de una IA dentro de una herramienta de trabajo

- Las guías de Microsoft incluyen como pautas "Make clear what the system can do" y "Make clear how well the system can do what it can do" (G1 y G2) [S1].
- Un indicador de progreso reduce la incertidumbre y hace que la espera se sienta más corta; debe responder de inmediato a la acción y mostrarse para todo lo que pase de 1 segundo [S6].
- Los indicadores en bucle sirven para esperas de 2 a 10 segundos; pasados 10 segundos los usuarios pierden la paciencia y no saben si el sistema está colgado. Para esperas largas se recomienda mostrar progreso (porcentaje o paso N de M) y permitir cancelar. Los indicadores estáticos ("Cargando…") y los giros indefinidos en esperas largas hacen que se abandone la tarea [S6].
- Apple pide mensajes específicos durante la generación en vez de "Processing…", y, si algo falla, "describir lo ocurrido en lenguaje claro y ofrecer un siguiente paso" [S10]. También recomienda diseñar la espera o generar en segundo plano mientras la persona usa otra parte de la aplicación [S10].
- Carbon trata la etiqueta de IA como un punto de acceso estable y reconocible; su presencia es la señal de que hay IA [S13].
- Wikimedia recomienda escalar la divulgación al riesgo: más detalle (etiqueta, descargo, instrucciones y vía de retroalimentación) cuando el contenido es generado, menos predecible o de mayor riesgo [S17].

### 2.2 Incertidumbre y confianza calibrada

- Google PAIR: el objetivo es que los usuarios ni desconfíen ni confíen de más; se explica más en situaciones de alto riesgo; "la mejor explicación probablemente sea parcial". Sobre la confianza: decidir si mostrarla (omitirla si no cambia decisiones o puede crear falsa confianza); si se muestra, categorías con umbrales claros y la acción que implica cada una; "los indicadores numéricos de confianza son riesgosos" [S2].
- Apple: "si no estás seguro de cómo se correlacionan tus valores de confianza con la calidad de los resultados, no es buena idea transmitirlos"; traducir la confianza a conceptos que la gente ya entienda, ordenar los resultados de forma que implique confianza, o expresarla como sugerencia accionable [S11].
- Mostrar una puntuación de confianza ayuda a calibrar la confianza, pero la calibración por sí sola no basta para mejorar el desempeño conjunto [A4].
- Expresar la incertidumbre en lenguaje natural ("No estoy seguro, pero…") redujo la confianza y el acuerdo de los participantes y mejoró su exactitud al reducir la sobredependencia de respuestas incorrectas (404 participantes, preguntas médicas); la redacción importa (las formas impersonales tuvieron efectos más débiles y no significativos) y se recomienda probar antes de desplegar [A8].
- Wikimedia: no ocultar la incertidumbre cuando afecta la confianza o la decisión [S17].

### 2.3 Fundamentación y citas

- Las citas de los chatbots suelen ser alucinadas, apuntar a URL muertas o no respaldar nada, y aun así hacen que la respuesta parezca más creíble; la gente rara vez hace clic. Recomendaciones: avisar de que se verifique, diferenciar visualmente la cita del texto, ponerla junto a la afirmación que respalda, enlazar al pasaje concreto y usar etiquetas descriptivas, no "Fuente" [S7].
- En un experimento, la confianza subió significativamente cuando había citas, incluso aleatorias, y bajó cuando los participantes las comprobaban [A7].
- Herramientas comerciales de investigación jurídica con recuperación aumentada alucinan entre el 17 % y el 33 % de las veces; las afirmaciones de los proveedores están sobredimensionadas [A6].
- El marco de Microsoft: facilitar la verificación (fuentes y explicaciones fáciles de encontrar e integradas); advierte que "la mera presencia de fuentes puede hacer que los usuarios confíen más" y que las explicaciones pueden aumentar la confianza aun siendo incorrectas [A9].
- Las explicaciones de "razonamiento" mostradas por los modelos suelen ser racionalizaciones posteriores; se recomienda apoyarse en fuentes y en declaraciones claras de limitaciones [S7].
- Apple: una atribución debe ser factual, ni demasiado específica ni demasiado general y sin jerga técnica o estadística [S11].

### 2.4 Divulgación progresiva

- Carbon: la etiqueta de IA abre un popover que es la primera capa de explicabilidad, con un resumen y la posibilidad de profundizar a demanda; las explicaciones deben aparecer solo cuando se piden, para no distraer [S13, S15].
- PAIR: explicaciones parciales; explicar en función de la acción del usuario [S2].
- NN/g: el tooltip es microcontenido breve y no esencial; "los usuarios no deberían necesitar encontrar un tooltip para completar su tarea" [S5].
- El patrón tooltip del APG: no recibe foco, no sirve para contenido con el que haya que interactuar; si es necesario contenido interactivo, usar un diálogo no modal [S24].

### 2.5 Transparencia del modo de generación (contingencia o respaldo)

- La Ley de IA, para sistemas de alto riesgo, exige informar de las características, capacidades y limitaciones de desempeño y de "cualquier circunstancia conocida y previsible" que pueda afectar el nivel esperado de exactitud (art. 13.3) [S26]. Es una referencia: no se concluye aquí que Kerna sea de alto riesgo (ver 2.10).
- Apple: comunicar limitaciones, mostrar cómo obtener buenos resultados y **explicar por qué ocurren resultados inferiores** [S11].
- Microsoft: las mitigaciones deben "señalar cuándo verificar" y hacer fácil detectar errores [A9].
- No hay una guía específica sobre mostrar que se usó un modelo de respaldo; la decisión de distinguirlo como estado propio es una aplicación de lo anterior (**supuesto** en cuanto al formato).

### 2.6 Control humano: aceptar, rechazar, corregir

- Apple: mantener a las personas al mando; permitir descartar contenido, revertir o reintentar; facilitar refinar o revertir y reconocer cuándo una corrección tuvo efecto; "nunca engañar" sobre si algo fue creado por una IA [S10]. Las correcciones guiadas (alternativas concretas) cuestan menos que las libres; nunca usar correcciones para compensar resultados de baja calidad [S11].
- PAIR: ofrecer una ruta manual no automatizada; las personas quieren más control cuando hay mucho en juego y cuando se sienten responsables del resultado [S3].
- Ley de IA, art. 14(4): quien supervisa debe poder entender capacidades y límites, ser consciente del sesgo de automatización, interpretar correctamente la salida y **decidir no usar el sistema o anular su resultado** [S27].
- Con explicaciones, las personas aceptan más las recomendaciones de la IA aunque se equivoque; no mejoraron el desempeño complementario [A1].
- Las "funciones de forzado cognitivo" redujeron la sobredependencia pero fueron las peor valoradas por los participantes, y ayudaron más a quienes tienen alta necesidad de cognición [A2].
- Las explicaciones pueden reducir la sobredependencia cuando bajan el costo de verificar la predicción [A3].
- Mostrar la etiqueta de la máquina sube mucho el desempeño humano, pero hay un compromiso entre desempeño y agencia [A5].
- Aversión al algoritmo: tras ver errores, la gente pierde la confianza en un algoritmo más rápido que en una persona [A10, resumen de búsqueda]. Una reseña posterior atribuye parte del efecto a la preferencia por pronósticos de mayor varianza con opción de "perfección" [A10, Chicago Booth]. La reseña no describe formas de reducir la aversión; que permitir modificar la salida la reduce proviene de un resultado de búsqueda sobre un trabajo posterior de los mismos autores, que no se abrió: tratarlo como **supuesto** razonable.
- "Apreciación del algoritmo": la gente común sigue más el consejo atribuido a un algoritmo que el atribuido a una persona; el efecto se debilita en quienes tienen experiencia en pronosticar, que confían menos en el consejo algorítmico y pierden exactitud [A11].
- Carbon: cuando el usuario edita contenido sugerido por IA, desaparece el estilo de IA y se ofrece revertir [S13, S15].

### 2.7 Retroalimentación

- Apple: el feedback explícito debe ser voluntario, con lenguaje simple que diga qué consecuencia tiene cada opción; pedirlo solo cuando es necesario; actuar de inmediato y mostrar que se recuerda; ponerlo en un lugar claro que no interrumpa; pulgares arriba/abajo son una opción simple, y se puede ofrecer un canal para feedback detallado [S10, S11].
- PAIR: avisar cómo se usa el feedback y prometer solo lo que el sistema cumple; reconocerlo [S3].
- Wikimedia considera el feedback "crucial" para contenido generado, aunque recomienda evitar escalas de pulgares y explicar cómo se usará [S17]: una tensión con el pulgar arriba/abajo que se resuelve limitando la valoración al artículo y agregando texto libre opcional (decisión de la propuesta, **supuesto**).
- ISO/IEC 42001 incluye, según un resumen secundario, controles de reporte externo y de comunicación de incidentes (A.8.3 y A.8.4) [S31]; no se pudo leer la norma [S30].

### 2.8 Interrupciones

- Apple: las funciones proactivas toleran peor los errores y quitan sensación de control; el feedback debe ubicarse sin interrumpir [S10, S11].
- HAX incluye "Time services based on context" y "Support efficient dismissal" (G3 y G8, solo títulos) [S1].
- Decisión derivada: un indicador pasivo, sin ventanas, avisos emergentes ni sonidos. Qué estados merecen un anuncio a lectores de pantalla no tiene respaldo en lo leído (**supuesto**).

### 2.9 Accesibilidad

- WCAG 2.2, 1.4.13 (AA): el contenido que aparece al pasar el puntero o enfocar debe poder **descartarse** sin mover el puntero ni el foco (por ejemplo con Esc), ser **sobrevolable** (poder llevar el puntero encima sin que desaparezca) y **persistente** hasta que se retire el disparador, se descarte o deje de ser válido; el contenido por hover debe ser alcanzable también por foco [S18].
- Patrón tooltip del APG: aparece con foco del teclado o con hover tras un breve retraso; Esc lo descarta y el foco se queda en el disparador; el disparador lo referencia con `aria-describedby`; el contenedor usa `role="tooltip"` [S24]. NN/g coincide: los tooltips deben aparecer con hover y con "hover de teclado" [S5].
- Carbon: la etiqueta de IA es un botón en el orden de tabulación, Enter/Espacio abre y cierra, Esc cierra y devuelve el foco, `aria-expanded` y `aria-controls`; no trata el color como señal única [S14].
- 1.4.1: el color no puede ser el único medio visual de transmitir información; se complementa con texto o forma [S19].
- 1.4.3: texto normal 4,5:1 y texto grande 3:1 [S20]. 1.4.11: componentes de interfaz e información gráfica necesaria, 3:1 contra los colores adyacentes; los estados también [S21].
- `prefers-reduced-motion`: se mantienen las animaciones por defecto y se sustituyen o quitan dentro de `@media (prefers-reduced-motion: reduce)`, cambiando el movimiento grande por cambios suaves de opacidad [S25]. WCAG 2.3.3 cita las técnicas C39 y SCR40 [S22]. WCAG 2.2.2: el movimiento que arranca solo, dura más de 5 segundos y se muestra junto a otro contenido necesita mecanismo para pausarlo, salvo que sea esencial [S23].
- Cloudscape y Carbon recomiendan nombre accesible en el ícono (en Carbon, `aria-label="AI - Show information"`) [S14]; en Cloudscape no hay reglas de accesibilidad para el destello [S16].

### 2.10 Aversión a la IA, "AI-washing" y marca explícita frente a marca integrada

- Un estudio con más de 1.000 adultos en EE. UU. encontró que describir un producto como "inteligencia artificial" reduce la confianza emocional y la intención de compra, y más en productos de alto riesgo (dispositivos médicos, servicios financieros); los autores aconsejan describir funciones y beneficios y evitar "palabras de moda" de IA [A12, solo comunicado de prensa]. Los resultados son de consumo, no de software profesional.
- Una búsqueda mostró otro estudio (Nordhoff y Zumstein, 2025) donde revelar que un texto de producto fue escrito por IA no reduce significativamente la compra y pesa más la calidad; **no se abrió** y no se usa para decidir.
- Aversión al algoritmo tras ver errores [A10]; en cambio, el público general tiende a seguir más un consejo algorítmico, y los expertos menos [A11]. La conjunción sugiere que en un auditor (profesional) el riesgo principal no es seguir ciegamente a la IA sino lo contrario o una confianza inestable tras un error; no hay estudio leído sobre auditores o abogados que lo confirme (**supuesto**).
- "AI washing": la SEC sancionó a dos asesoras de inversión por declarar usos de IA que no tenían; su presidente dijo que no se debe engañar al público diciendo que se usa un modelo de IA cuando no es así [S32]. Lección de diseño: **no sobrerrepresentar** lo que hace el sistema; afirmar en pantalla solo lo que ocurrió (por ejemplo, "cita comprobada" solo si se comprobó).
- Marca explícita de IA: Carbon exige una etiqueta de IA integrada en cada componente de IA, pero también dice que no debe usarse como adorno ni como disparador de acciones [S13, S15]; Cloudscape reserva el destello para acciones impulsadas por IA y desaconseja usarlo como identificador de un modelo (para eso, un logo o avatar) [S16]. Apple pide comunicar dónde se usa IA y nunca hacer pasar contenido de IA por humano [S10]. Wikimedia: etiquetar explícitamente lo generado, descargos para lo generado, y evitar presentar al sistema como socio o actor principal [S17].
- El destello (✨) es ambiguo: nadie en la investigación del artículo lo asoció con "inteligencia artificial", se parece a una estrella ("guardar") y puede encubrir riesgos; se recomienda acompañarlo de texto [S9].
- Humanizar: el lenguaje en primera persona infla la inteligencia percibida; se recomienda frases neutras y factuales [S7].
- ISO/IEC 42001 y Ley de IA: la norma ISO (según resumen secundario) tiene un objetivo A.8 de información para las partes interesadas (documentación e información para usuarios, reporte externo, comunicación de incidentes, información para partes interesadas) y A.9 de uso responsable e intención de uso [S31]; no se leyó su texto [S30]. El art. 50 de la Ley de IA obliga a avisar a quien interactúa directamente con una IA salvo que sea evidente, y a marcar los contenidos sintéticos; el aviso debe ser claro y distinguible, a más tardar en la primera interacción y accesible (art. 50.5) [S28]. El anexo III incluye sistemas destinados a ser usados por una autoridad judicial o en su nombre [S29]. Para Kerna estas son **referencias**: si su uso cae en alto riesgo o no es una cuestión legal pendiente (ver preguntas abiertas).
- Conclusión: la transparencia se cumple con **texto claro** ("Sugerencia asistida", modo de generación, límites), no con un ícono. La elección del ícono (robot, marca propia, símbolo de la tarea) es un asunto de percepción y de identidad; **no encontré un estudio que compare íconos de robot con símbolos de la tarea en herramientas jurídicas**, así que no hay evidencia para recomendar uno.

### 2.11 Sesgo de automatización y sobreconfianza en contextos de alto riesgo

- La sobredependencia es aceptar salidas incorrectas o incompletas, normalmente porque el diseño dificulta ver los errores; su impacto es mayor en tareas de alto riesgo, y los factores de riesgo incluyen poca alfabetización en IA, poca experiencia en el dominio, poca familiaridad con la tarea y alta confianza general en la IA. Las tres metas de UX: crear modelos mentales realistas, señalar cuándo verificar y facilitar la verificación; muchas mitigaciones pueden tener efecto contrario [A9].
- NN/g: "pensamiento de bola 8 mágica": verificar lo que importa, igualar el escrutinio al riesgo, mantener la responsabilidad, hacer trazables las salidas con citas o tarjetas de fuente [S8].
- Los descargos escondidos en pies de página se omiten; deben usar lenguaje claro y específico y acompañarse de una acción ("revisa las respuestas") y estar cerca de donde se usa [S7].
- Weisz et al. proponen seis principios con estrategias de diseño para aplicaciones de IA generativa (no se listan en el resumen) [A13].

## 3. Principios derivados

| # | Principio | Fuentes |
|---|---|---|
| P1 | **Decir lo que es, lo que hace y sus límites, en texto claro y desde el primer vistazo**: "Sugerencia asistida, no es un dictamen jurídico". Transparencia con palabras, no con adornos | S1, S2, S10, S11, S17, S28 (referencia) |
| P2 | **Marca de IA proporcional al riesgo**: texto explícito donde hay decisión; nada de destellos ni personajes; no prometer más de lo que el sistema hizo (evitar "AI washing") | S13, S15, S16, S17, S9, S32, A12 |
| P3 | **Estado específico y honesto**, con etiqueta de texto y sin progreso inventado: no hay datos para una barra de porcentaje; indicar "suele tardar unos minutos" y el tiempo transcurrido; no animar indefinidamente | S6, S10, S23, S25 |
| P4 | **Confianza calibrada**: no mostrar cifras de confianza del modelo si no están validadas; ordenar por relevancia; el respaldo es la cita literal comprobada, y solo se afirma lo comprobado | S2, S11, A4, A8, A7, A6 |
| P5 | **Fundamentación verificable**: cada artículo con explicación, cita literal y enlace específico a la fuente, junto a la afirmación; con aviso de que se revise | S7, S8, A9, A6, A7 |
| P6 | **Divulgación progresiva**: etiqueta y tooltip dan el resumen; el detalle se abre a petición; el tooltip nunca contiene lo imprescindible ni controles | S5, S13, S15, S24, S2 |
| P7 | **El humano decide y puede anular**: sin preselección, "ninguno aplica", clasificar a mano sin bloqueo; fricción ligera hacia la verificación (forzado cognitivo) con cuidado de no resultar fastidiosa | S10, S3, S27, A1, A2, A3, A10 |
| P8 | **Retroalimentación voluntaria, simple y con consecuencias claras**, ligada a cada artículo, con comentario opcional | S10, S11, S3, S17 |
| P9 | **Fallos explicados en lenguaje claro**: qué pasó, qué significa, qué hacer; devolver el control; sin jerga | S4, S10, S11 |
| P10 | **El modo de generación es información relevante**: la contingencia se distingue y se explica porque puede afectar la exactitud | S26 (referencia), S11, A9 |
| P11 | **Accesible por construcción**: tooltip descartable, sobrevolable y persistente, disparable con foco; color nunca solo; contraste; movimiento reducible | S18, S19, S20, S21, S22, S23, S24, S25, S5, S14 |
| P12 | **Sin interrupciones**: indicador pasivo; el usuario decide cuándo abrir el detalle | S10, S11, S1 |
| P13 | **Lenguaje neutro y factual**: sin primera persona ni antropomorfismo | S7, S17 |
| P14 | **Probar con usuarios**: muchas mitigaciones fallan o tienen efectos contrarios | A9, S2, A8 |

## 4. Tabla principio → fuente → decisión de diseño

| Principio | Fuente | Decisión aplicada al indicador y al bloque de Kerna |
|---|---|---|
| P1 | S10, S17, S11 | El panel lleva siempre, sin poder cerrarse, el aviso "Sugerencia asistida: no es un dictamen jurídico". La etiqueta del indicador dice "Kerna" con el estado en texto |
| P2 | S13, S15, S16, S9, A12, S32 | El indicador se rotula con el nombre del producto y el estado, no con "IA". Sin destellos. El ícono es intercambiable (tres o cuatro opciones) y no es lo que transmite la transparencia. No se afirma nada que no se haya comprobado |
| P2 | S9 | Si se usara un símbolo de IA, acompañarlo siempre de texto (evitar la ambigüedad del destello). Opciones de ícono sin destellos |
| P3 | S6, S10 | La etiqueta "Preparando sugerencia" con la antigüedad ("hace 2 min") y la expectativa ("suele tardar unos minutos") en el tooltip; sin barra de porcentaje |
| P3 | S23, S25, S22 | La animación del estado de espera es opcional: se desactiva con `prefers-reduced-motion` y no dura más de 5 s por episodio (al terminar queda la forma estática), de modo que no exige botón de pausa. El estado se entiende sin ella |
| P4 | S2, S11, A4 | No se muestra el campo `confianza` como número ni porcentaje (no está validado contra la calidad); los artículos se ordenan por él, lo que implica confianza sin cifras |
| P4 | A7, A6, A9 | La marca "cita comprobada" se redacta como "La cita coincide con el texto de la ley", no como "es correcto", y junto a ella se pide revisar que el artículo aplica al caso |
| P5 | S7, S8, A9 | Cada artículo muestra explicación, cita literal diferenciada y un enlace descriptivo a la Biblioteca del Congreso Nacional ("Ver el artículo X en la Biblioteca del Congreso Nacional"), junto a la afirmación |
| P6 | S13, S15, S5, S24 | Tooltip = resumen de una línea más modo; clic o Enter abre el panel completo. El tooltip no contiene botones ni enlaces (el APG lo prohíbe para contenido interactivo) |
| P7 | S10, S3 | El trabajo manual nunca se bloquea; el panel no impide clasificar; hay "Ninguno aplica" y "Agregar otro artículo" |
| P7 | A2, A1, A3 | Los artículos no vienen marcados: el auditor elige cuáles incluir en la clasificación (fricción ligera de verificación, sin pantallas intermedias) y se mantiene la cita a un clic para bajar el costo de verificar. **Supuesto sobre el grado de fricción**: probar con auditores (P14) |
| P7 | A10, A11 | No se auto-aplica ninguna clasificación; el auditor puede modificar la sugerencia (idea de que modificar reduce la aversión: **supuesto**, ver 2.6) |
| P8 | S10, S11, S17 | Valoración arriba/abajo por artículo (`aria-pressed`), con observación opcional de 500 caracteres; texto que indica que se guarda en el caso y que es voluntaria; tensión con S17 anotada |
| P8 | S3 | Solo se promete lo que el contrato cumple: la valoración se envía a Kerna una vez y sirve para medirla (la redacción final debe confirmarse con el equipo) |
| P9 | S4, S10 | Cada estado de fallo tiene un mensaje "qué pasó / qué significa / qué puedes hacer" sin códigos ni nombres de servicios o proveedores; el detalle técnico va a telemetría con un código copiable |
| P10 | S26, S11, A9 | Estado propio "Lista · modo de respaldo/local/búsqueda local", color distinto, aviso dentro del panel y línea "Modo" en el tooltip |
| P11 | S18, S24 | Tooltip: aparece con hover y foco, Esc lo cierra sin mover el foco, el puntero puede entrar en él sin que se cierre (retraso de cierre y área contigua), `aria-describedby` y `role="tooltip"` |
| P11 | S19, S21, S20 | Cada estado lleva etiqueta de texto y una silueta secundaria distinta, más color; razones de contraste calculadas (4,5:1 texto, 3:1 componentes) |
| P11 | S14 | El indicador es un botón con `aria-expanded` y `aria-controls`; Enter y Espacio abren el panel; Esc cierra el tooltip y no el panel |
| P12 | S10, S11 | Sin ventanas emergentes, avisos temporales ni sonidos: el indicador cambia de estado sin interrumpir. Si se anuncian cambios a lectores de pantalla se hará con una región `aria-live="polite"` (**supuesto**, no respaldado por las fuentes leídas) |
| P13 | S7, S17 | Los textos usan frases impersonales y factuales ("la sugerencia se basa en…"), sin primera persona |
| P14 | A9, A8 | Pruebas con auditores reales antes de fijar la redacción y la fricción |

## 5. Lo descartado y por qué

| Descartado | Motivo |
|---|---|
| Barra de progreso en porcentaje | No hay dato de progreso en el contrato; sería inventado. Se compensa con texto y antigüedad [S6] |
| Giro continuo mientras dure la espera | Los giros indefinidos en esperas largas hacen abandonar [S6] y el movimiento automático de más de 5 s exige control de pausa [S23] |
| Mostrar la `confianza` como número o porcentaje | Riesgoso e inútil sin calibración [S2, S11] |
| Marcar los artículos como "verificados" sin más | Una cita que existe no demuestra que el artículo aplique; las citas elevan la confianza aun siendo irrelevantes [A7, A6] |
| Mostrar "razonamiento paso a paso" del modelo | Suele ser racionalización [S7] |
| Destellos (✨) como marca | Ambiguos [S9] y con riesgo de sugerir "magia" [S9]; Carbon y Cloudscape piden que no sean adorno [S13, S16] |
| Avatar, personaje o texto en primera persona | Antropomorfismo [S7, S17] |
| Notificaciones emergentes, modales o sonidos | Interrupción innecesaria [S10, S11] |
| Botón "Regenerar" | El contrato no tiene esa operación; además Carbon desaconseja mezclar acciones con la etiqueta [S13] |
| Enlaces o botones dentro del tooltip | El tooltip no recibe foco [S24]; lo interactivo va en el panel |
| Atributo `title` nativo como tooltip | No es controlable por el autor ni sobrevolable de forma fiable (WCAG lo excluye de 1.4.13 porque lo controla el navegador [S18]); se usa un componente propio |
| Preseleccionar todos los artículos sugeridos | Aumenta la aceptación sin revisión [A1, A2] |
| Mostrar nombres de modelos, proveedores o códigos HTTP | Requisito de lenguaje claro; PAIR recomienda no sobre-explicar vulnerabilidades [S4] |
| Un solo color para todos los problemas | Cada estado necesita distinguirse; el color no es suficiente por sí solo y se acompaña de forma y texto [S19] |
| Descartar el pulgar arriba/abajo por la crítica de Wikimedia | Se mantiene limitado a cada artículo y con texto opcional [S10 apoya el pulgar; S17 lo critica] |

## 6. Preguntas abiertas y supuestos

1. **Material Design** no se pudo leer; falta contrastar S12 (la herramienta solo recibió el título).
2. **ISO/IEC 42001**: no se leyó la norma (de pago); las decisiones que invocan A.8 dependen de un resumen secundario [S31].
3. ¿Kerna es un sistema de alto riesgo bajo la Ley de IA? El anexo III menciona a autoridades judiciales [S29]; el uso del auditor en una empresa podría no caer ahí. Pendiente de criterio legal; las obligaciones se usan como referencia.
4. Umbrales de tiempo (5 min sin nota y 6 min en "preparando") son **supuestos** derivados de los plazos del contrato (ver propuesta); validarlos con datos reales de operación.
5. Fricción ideal: ¿basta con no preseleccionar? ¿Conviene pedir abrir la cita antes de incluir un artículo? [A2] muestra el compromiso entre eficacia y agrado. Probar con auditores.
6. Redacción de las frases: se aplicó el criterio de las fuentes (qué pasó, qué significa, qué hacer; impersonal; sin jerga); falta una prueba de comprensión con auditores [A8, A9].
7. ¿La valoración se usa para algo concreto? Hay que decirlo al auditor con precisión [S3].
8. Identificación de la cuenta de servicio de Kerna en el cliente: el comentario solo trae `author_id` (ver propuesta).
9. Falta evidencia sobre íconos de robot frente a símbolos de la tarea en herramientas jurídicas; la elección es de identidad y percepción de la usuaria, no de evidencia.
10. Anuncio a lectores de pantalla de los cambios de estado: sin respaldo en lo leído (**supuesto**).
11. No se evaluó el desempeño de la sugerencia: [A6] sugiere que ni siquiera las herramientas jurídicas comerciales con citas son infalibles; por eso el diseño trata la sugerencia como apoyo y no como dictamen.
