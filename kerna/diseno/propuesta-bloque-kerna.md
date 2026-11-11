# Propuesta: indicador y bloque de Kerna en la vista del caso del auditor

Estado: **implementado en el cliente** (ver la sección 9, que recoge lo que difiere de lo propuesto). Los textos
vigentes están en `textos-finales.md` y reemplazan los borradores de la sección 2.5. Las fuentes de cada decisión están en `investigacion-asistente-ia.md` (códigos `S`, `A`, `P`). Las opciones de
ícono y las capturas están en `opciones-icono/`.

## 1. Dónde va cada pieza en el cliente Angular

Vista real del caso del destinatario: `client/app/src/pages/recipient/tip/tip.component.{html,ts}` (selector
`src-tip`). Estructura actual: barra `#Toolbar` → fila con `<src-tip-info>` → lista de destinatarios → respuestas del
cuestionario → archivos → pestañas de comentarios (`<src-tip-comments>`, `public`, `internal` y `personal`).

### 1.1 Archivos nuevos (todo lo de Kerna junto)

Carpeta `client/app/src/shared/partials/kerna/`:

| Archivo | Contenido |
|---|---|
| `kerna-notas.ts` | Tipos y lectura de las notas (`kerna_sugerencia`, `kerna_estado`, `kerna_feedback`, `kerna_clasificacion`, según `kerna/docs/contratos.md`), `esNotaKerna(comentario)` y `deducirEstado(entrada)`: función pura, sin Angular, con pruebas unitarias |
| `kerna-estados.ts` | Tabla de los 12 estados: id, clave de texto de `es.json`, clase CSS, glifo. Es la única fuente de la lista de estados |
| `kerna-icono.component.ts` | Componente `src-kerna-icono`: **el único lugar donde vive el SVG de marca**. Cambiar de ícono es reemplazar el `<svg>` de esa plantilla (las cuatro opciones están en `opciones-icono/svg/`) |
| `kerna-glifo.component.ts` | Siluetas secundarias por estado (check, arco, rombo, reloj de arena…), también SVG en línea |
| `kerna-indicador.component.ts` | `src-kerna-indicador`: botón-píldora con ícono, glifo y etiqueta; tooltip; consulta periódica |
| `kerna-panel.component.ts` | `src-kerna-panel`: tarjeta con la sugerencia, la valoración y la clasificación |
| `kerna.service.ts` | Estado compartido entre indicador y panel (estado deducido, consulta periódica, envío de valoración y clasificación con `ReceiverTipService.newComment(contenido, 'internal')`, que ya existe) |

Los estilos van en el **CSS global ya existente** (`client/app/css/main.css`, una sección al final) y no en estilos
de componente: la política de seguridad de contenido de Veridy (`backend/globaleaks/rest/api.py`) solo admite
`style-src 'self'` más un nonce y `img-src 'self'`; con CSS global se evita depender del nonce y todo el SVG va en
línea. Los colores son variables CSS `--kerna-*` (sección 4). Sin CDN, sin fuentes remotas, sin imágenes `data:`.

### 1.2 Cambios en pantallas existentes (los mínimos)

1. **Indicador, encima de la denuncia, en la cabecera**: en `tip.component.html`, entre el bloque `#Toolbar` y la
   fila que contiene `<src-tip-info>` (fila `row mt-2`), una fila nueva:
   `<div class="row mt-2"><div class="col-md-12"><src-kerna-indicador [tipService]="RTipService" (abrir)="..."/></div></div>`.
2. **Panel, junto a la clasificación manual**: justo después de la fila de `<src-tip-info>` (que contiene la etiqueta
   y el estado del caso) y antes de las respuestas del cuestionario, `<src-kerna-panel>` como tarjeta plegable con el
   mismo aspecto de `TipCommentsBox` (`card card-default`). Se abre en el sitio (no en ventana modal) para poder leer
   la denuncia y la sugerencia a la vez. El panel no duplica ni oculta la clasificación manual (el cambio
   de estado del caso que ya existe, `openModalChangeState()`): los mensajes dicen "clasifícalo como siempre".
