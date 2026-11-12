# Rendimiento y íconos del front (v3)

Medido en producción con Chromium (Playwright) y CDP, escritorio 1366×850, 10 s en reposo. Antes = commit fbe737c88; después = esta versión.

## Qué pesaba
1. **El servidor, no el navegador.** `/panel/informe` tardaba 9 a 17 s en responder (12 consultas KQL y 2 lecturas de tablas, una tras otra; dos consultas de 7 s cada una). `/panel` tardaba 0,25 s (2 s en frío). En reposo el navegador gastaba 5 a 6 ms de CPU cada 10 s: los SVG no consumían nada parado.
2. Sin compresión y sin caché de estáticos: 1,3 MB por vista (ECharts 1,0 MB sin comprimir).
3. Nodos y capas: 70 a 87 `<svg>` por vista (logos de menú armados con JS, fondos de órbitas y trama guilloché como data-URI), 458 nodos SVG en el Resumen.

## Qué se cambió
- Consultas en paralelo (`cache.paralelo`), caché compartida con refresco en segundo plano (`cache.obtener`: entrega lo guardado y recalcula aparte), precalentado al arrancar y reintento si casi todo falla. La petición ya no espera a Log Analytics.
- Informe: si no hay datos calculados sale el esqueleto y el cuerpo llega por `/panel/informe/cuerpo`; las tablas llegan por `/panel/informe/datos` solo al abrir «Datos».
- gzip en HTML, CSS y JS; estáticos con `?v=` en `Cache-Control: immutable` de un año (sin `?v=`, 7 días).
- ECharts propio (617 KB, 213 KB comprimido, antes 1,0 MB y 333 KB): solo barras, líneas, anillos y mapa de calor, renderer canvas, una instancia por gráfico visible creada al entrar en pantalla (IntersectionObserver), destruida al cambiar de pestaña, animación solo de entrada. Ajustes y la portada ya no cargan ECharts.
- Decoración rasterizada (WebP con transparencia, 2x): trama guilloché (2 imágenes), órbitas de fondo (2 capas que giran con CSS transform) y símbolo del menú. El logo de la portada sigue vivo porque reacciona al cursor y al scroll.
- Íconos de estado de la identidad Núcleo en un sprite estático de 13 KB (3 KB comprimido).

## Por qué no GIF
GIF tiene 256 colores, transparencia de un solo bit (bordes serruchados sobre fondos de color) y pesa más que WebP para el mismo dibujo. Un trazo punteado fino necesita semitransparencia, y el GIF no la tiene. Además, un GIF animado se repinta cuadro a cuadro en la CPU. WebP con alfa pesa 25 a 55 KB por capa y la rotación se hace con `transform` (compositor, sin repintar). Si alguna animación no pudiera hacerse con capas que giran, la alternativa sería un video WebM corto en bucle (muted, playsinline, pausado fuera de pantalla) con póster estático; no hizo falta.

## Antes y después
| Métrica | /panel antes → después | /panel/informe antes → después | /panel/negocio antes → después |
|---|---|---|---|
| Respuesta del servidor (TTFB), caliente | 0,25 → 0,05 s | 9,1 a 17,3 → 0,05 s | 0,04 → 0,05 s |
| TTFB en frío (primera visita tras reiniciar) | 2,1 → 0,2 a 0,4 s (con precalentado; 5,6 s si se pide antes de que termine) | 9,1 → 0,15 s | 0,04 → 0,07 s |
| Primer contenido (FCP) | 14,5 s* → 0,27 s | 9,2 s → 0,22 s | 0,21 → 0,26 s |
| Contenido principal (LCP) | n/m → 0,40 s | n/m → 0,22 s | n/m → 0,47 s |
| Carga completa (evento load) | 14,6 s* → 0,32 s | 9,2 s → 0,30 s | 0,39 → 0,31 s |
| Peso transferido | 1.269 → 464 KB | 1.296 → 444 KB | 1.278 → 465 KB |
| Elementos DOM / nodos SVG / `<svg>` | 916 / 458 / 71 → 508 / 62 / 54 | 1.444 / 119 / 75 → 527 / 66 / 62 | 876 / 247 / 87 → 693 / 78 / 71 |
| Scripting al cargar | 203 → 191 ms | 81 → 261 ms (ECharts + 2 canvas) | 307 → 136 ms |
| Layout + estilos al cargar | 93 → 74 ms | 91 → 55 ms | 112 → 95 ms |
| CPU en reposo (10 s) | 6,4 → 4,1 ms | 4,9 → 4,7 ms | 5,2 → 4,5 ms |
| CPU al desplazarse (tarea total, 30 pasos) | 172 → 236 ms | 63 → 29 ms | 122 → 234 ms |
| CLS | n/m → 0,001 | n/m → 0,008 | n/m → 0,003 |
| Alto de la página (1366 px) | 1.791 → 1.775 px | 4.666 → 850 px | 2.292 → 2.192 px |
| Alto en móvil (390 px) | 2.882 → 2.865 px | 6.000+ → 1.742 px | 3.645 → 3.440 px |

\* esa medición del Resumen «antes» cayó en un frío del servidor; en caliente era 0,25 s de TTFB y carga cercana a 0,4 s.
n/m = no medido antes (se agregó LCP y CLS a la medición). El costo de desplazarse sube en Resumen y Negocio porque los gráficos se crean al entrar en pantalla (antes se creaban todos al cargar).

## Íconos de estado: mapeo (identidad Núcleo, paleta B)
| Estado del front | Ícono | Tono |
|---|---|---|
| Bien / lista | `lista` | verde |
| Atención / modelo con contingencia | `contingencia-modelo` | ámbar |
| Mal / cadena agotada | `cadena-agotada` | rojo |
| Sin datos | `sin-info` | neutro |
| En proceso | `generando` | azul |
| Proveedor sin información | `sin-conexion` | gris |
| Revisión manual (citas, tiempo), búsqueda | `revision-citas`, `revision-tiempo`, `contingencia-busqueda` | violeta, naranja, ámbar |
Lucide queda solo para íconos utilitarios (descargar, menú, flechas, calendario). Los colores semánticos `--ok/--warn/--bad/--na/--pro` salen de la paleta B: texto = acento mezclado 68 % hacia el fondo del tono, barra = mezcla 50 %, tinte = acento al 14 % sobre blanco. Contraste (WCAG): texto/blanco 6,1 a 9,3; texto/tinte 5,5 a 8,2; barra/blanco 3,9 a 6,6 (mínimos 4,5 y 3). Se genera y verifica con `herramientas/construir_iconos_estado.py`.
