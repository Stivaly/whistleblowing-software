# Textos del indicador y del bloque de Kerna

Redacción vigente de cada estado. Reemplaza los borradores de la sección 2.5 de `propuesta-bloque-kerna.md` y es la
fuente de las claves `kerna.*` de `client/app/assets/data/l10n/es.json`. Cada mensaje dice qué pasó, qué significa
para el caso y qué puede hacer el auditor. Ninguno bloquea el trabajo manual.

Ícono de marca vigente: `articulo-marcado` (se cambia en `kerna-icono.component.ts`; las demás opciones están en
`opciones-icono/svg/`).

Textos fijos:
- Aviso permanente del panel: "Sugerencia asistida: no es un dictamen jurídico. La decisión y la clasificación final son tuyas."
- Pie del tooltip: "Abre el detalle con clic o Enter. Esc cierra este aviso."
- Código: "Código de seguimiento (para reportar un problema)". Botón: "Copiar código". Confirmación: "Código copiado".
- Valoración: "Este artículo corresponde al caso" / "Este artículo no corresponde al caso". Observación: "Observación (opcional)".
- Clasificación: "Incluir en la clasificación", "Agregar otro artículo", "Guardar clasificación", "Ninguno aplica".
- Enlace: "Ver el artículo en la Biblioteca del Congreso Nacional".
- Acciones: "Actualizar", "Reintentar".

| Estado | Etiqueta | Título del tooltip | Mensaje en el panel |
|---|---|---|---|
| `sin-info` | Sin información de Kerna | Aún no hay información de Kerna para este caso | Aún no hay información de Kerna para este caso. Puede ser un caso recién recibido o anterior a la activación de Kerna. Puedes clasificarlo como siempre; si llega una sugerencia, aparecerá aquí. |
| `generando` | Preparando sugerencia | Kerna está preparando la sugerencia | Kerna recibió el caso y está buscando los artículos que podrían aplicarse. Suele tardar pocos minutos. Puedes seguir trabajando en el caso; la sugerencia aparecerá aquí cuando esté lista. |
| `lista` | Sugerencia lista | Sugerencia lista | (sin mensaje: el panel muestra los artículos) |
| `contingencia` (modo respaldo o local) | Sugerencia lista · modo alternativo | Sugerencia lista, preparada en modo alternativo | Esta sugerencia se preparó con un modelo alternativo, porque el habitual no estaba disponible. Las citas fueron verificadas igual, pero la selección de artículos puede ser menos precisa. Revisa cada artículo con especial atención. |
| `contingencia` (recuperación local) | Sugerencia lista · búsqueda alternativa | Sugerencia lista, con búsqueda alternativa de normas | Para esta sugerencia las normas se buscaron con un método alternativo, porque el habitual no estaba disponible. Las citas fueron verificadas igual, pero puede faltar algún artículo pertinente. Revisa la sugerencia con especial atención. |
| `revision-tiempo` | Sin sugerencia · tiempo excedido | Kerna no alcanzó a terminar a tiempo | Kerna tardó más de lo permitido en preparar la sugerencia y se detuvo. Este caso no tendrá sugerencia. Clasifícalo como siempre. |
| `revision-citas` | Sin sugerencia · citas no verificadas | La sugerencia no superó la verificación de citas | Kerna preparó una sugerencia, pero sus citas no coincidían con el texto vigente de las normas. Por seguridad no se muestra ningún artículo. Clasifica el caso como siempre. |
| `sin-normativa` | Sin normativa encontrada | Kerna no encontró normas aplicables | Kerna no encontró, entre las normas que conoce, artículos que correspondan con claridad a este caso. Eso no significa que no exista normativa aplicable. Clasifica el caso según tu criterio. |
| `cadena-agotada` | Sin sugerencia · no se pudo generar | Kerna no pudo preparar la sugerencia | Kerna no pudo preparar la sugerencia de este caso por una falla propia. Este caso no tendrá sugerencia. Clasifícalo como siempre; si se repite en otros casos, reporta el código de seguimiento. |
| `nucleo-no-disponible` | Kerna no disponible | Kerna no está disponible en este momento | Kerna no está disponible en este momento. El caso quedó en espera y se seguirá intentando automáticamente. Puedes clasificarlo como siempre; la sugerencia aparecerá aquí cuando Kerna vuelva. |
| `conector-inactivo` (sin ninguna nota) | Kerna sin respuesta | Kerna todavía no ha recibido este caso | Ya pasó el tiempo habitual y Kerna todavía no ha recibido este caso. Por ahora no habrá sugerencia. Clasifícalo como siempre; si ocurre en varios casos, avisa a quien administra la plataforma. |
| `conector-inactivo` (en proceso hace demasiado) | Kerna sin respuesta | Kerna recibió el caso, pero no ha respondido | Kerna recibió este caso, pero la sugerencia no ha llegado en el tiempo habitual. Puede que llegue más tarde. Clasifica el caso como siempre; si ocurre en varios casos, reporta el código de seguimiento. |
| `sin-conexion` | Sin conexión | No se pudo actualizar la información de este caso | No se pudo actualizar la información de este caso: se perdió la conexión con la plataforma. Lo que ves puede estar desactualizado. Reintenta en unos minutos; lo que ya guardaste no se pierde. |
| `valorada` | Clasificación guardada | Clasificación final guardada | Tu clasificación de este caso quedó guardada. Si necesitas corregirla, guarda una nueva: vale la última. |

Resumen del tooltip: "{norma} · {n} artículos" cuando hay sugerencia; "Sin sugerencia" en los estados de revisión
manual; "Sin resultados todavía" en los demás. Modo: "Modo habitual", "Modo alternativo", "Búsqueda alternativa",
"Revisión manual" o "Aún no disponible".