3. **Retirar las notas JSON del hilo de comentarios**: en
   `client/app/src/shared/partials/tip-comments/tip-comments.component.{ts,html}`, un único cambio: sustituir
   `[items]="tipService.tip.comments"` por un getter `comentariosVisibles` que, **solo si la sesión es de rol
   `receiver`**, descarta los comentarios cuyo contenido es un JSON con `tipo` que empieza por `kerna_` (`esNotaKerna`).
   Para el denunciante el getter devuelve la lista sin tocar. Las notas se siguen guardando en el caso; solo dejan de
   mostrarse como texto crudo.
4. `tip.component.ts`: agregar los dos componentes al arreglo `imports` del componente independiente.
5. `client/app/assets/data/l10n/es.json`: claves nuevas con prefijo `kerna.` (todas las frases de la sección 3 y los
   textos del panel). Sin empeorar las claves que ya faltan.

**Sin tocar**: el flujo del denunciante (`pages/whistleblower/*`), el backend y el modelo de datos.
`<src-tip-comments>` también se usa en la vista del denunciante (`tippage.component.html`); por eso el filtro depende
del rol.

### 1.3 De dónde salen los datos (sin endpoints nuevos)

- Notas: `tip.comments` ya viene con `GET api/recipient/rtips/<id>` (cada comentario trae `id`, `creation_date`,
  `content`, `author_id`, `visibility`, `type`). El contenido llega descifrado en la sesión del destinatario.
- Fecha de creación del caso: `tip.creation_date`.
- Escritura de valoración y clasificación: `ReceiverTipService.newComment(...)` →
  `POST api/recipient/rtips/<id>/comments` con `visibility: "internal"`.
- Actualización: `KernaService` vuelve a pedir el caso con `HttpService.receiverTip(id)` y actualiza solo los
  comentarios (no usa `reloadComponent()`, que recarga la ruta completa y descartaría lo que el auditor escribe).
  Cada 20 s mientras el estado sea provisional (`sin-info` reciente, `generando`, `nucleo-no-disponible`,
  `conector-inactivo`) y con la pestaña visible; se detiene en los estados finales. **Supuesto**: el intervalo, para
  ajustarlo con datos.
- **Identificación de la cuenta de servicio**: el comentario trae solo `author_id`. Se resuelve con
  `appDataService.receivers_by_id[author_id]`, cuyo `name` es el nombre visible de la cuenta. Las reglas del contrato
  exigen que `kerna_sugerencia` y `kerna_estado` provengan de esa cuenta. Pendiente decidir cómo reconocerla de forma
  fiable (por nombre configurado, o con un dato nuevo del servidor). Mientras no exista la cuenta entre los
  destinatarios, el indicador **no se muestra**: una instalación sin Kerna no cambia.

## 2. Estados del indicador y cómo se deducen

### 2.1 Datos de entrada

- `notas`: comentarios internos cuyo contenido es JSON válido con `tipo` conocido y `version` 1 (si la versión es
  mayor y falta algún campo, se ignora la nota; si el JSON no es válido, es un comentario común).
- `sugerencia`: la `kerna_sugerencia` de la cuenta de servicio (el contrato dice que se publica una sola).
- `estado`: la `kerna_estado` más reciente por `fecha` de la cuenta de servicio.
- `clasificacion`: la última `kerna_clasificacion` de un destinatario que **no** es la cuenta de servicio.
- `edad`: ahora menos `tip.creation_date`.
- `fallaDeRed`: la última consulta periódica falló (sin red o respuesta de error de la plataforma) dos veces
  seguidas (para no parpadear con un fallo aislado).

### 2.2 Umbrales (propuestos)

| Constante | Valor | Razón |
|---|---|---|
| `UMBRAL_CONECTOR` | **5 min** | El conector revisa los casos cada 30 s por defecto (`CONECTOR_INTERVALO_S`); 5 min son 10 pasadas sin que aparezca ninguna nota |
| `UMBRAL_ESPERA` | **6 min** | Plazo global del núcleo (240 s, tras lo cual publica revisión manual por tiempo) + dos pasadas del conector (60 s) + 60 s de margen |
| `VENTANA_CASO_NUEVO` | **24 h** | Los casos anteriores a Kerna nunca tendrán nota; pasada esa edad un caso sin notas se muestra "sin información", no como falla |

