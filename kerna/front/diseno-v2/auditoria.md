# Auditoría de la maqueta (kerna/front/diseno-v2/maqueta.html)

Método: Playwright 1.64.0 en Docker (`mcr.microsoft.com/playwright/python:v1.64.0-noble`), capturas a 1440x900 y 400x860 de portada, resumen, negocio, ajustes (y su resumen de cambios), informe (pasos 1 a 3, cargando y listo) y tooltip. Se midió también desbordamiento horizontal y errores de consola. Capturas finales en `capturas/` (prefijo `final-`, `-d` escritorio, `-m` móvil).

Checklist: jerarquía visual, densidad, alineación, contraste AA, consistencia de componentes, legibilidad de gráficos, estados vacíos, tooltips, foco de teclado, responsive, semáforo consistente, información orientada a decisiones.

## Ronda 1 (primer render)
| Hallazgo | Corrección |
|---|---|
| Los gráficos no aparecían: ECharts 5.5.1 no existe en cdnjs (404) | Se carga desde jsDelivr con versión exacta |
| Deslizadores de Ajustes deshabilitados (`:disabled` evaluaba `undefined`) | `!!(dep && !valor)` |
| Gráficos de Negocio quedaban con ancho 0 al cambiar de vista | `ResizeObserver` por gráfico |
| En móvil las 4 tarjetas de salud ocupaban una columna y alargaban la página | Cuadrícula de 2 columnas desde 400 px |
| Mapa de calor: texto blanco sobre celdas claras (contraste bajo) | Texto oscuro bajo 10 denuncias, blanco sobre celdas oscuras |
| Tarjeta de latencia con gran espacio vacío | Se añadió "¿Dónde se va el tiempo de un caso?" con conclusión |
| Cliente C inactivo aparecía con "uso sano del plan" (contradicción) | Estado ámbar y nota "se detuvo" |
| Embudo de adopción con 86 fijo, distinto al 89 del resumen | Valor derivado del mismo cálculo |
| Eje superior "segundos" cortado; pico fuera de escala | Más margen superior y máximo 70 |

## Ronda 2
| Hallazgo | Corrección |
|---|---|
| Títulos de sección del informe sin peso (el reset de Tailwind los dejó finos) | h3 en negrita y color de marca |
| "17 casos" partido en dos líneas en la tabla de incidentes | Columna de 100 px y sin salto |
| Pasos del asistente truncados en móvil ("Vista ...") | Solo el paso activo muestra su nombre |
| Símbolo decorativo de la portada pisaba el texto de la tarjeta de ejemplo | Fondo al 9 % y desplazado a la esquina |
| Titular de portada sin acento de marca | Subrayado lima en "segundos" |
| Barra de progreso de generación invisible (el `:style` borraba el fondo) | Fondo y ancho en el mismo `:style` |
| Leyenda del área apilada por cliente con colores distintos a las series | `itemStyle` explícito |
| Eje de la proyección cortaba "US$" | Margen izquierdo de 62 px |
| Casilla "sección de negocio" no aparecía en la vista previa durante la prueba | Verificado: la sección 7 aparece al activarla |

## Resultado final
- Sin errores de consola ni desbordamiento horizontal en ninguna vista a 400 y 1440 px.
- Contraste: texto secundario #4F5B85 sobre blanco 6,1:1; chips verde 4,8:1, ámbar 5,0:1 o más, rojo 6,5:1; las barras de gráficos usan tonos de 3:1 o más y siempre llevan ícono y texto al lado, nunca solo color.
- Foco de teclado: anillo de 3 px en todos los controles; los "?" abren con foco, pasar el mouse o toque, y se cierran con Esc; interruptores con `role="switch"`, deslizadores nativos con `aria-valuetext`.
- Estados vacíos presentes (valoraciones, leyes más frecuentes) en gris, con explicación y qué esperar.

## Pendiente para el front real (no resuelto en la maqueta)
- Compilar Tailwind y alojar localmente las librerías (la maqueta usa CDN).
- Selector de fecha nativo muestra el formato del navegador; valorar un calendario propio.
- "Plan contratado", tarifa, clientes B y C y valoraciones son supuestos: el almacén (`solicitud`, `sugerenciaarticulo`, `valoracion`, `clasificacion`) no tiene plan ni tarifa; hay que definir dónde se guardan.
- "Casos pendientes de reintento", salud por componente y mapa de horarios requieren consultas nuevas.
- Dos colores del semáforo (ámbar sobre blanco en barras) rozan 3:1; mantener siempre la etiqueta de texto.
