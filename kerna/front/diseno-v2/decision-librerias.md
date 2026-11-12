# Decisión de librerías para el front de Kerna (v2)

Requisitos: FastAPI + plantillas Jinja, App Service F1 (sin build de Node en el servidor), accesible, responsive, gráficos legibles, poco peso.

## Combinación elegida
| Capa | Elección | Por qué |
|---|---|---|
| Estilos y componentes | **Tailwind CSS 3.4** + componentes propios con tokens en `:root` (patrón shadcn/ui: tarjetas, chips, interruptores, segmentos) | Es el estándar de facto en SaaS modernos, da consistencia (espaciado, tipografía, estados) y permite usar los tokens de marca. En la maqueta va por CDN "play"; en el front real se compila **sin Node** con el binario *Tailwind standalone CLI* en `desplegar.sh` y se sirve un único `.css` estático. |
| Interacción | **Alpine.js 3.14** | 15 KB, declarativo, encaja con plantillas del servidor, sin paso de build. Cubre vistas, asistente de 3 pasos, interruptores, resumen de cambios y estado de generación. |
| Gráficos | **Apache ECharts 5.5** (render SVG) | Cubre sin plugins lo que pide el diseño: áreas y barras apiladas, líneas de meta, anotaciones de incidentes, gauge, mapa de calor, tooltips y ajuste responsive. Renderiza SVG (nítido, accesible con `aria`). |
| Íconos | **Lucide 0.469** | Trazo consistente y legible, ISC. Se usan por un elemento propio `<k-ic>`; en producción se incrustan solo los usados (sprite) para no cargar la librería completa. |
| Tipografía | **Inter** (cuerpo) + **Unbounded** (solo títulos y marca) | La identidad de Kerna queda en logo, lima y títulos; el producto se lee en una sans neutra. |

## Alternativas evaluadas
- **DaisyUI / Flowbite**: aceleran, pero imponen un aspecto genérico y dificultan que los semáforos y tokens de marca se apliquen con precisión. Componentes propios sobre Tailwind dan más control con poco código.
- **Chart.js**: más liviano (~200 KB frente a ~1 MB de ECharts), pero requiere plugins para anotaciones, gauge y heatmap, y su tooltip/responsive es más pobre. Con F1 y caché del navegador el peso de ECharts es aceptable; se puede reducir con una build personalizada.
- **htmx / Bootstrap / Material**: htmx no cubre estado de UI local; Bootstrap y Material dan un aspecto más anticuado o pesado.

## Para el front real
Copiar los archivos de las librerías a `app/estaticos/` (sin depender de CDN, como hoy con las fuentes), compilar Tailwind con el CLI standalone al desplegar y mantener los tokens de color de `maqueta.html` como fuente de verdad. Semáforo: verde = bien, ámbar = atención, rojo = problema, gris = sin datos; el lima es solo acento de marca. Nunca solo color: siempre ícono + texto.

Nota de maqueta: ECharts se carga desde jsDelivr porque la versión 5.5.1 no está en cdnjs.