Son **supuestos** derivados del contrato; validarlos con datos de operación.

### 2.3 Orden de evaluación

1. `fallaDeRed` → **sin-conexion** (se recuerda el último estado conocido para el tooltip).
2. Hay `clasificacion` → **valorada**.
3. Hay `sugerencia`:
   - `estado = completada` con `articulos` vacío → **sin-normativa** (defensivo: el contrato no lo prevé);
   - `completada` con `contingencia = true` → **contingencia** (variante según `modo`: `respaldo` o `local`, o
     `recuperacion = local`);
   - `completada` sin contingencia → **lista**;
   - `revision_manual` según `motivo_revision`: `tiempo_agotado` → **revision-tiempo**; `validacion_fallida` →
     **revision-citas**; `sin_normativa_aplicable` → **sin-normativa**; `cadena_agotada` (o cualquier otro valor) →
     **cadena-agotada**.
4. Hay `estado`: `nucleo_no_disponible` → **nucleo-no-disponible**; `en_proceso` → **generando**, salvo que hayan
   pasado más de `UMBRAL_ESPERA` desde su `fecha` sin sugerencia: entonces **conector-inactivo**.
5. No hay ninguna nota de Kerna: `edad` < `UMBRAL_CONECTOR` → **sin-info**; entre `UMBRAL_CONECTOR` y
   `VENTANA_CASO_NUEVO` → **conector-inactivo**; mayor → **sin-info**.

La detección de "plataforma en mantenimiento" se trata igual que cualquier fallo de la consulta (**supuesto**: no se
verificó en el servidor ninguna señal específica de mantenimiento).

### 2.4 Lista de estados

Colores: fondo / texto / acento (borde y glifo). Contraste verificado en la sección 4. Cada estado tiene una silueta
secundaria distinta, que acompaña al color (WCAG 1.4.1, S19). Todos son **borradores** de texto.

| # | Id | Etiqueta corta | Fondo / texto / acento | Silueta | Cómo se deduce |
|---|---|---|---|---|---|
| 1 | `sin-info` | Sin información de Kerna | `#F5F7FA` / `#434A54` / `#707A8A` (borde discontinuo) | Círculo discontinuo | No hay notas de Kerna y `edad` < 5 min, o `edad` > 24 h |
| 2 | `generando` | Preparando sugerencia | `#DCEBF8` / `#12324F` / `#2A6496` | Arco abierto (gira ≤ 5 s) | `kerna_estado = en_proceso`, sin sugerencia, hace menos de 6 min |
| 3 | `lista` | Sugerencia lista | `#DDF3E4` / `#11432A` / `#2E7D4F` | Círculo con marca de verificación | `completada`, `contingencia = false` |
| 4 | `contingencia` | Lista · modo de respaldo / modo local / búsqueda local | `#FFF2BF` / `#4D3A00` / `#8F6B00` | Rombo con barra | `completada` con `contingencia = true` |
| 5 | `revision-tiempo` | Revisión manual · demoró | `#FFE2C4` / `#5C2C05` / `#A85400` | Reloj de arena | `revision_manual` + `tiempo_agotado` |
| 6 | `revision-citas` | Revisión manual · citas sin confirmar | `#EAE4F7` / `#2E1F63` / `#6A4FB3` | Cuadrado redondeado con "?" | `revision_manual` + `validacion_fallida` |
| 7 | `sin-normativa` | Sin normativa encontrada | `#DDEFF0` / `#0F4249` / `#2C7C86` | Lupa con signo menos | `revision_manual` + `sin_normativa_aplicable` (o `completada` sin artículos) |
| 8 | `cadena-agotada` | Revisión manual · sin sugerencia | `#FDE0DD` / `#7A1212` / `#C62828` | Octógono con barra | `revision_manual` + `cadena_agotada` (o motivo desconocido) |
| 9 | `nucleo-no-disponible` | Kerna no disponible | `#FBDCEA` / `#6B0F3B` / `#B02A6B` | Triángulo con "!" | `kerna_estado = nucleo_no_disponible` (la última nota de estado) |
| 10 | `conector-inactivo` | Kerna sin respuesta | `#E7E2D6` / `#433818` / `#7D6D45` | Hexágono con tres puntos | Sin notas entre 5 min y 24 h; o `en_proceso` hace más de 6 min |
| 11 | `sin-conexion` | Sin conexión | `#323A49` / `#FFFFFF` / `#FFFFFF` | Círculo tachado | Falla la consulta periódica dos veces seguidas |
| 12 | `valorada` | Clasificación guardada | `#205782` / `#FFFFFF` / `#FFFFFF` | Bandera | Existe `kerna_clasificacion` de un destinatario |

Los estados 5 a 12 son los "de problema o revisión manual": ninguno bloquea el trabajo y todos se distinguen entre sí
por color, silueta y texto. `sin-conexion` y `valorada` son los dos estados oscuros (borde igual al fondo).

### 2.5 Contenido por estado: tooltip y mensaje (borradores)

El tooltip tiene siempre cuatro partes: **estado** (título), **resumen**, **modo de generación** y **cómo abrir el
detalle** (texto fijo: "Abre el detalle con clic o Enter. Esc cierra este aviso."). "Resumen" es la ley principal
(la `norma` con más artículos sugeridos; si empata, la de mayor `confianza` del primer artículo) y el número de
artículos: "Ley N.° 21.643 · 3 artículos". Las frases del mensaje responden **qué pasó / qué significa para este caso /
qué puedes hacer** y no usan códigos, "timeout", nombres de servicios ni de proveedores. Los mensajes de la columna
derecha aparecen en el panel; el tooltip usa título, resumen y modo.

| Id | Título del tooltip | Resumen | Modo | Mensaje en el panel (qué pasó / significa / puedes) |
|---|---|---|---|---|
| `sin-info` | Aún no hay información de Kerna para este caso | Sin resultados todavía | No disponible | Todavía no hay información de Kerna sobre este caso. / Puede que el caso sea reciente o que Kerna aún no lo haya tomado. / Puedes clasificarlo como siempre. Si Kerna lo toma, la sugerencia aparecerá aquí. |
| `generando` | Kerna está preparando la sugerencia | "Aún sin resultados" + antigüedad ("hace 2 min") | Se indicará cuando esté lista | Kerna está revisando el caso para sugerir artículos de la normativa. Suele tardar unos minutos. / Todavía no hay sugerencia, pero tu trabajo no se bloquea. / Puedes seguir con el caso y clasificarlo manualmente. La sugerencia aparecerá aquí cuando esté lista. |
| `lista` | Sugerencia lista | Ley N.° 21.643 · 3 artículos | Modo oficial | (el panel muestra los artículos; no hay mensaje de problema) |
| `contingencia` | Sugerencia lista, con aviso | Ley N.° 21.643 · 3 artículos | Modo de respaldo / Modo local / Búsqueda de normativa en modo local | Aviso fijo en el panel: "Esta sugerencia se preparó con un método alternativo porque el servicio principal no estaba disponible. Puede ser menos precisa: revisa cada artículo con especial atención." |
| `revision-tiempo` | Kerna no alcanzó a terminar a tiempo | Sin sugerencia | Revisión manual | La sugerencia tardó más de lo previsto y se detuvo. / Para este caso no habrá sugerencia de Kerna. / Clasifícalo manualmente como siempre. |
| `revision-citas` | La sugerencia no pasó la revisión de citas | Sin sugerencia | Revisión manual | Kerna preparó una sugerencia, pero no se pudo comprobar que sus citas coincidieran con el texto de las leyes. / Por seguridad no se muestra ningún artículo para este caso. / Clasifícalo manualmente como siempre. |
| `sin-normativa` | Kerna no encontró normativa aplicable | Sin artículos sugeridos | Revisión manual | Kerna no encontró en su base de normas artículos que correspondan con claridad a este caso. / No quiere decir que no exista normativa aplicable, sino que Kerna no puede sugerir una. / Clasifícalo según tu criterio. |
| `cadena-agotada` | Kerna no pudo preparar la sugerencia | Sin sugerencia | Revisión manual | Kerna no pudo preparar una sugerencia para este caso por un problema en sus servicios. / Para este caso no habrá sugerencia. / Clasifícalo manualmente. Si el problema se repite, informa el código de seguimiento. |
| `nucleo-no-disponible` | Kerna no está disponible ahora | Sin resultados todavía | Se sigue intentando | Kerna no está disponible en este momento. / El caso quedó en espera; se sigue intentando automáticamente. / Puedes clasificar el caso como siempre; la sugerencia aparecerá aquí cuando Kerna vuelva. |
| `conector-inactivo` | Kerna aún no ha tomado este caso | Sin resultados | No disponible | Ya pasó el tiempo habitual y Kerna no ha tomado este caso. Puede que la conexión con Kerna esté detenida o que no tenga acceso a este caso. / Por ahora no habrá sugerencia. / Clasifícalo como siempre. Si pasa en varios casos, avisa a la persona administradora. |
| `sin-conexion` | No se pudo actualizar la información | Último estado conocido (ej.: sugerencia lista) | Puede estar desactualizado | No se pudo actualizar este caso: la conexión se interrumpió o la plataforma está en mantenimiento. / Lo que ves puede estar desactualizado. / Espera unos minutos y vuelve a intentarlo. Tu trabajo ya guardado no se pierde. |
| `valorada` | Clasificación final guardada | 2 sugeridos aplicados · 1 agregado por ti | Modo con que se generó | El panel muestra la clasificación guardada y no permite editarla (para corregir se agrega una nueva; el contrato dice que vale la última) |

Acciones por estado: **Actualizar** (vuelve a consultar el caso) en los estados provisionales; **Reintentar** en
`sin-conexion`; **Clasificar manualmente** en los estados de revisión manual y en `nucleo-no-disponible` y
`conector-inactivo`. No existe "regenerar": el contrato no tiene esa operación y el conector reintenta solo cuando el
núcleo no responde. El **código de seguimiento** (`id_solicitud` o, si no existe, `id_seguimiento`) se muestra con un
botón de copiar en todos los estados que tienen una nota; nunca se muestra detalle técnico. Si ninguna nota existe
(`sin-info`, `conector-inactivo` sin notas) no hay código.

## 3. Comportamiento

### 3.1 Indicador y tooltip

- El indicador es un `<button>` (píldora de 36 px de alto; objetivo mayor que el mínimo de 24 px de WCAG 2.2) con
  ícono de marca, glifo de estado y etiqueta de texto. El texto "Kerna:" se agrega como texto solo para lectores de
  pantalla. Tiene `aria-describedby` hacia el tooltip, `aria-expanded` y `aria-controls` hacia el panel.
- Tooltip con `role="tooltip"`; aparece al pasar el puntero (con breve retraso) y al recibir el **foco del teclado**
  (S24, S5); **Esc** lo descarta sin mover el foco; **no desaparece al pasar el puntero encima** de él (cierre con
  retraso y sin hueco entre indicador y tooltip); permanece mientras el foco o el puntero estén en el disparador o en
  él, hasta que se descarte o cambie el estado (S18). No recibe foco ni contiene enlaces o botones (S24). No usa el
  atributo `title` ni el tooltip de `ngbTooltip` de la barra, que cierra al salir del disparador: se necesita un
  componente propio (**supuesto** técnico: no se probó el comportamiento de `ngbTooltip` ante 1.4.13).
- Sin ventanas emergentes, avisos temporales ni sonidos (P12). Si más adelante se anuncia un cambio de estado a
  lectores de pantalla se usará una región `aria-live="polite"` (**supuesto**).
- Animación de espera (`generando`): pulso suave de opacidad de la píldora y giro del arco, **como máximo 5 s por
  episodio** (así no necesita botón de pausa, WCAG 2.2.2, S23) y **desactivada** dentro de
  `@media (prefers-reduced-motion: reduce)` (S25, S22); el estado se entiende sin ella (texto y silueta).

### 3.2 Panel

- Se abre con clic, Enter o Espacio sobre el indicador y se cierra con el mismo gesto; el foco permanece en el
  indicador. Tarjeta plegable inline (disclosure), con `aria-labelledby`.
- Siempre visible, sin poder ocultarse: aviso **"Sugerencia asistida: no es un dictamen jurídico. La decisión y la
  clasificación final son tuyas."**
- Aviso de **contingencia** (fondo amarillo del estado 4) cuando `contingencia = true`, antes de la lista.
- Lista de artículos, ordenados por `confianza` (sin mostrar el número, P4). Cada uno: norma y artículo, explicación,
  **cita literal** en bloque diferenciado, enlace "Ver el artículo en la Biblioteca del Congreso Nacional"
  (`enlace_fuente`, con `rel="noopener noreferrer"` y `target="_blank"`), casilla **"Incluir en la clasificación"**
  (sin marcar por defecto) y valoración **arriba/abajo** (`aria-pressed`) con **observación opcional de hasta 500
  caracteres** y contador.
- Clasificación final: artículos sugeridos marcados por el auditor más los que agregue (campo "Agregar otro
  artículo", `origen: agregado_por_auditor`), botón "Guardar clasificación" y botón "Ninguno aplica" (lista vacía,
  que el contrato permite). Escribe una `kerna_clasificacion` interna; las valoraciones, una `kerna_feedback` por
  artículo.
- Pie con el **código de seguimiento** (copiable) para reportar un problema.
- La valoración y la clasificación pueden enviarse aunque el estado sea `contingencia`. En `sin-conexion` los
  controles se deshabilitan con una explicación (no se pierde lo escrito).

## 4. Paleta y contraste

Colores como variables CSS `--kerna-<estado>-fondo`, `-texto` y `-acento`, coherentes con Bootstrap y con
`client/app/css/components/libs/bootstrap/bootstrap.scss` (azul Veridy `#205782`, rojo `#DE1B1B`, amarillo
`#FFD644`, grises `#F5F7FA` a `#1D1F24`). Nota: en ese tema `$success` está asignado al azul de la marca, de modo que
**no se reutiliza `bg-success`** y el verde de "lista" es propio. El estado `valorada` usa el azul Veridy; `generando`,
un azul claro de la misma familia.

Razones de contraste WCAG calculadas con `kerna/docs/diseno/calcular_contraste.py` (fórmula de luminancia
relativa, sin redondear; `python3 calcular_contraste.py --verificar` además comprueba que la maqueta use los mismos
colores). Mínimos: texto 4,5:1 (1.4.3) y componentes 3:1 (1.4.11): borde y glifo contra el fondo de la etiqueta y
contra la página blanca.

| Estado | Fondo | Texto | Acento | Texto/fondo (≥4,5) | Acento/fondo (≥3) | Borde/página (≥3) | Fondo/página (informativo) |
|---|---|---|---|---|---|---|---|
| `sin-info` | `#F5F7FA` | `#434A54` | `#707A8A` | 8,34 | 4,04 | 4,34 | 1,07 |
| `generando` | `#DCEBF8` | `#12324F` | `#2A6496` | 10,84 | 5,14 | 6,25 | 1,22 |
| `lista` | `#DDF3E4` | `#11432A` | `#2E7D4F` | 9,68 | 4,33 | 5,05 | 1,17 |
| `contingencia` | `#FFF2BF` | `#4D3A00` | `#8F6B00` | 9,74 | 4,38 | 4,92 | 1,12 |
| `revision-tiempo` | `#FFE2C4` | `#5C2C05` | `#A85400` | 9,31 | 4,30 | 5,34 | 1,24 |
| `revision-citas` | `#EAE4F7` | `#2E1F63` | `#6A4FB3` | 11,35 | 5,01 | 6,21 | 1,24 |
| `sin-normativa` | `#DDEFF0` | `#0F4249` | `#2C7C86` | 9,33 | 4,08 | 4,84 | 1,19 |
| `cadena-agotada` | `#FDE0DD` | `#7A1212` | `#C62828` | 8,78 | 4,52 | 5,62 | 1,24 |
| `nucleo-no-disponible` | `#FBDCEA` | `#6B0F3B` | `#B02A6B` | 9,41 | 4,88 | 6,20 | 1,27 |
| `conector-inactivo` | `#E7E2D6` | `#433818` | `#7D6D45` | 8,94 | 3,92 | 5,07 | 1,29 |
| `sin-conexion` | `#323A49` | `#FFFFFF` | `#FFFFFF` | 11,43 | 11,43 | 11,43 | 11,43 |
| `valorada` | `#205782` | `#FFFFFF` | `#FFFFFF` | 7,64 | 7,64 | 7,64 | 7,64 |

| Elemento fijo | Primer plano | Fondo | Razón | Mínimo |
|---|---|---|---|---|
| Tooltip: texto / fondo | `#FFFFFF` | `#1D1F24` | 16,49 | 4,5 |
| Aviso permanente: texto / fondo | `#1D1F24` | `#EBEFF5` | 14,29 | 4,5 |
| Aviso de contingencia: texto / fondo | `#4D3A00` | `#FFF2BF` | 9,74 | 4,5 |
| Enlace (azul Veridy) / blanco | `#205782` | `#FFFFFF` | 7,64 | 4,5 |
| Anillo de foco / blanco | `#205782` | `#FFFFFF` | 7,64 | 3,0 |

Todo cumple. Observaciones: (1) el fondo claro de las etiquetas contra la página blanca tiene razón de 1,07 a 1,29,
por eso **cada etiqueta lleva borde de 1,5 px** con el color de acento (3,9 a 6,3 contra la página), que es lo que
cumple 1.4.11, no el relleno; (2) en los estados oscuros el borde es el propio fondo; (3) el estado es identificable
sin color por el texto y la silueta (1.4.1).

## 5. Restricciones técnicas

- **SVG propio en línea** (plantillas de Angular, sin `innerHTML`, por las `trusted-types` de la política de
  seguridad); sin recursos externos, sin fuentes remotas, sin imágenes `data:` (la política admite `img-src 'self'`).
- **Ícono en un solo lugar**: `kerna-icono.component.ts`. Los SVG candidatos son monocromos con `currentColor`, caja
  `viewBox="0 0 24 24"`, y toman el color del acento del estado (o blanco en los oscuros), sin tocar nada más.
  Los glifos de estado están aparte (`kerna-glifo.component.ts`) y no dependen de la opción elegida.
- Textos en `es.json` con el prefijo `kerna.`; plantillas sin cadenas fijas.
- Visible solo para destinatarios (la página `pages/recipient/tip` ya lo es) y solo si existe la cuenta de Kerna.
- Pruebas (Playwright, una por estado) con el conector y el núcleo simulados: la maqueta y las capturas de
  `opciones-icono/` sirven de referencia visual.

## 6. Opciones de ícono

Las fichas están en `opciones-icono/README.md` (ventajas y riesgos según la investigación, **sin recomendar una**).
SVG en `opciones-icono/svg/`: `robot.svg`, `v-veridy.svg`, `articulo-marcado.svg`, `balanza.svg`.

## 7. Maqueta y capturas

- Maqueta estática y autocontenida: `opciones-icono/maqueta/maqueta.html`, parametrizable por URL, por ejemplo
  `maqueta.html?icono=balanza&estado=contingencia&variante=local`. Reproduce la barra del caso de Veridy con el logo
  de ejemplo, el indicador, el tooltip abierto y el panel.
- Capturas: `opciones-icono/<opcion>--<estado>.png` (4 opciones x 12 estados, más las variantes
  `contingencia-local` y `contingencia-recuperacion-local`) e `iconos-tamanos.png` (24, 20 y 16 px, claro y oscuro).
- Para repetirlas: `kerna/docs/diseno/opciones-icono/generar_capturas.sh` (imagen
  `mcr.microsoft.com/playwright/python:v1.49.0-noble`, versión fijada; el paquete Python de Playwright se instala dentro
  del contenedor y los navegadores ya vienen en la imagen; no se instala nada en el host).
- La maqueta usa texto de ejemplo para las citas: no son citas reales de las leyes.

## 8. Preguntas abiertas

1. ¿Qué es exactamente la "clasificación manual" de Veridy para el panel: el cambio de estado y subestado del caso
   (`openModalChangeState`) y la etiqueta, o una clasificación por normativa que aún no existe? La propuesta supone lo
   primero y deja el panel en la fila de la información del caso.
2. ¿Cómo reconoce el cliente la cuenta de servicio de Kerna de forma fiable (nombre visible configurado, o un dato que
   exponga el servidor)? Sin eso las notas de otro destinatario podrían hacerse pasar por Kerna.
3. Umbrales (5 min, 6 min, 24 h) y intervalo de consulta (20 s): validar con datos reales.
4. ¿El texto "Kerna" basta como marca, o se prefiere además "asistente"? Depende de la prueba con auditores.
5. Fricción de la clasificación (casillas sin marcar, ¿exigir abrir la cita?): probar con auditores.
6. Valoración: ¿qué se promete exactamente sobre su uso? (el texto debe ser cierto)
7. ¿Se muestra el nombre de la ley principal con su número y título ("Ley N.° 21.643") o solo el número? Depende de lo
   que publique el conector en `norma`.
8. Señal de mantenimiento de Veridy: no se verificó que el servidor entregue una distinta de un fallo de conexión.
9. Elección del ícono: de la usuaria.
10. Si la Ley de IA de la UE aplica a Kerna (referencia usada en la investigación) es una cuestión legal pendiente.

## 9. Implementación: lo que difiere de la propuesta

Archivos nuevos en `client/app/src/shared/partials/kerna/`: `kerna-notas.ts`, `kerna-estados.ts`, `kerna-icono.component.ts`
(ícono `articulo-marcado`, único lugar), `kerna-glifo.component.ts`, `kerna-indicador.component.{ts,html}`,
`kerna-panel.component.{ts,html}`, `kerna.service.ts` y `kerna-pruebas.ts` (pruebas de la lógica pura). Cambios mínimos en
`tip.component.{ts,html}` (dos componentes y dos líneas de plantilla), `tip-comments.component.{ts,html}` (getter
`comentariosVisibles`, solo rol `receiver`), `es.json` y `en.json` (claves nuevas `kerna.*`) y `css/main.css` (sección
final, sin estilos en línea).

- **Cuenta de servicio**: el destinatario del caso (`tip.receivers`, campos `id` y `name`) cuyo nombre empieza con
  "Kerna AI" (`PREFIJO_CUENTA_KERNA` en `kerna-notas.ts`). `kerna_sugerencia` y `kerna_estado` valen solo si su `author_id` es
  esa cuenta; `kerna_feedback` y `kerna_clasificacion`, solo si son de otro destinatario del caso. Todas deben ser notas
  `internal` comunes. Sin esa cuenta no se muestra nada.
- **Textos**: los de `textos-finales.md`, con sus dos variantes de `contingencia` y de `conector-inactivo`. Se agregaron
  claves que ese archivo no trae: título del panel, etiquetas "Resumen" y "Modo" del tooltip, "Valoración de la
  sugerencia", "Enviar valoración", "Valoración enviada", "Agregar", "Quitar" y el resumen de un solo artículo
  ("{norma} · 1 artículo"). Las claves están en `en.json` con el mismo texto en español (si no, un idioma sin
  traducción mostraría la clave); los demás idiomas muestran la clave hasta que se traduzcan.
- **Tooltip**: sin la antigüedad ("hace 2 min") de la propuesta; está siempre en el DOM (oculto) para que
  `aria-describedby` apunte a él, y se muestra con puntero (tras 200 ms) o foco.
- **Panel**: cerrado por defecto; sin botón "Clasificar manualmente"; en `valorada` muestra la clasificación guardada y deja
  guardar una nueva (vale la última); la valoración usa un botón "Enviar valoración" y la observación aparece al elegir.
- **Consulta periódica** (20 s mientras el estado es provisional): usa un `HttpClient` sin interceptores, porque el
  interceptor global muestra el panel de carga que bloquea la pantalla en cada petición. `sin-conexion` se activa con dos
  fallos seguidos, con el evento `offline` del navegador o si falla un envío.
- **Valoración**: "Este artículo corresponde / no corresponde al caso" (arriba/abajo) por artículo.
- **Verificación**: el cliente compila (`ng build --configuration development`); 40 casos de la lógica pura; un arnés
  temporal con el cliente real compilado (indicador y panel con las dependencias simuladas) comprobó los 13 estados, el
  tooltip (hover, foco, Esc, persistencia), el envío de notas y la ausencia del bloque para el denunciante;
  `kerna/pruebas/e2e/test_bloque_kerna.py` (21 pruebas) solo se ha recolectado, no ejecutado contra una instancia.
