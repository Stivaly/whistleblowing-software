# Dirección de diseño del panel de Kerna AI

Reemplaza las instrucciones de diseño anteriores. Vale para Resumen, Negocio, Ajustes, el informe de gestión y su PDF. La portada no se toca.

## 1. Idea central

El panel no es una grilla de tarjetas. Es una **sala de control orbital**: la identidad Núcleo (kerna/diseno/identidad-v3, lámina `lamina-comparativa.png`, columna B, versión en fondo claro de `capturas-claro/`) se usa como lenguaje para mostrar datos, no como adorno.

- **Núcleo:** el total del período (las denuncias, o el ingreso en Negocio).
- **Órbitas:** lo que les pasó (modos, etapas, leyes).
- **Satélites:** las unidades, con su tamaño o posición según el dato y su color según el estado.
- **Estados:** se muestran con las ilustraciones de la librería B (sugerencia lista, modo alternativo, no se pudo, sin información, tiempo excedido…), nunca con un visto, un «!» o una cruz genéricos.

Cada vista se lee como una lámina: **una frase titular**, **una visualización protagonista** y **datos de apoyo en bandas finas**. El ojo recorre de arriba abajo y en 5 segundos sabe cómo va todo.

## 2. Reglas que no se negocian

0. **Optimizar no es quitar:** lo que la usuaria aprobó (los paneles azules orbitales de Ajustes, el logo vivo, la identidad) se conserva y se hace más liviano. Antes de eliminar cualquier elemento visual, comprueba que no fue aprobado (en `pendientes/` o en esta guía); si hay duda, se optimiza y no se elimina.

1. **Ningún hueco:** ningún bloque tiene más de 16 px de espacio interno vacío. Un bloque mide lo que mide su contenido. Si algo queda vacío, se rediseña el bloque o se elimina; nunca se rellena con aire.
2. **Las tarjetas son la excepción:** se usan solo para algo agrupado e interactivo (por ejemplo, la cola de reintentos con su botón). Lo demás va sobre el fondo de la página, en **bandas** separadas por la línea punteada de la identidad (puntos de 1,5 px cada 8 px). No hay tarjeta por métrica.
3. **La columna se elige según el dato:** usa ancho completo para lo protagonista, una fila de métricas en banda para los KPI, y 2 columnas solo cuando dos cosas se comparan.
4. **Texto:** el título se explica solo; no hay frases de contexto ni de misión. El «?» lleva una línea con qué significa o qué cambia. Las cifras siempre van con unidad y con el color de su estado. Nada menciona el informe académico, capítulos ni tablas.
5. **Estados vacíos:** si no hay dato, la sección no se muestra, o se muestra en una línea con el ícono «sin información» pequeño y «—». Nunca hay una tarjeta grande que diga «sin datos».
6. **Movimiento:** solo se mueve lo que reacciona (cursor, clic, datos en vivo). La decoración es estática.
7. **Espacio y alineación:** el contenido va pegado al menú lateral (gutter de 24 px), es fluido hasta 1.440 px y está alineado a la izquierda. En móvil, una columna sin scroll horizontal (`scrollWidth == clientWidth` a 360, 375, 390 y 414 px).

## 3. Sistema visual

| Elemento | Regla |
|---|---|
| Espaciado | Escala 4 · 8 · 12 · 16 · 24 px. Entre bandas, 24 px. Dentro de una banda, 8–12 px. |
| Cifras | Unbounded 700. Protagonista: 40–44 px. Banda de KPI: 28–32 px. Listas: 16–18 px. |
| Rótulos | JetBrains Mono 11–12 px, mayúsculas, con tracking. |
| Texto | Inter 13–14 px. |
| Colores de estado | Verde (bien), ámbar (atención), coral (mal), gris (sin dato), azul (en proceso). Valores de la paleta B en `paletas.json`. |
| Colores de categoría | La paleta B de 8 colores (lima, verde, azul, amarillo, naranja, coral, cian, violeta), cada uno con un significado fijo en todo el panel. Por ejemplo: modelo principal = verde, respaldo = amarillo, revisión manual = coral, búsqueda = cian, redacción = violeta. |
| Íconos | Librería B-* completa, con el dibujo orbital, a 40–56 px en estados y KPI. A 20–24 px solo una simplificación del mismo dibujo. Íconos de ley (Karin, Datos personales, Responsabilidad penal) junto a cada ley. Si falta un concepto (costo, tiempo, ingreso, cliente, ajustes), se diseña en el mismo lenguaje y se suma al sprite. |
| Corte de esquina | Solo en la tarjeta excepcional y en las baldosas de estado. |
| Gráficos | 160–220 px de alto. Sin cuadrícula pesada: ejes mínimos, etiquetas directas sobre las series en vez de leyendas cuando se pueda, y meta como línea punteada coral. |

## 4. Resumen

**Barra de título (1 línea, ~56 px):**
- A la izquierda: «Resumen», el punto «En vivo» y el período (7 / 30 días).
- A la derecha: los 3 proveedores como glifos orbitales de 28 px con su nombre al pasar el cursor; un satélite apagado o coral indica caída.
- El botón «Informe».

**Banda protagonista (ancho completo, ~260 px):**
- **Izquierda, el diagrama orbital del período:**
  - Núcleo con «303 denuncias».
  - Tres anillos concéntricos, uno por modo: principal, respaldo y revisión manual.
  - En cada anillo, un arco proporcional al porcentaje, del color de su categoría, con un satélite al final del arco que lleva la cifra (17 · 15 · 271).
  - Reemplaza «Denuncias», «¿Cómo se resolvieron?» y «Denuncias por día».
- **Derecha:**
  - Una **frase titular** en Unbounded de 20–24 px, armada con los datos. Ejemplo: «11 % recibió sugerencia. 271 casos esperan reintento.» La frase se arma con reglas a partir de los datos; no la genera un modelo.
  - Debajo, la cola de reintentos en línea: la ilustración de estado del motivo (modo alternativo o no se pudo) a 40 px, «173 · modelos no disponibles», «98 · tiempo excedido» y el botón «Reintentar ahora».

**Banda de KPI (una fila, ~96 px, sin tarjetas, separadores punteados verticales):**
Acierto · Respuesta · Costo · Sugerencias valoradas. Cada uno lleva:
- el ícono de identidad de 40 px;
- la cifra con el color de su estado;
- una barra bala (bullet) de 120 px con la marca de la meta;
- el estado en una palabra.

**Banda «El camino de una denuncia» (ancho completo, ~180 px):**
- Las 5 etapas (anonimizar, clasificar, buscar en la ley, redactar, verificar citas) como satélites sobre una órbita horizontal.
- El tamaño del satélite es proporcional al tiempo de la etapa, y su color es el de la categoría de la etapa, o coral si es la que más demora.
- Debajo de cada satélite, el tiempo («12 s»). A la derecha, «caso típico 27 s · 9 de cada 10 < 135 s · meta 15 s».
- Reemplaza «Rapidez» y «¿Dónde se va el tiempo?».

**Banda «Acierto por ley» (~120 px):**
- Una fila de pequeños múltiplos, uno por ley: el ícono de la ley, un anillo de 64 px con el porcentaje de acierto, una marca en 80 % y el porcentaje al centro con el color de su estado.
- Debajo del anillo, una etiqueta corta («Ley Karin»). Al lado, «Leyes más sugeridas» como chips con su conteo, solo si hay datos.

**Banda «Cuándo llegan» (~120 px):** el mapa de calor de 7×24, compacto. Solo se muestra con 7 días o más de datos.

**Meta:** 1366×850, Resumen en ≤ 1,3 pantallas.

## 5. Negocio

- **Barra de título:** igual que en Resumen.
- **Banda protagonista:**
  - **Izquierda:** la frase titular. Ejemplo: «Este mes: 31,87 UF de ingreso y −0,34 UF de utilidad».
  - **Derecha:** una cascada compacta de ~200 px: ingreso en verde, descuentos en coral (costo de servir, parte de Veridy, fijos, depreciación e intereses, impuesto) y resultado con el color de su estado. Etiquetas directas.
- **Banda de KPI**, como en Resumen: Margen operativo (con medidor pequeño) · Costo de servir · Con sugerencia · Valoradas.
- **Banda «Clientes»:**
  - Cada cliente con uso es una fila de ~44 px: nombre · plan, un anillo de capacidad del plan (el uso que pasa de 100 % se dibuja como un satélite fuera del anillo, en coral), ingreso · costo y último uso.
  - Los clientes sin uso van en una sola línea plegada: «4 con contrato, sin uso registrado».
- **Banda «Proyección»:**
  - En la línea del título, chips de valor actual neto, retorno, índice y recuperación.
  - Gráfico de 200 px con los ingresos, los costos y la utilidad de cada año, y el número de clientes como etiqueta sobre cada año.
  - «Ver tabla» plegado justo debajo.
- **Meta:** ≤ 1.100 px.

## 6. Ajustes

- **Se conserva lo que la usuaria aprobó:** cada sección tiene su panel de fondo azul (tinta de la identidad) con la ilustración orbital que muestra el efecto del ajuste. Los satélites, órbitas y equipos cambian al mover los controles. Ver `kerna/front/diseno-v2/maqueta.html` (clase `.mod-art` / `.orb-svg`) y la captura `kerna/front/diseno-v2/capturas/v4-despues-ajustes-d.png`. **No se elimina: se optimiza.**
  - Las órbitas y tramas de fondo son una imagen estática (WebP 2x) que gira con CSS transform.
  - Solo los satélites y estados que cambian con el control son SVG vivos, que se actualizan al mover el control, sin animación infinita.
  - El panel azul mide lo mismo que sus filas de ajustes, a su izquierda (en escritorio, ~280 px de ancho). En móvil se muestra como una franja baja sobre las filas, no se oculta.
- **Sin texto narrativo:** solo título, control y valor; nada de «Así queda en vivo» con frases.
- **Encabezado de sección:** una línea con un ícono de identidad de 24 px y el título.
- **Cada ajuste es una fila de 44–52 px:** título y «?», el control y el valor alineado a la derecha.
  - El deslizador mide 200 px y lleva el valor recomendado como marca sobre la pista.
  - El selector segmentado va en línea.
- 2 columnas de filas en escritorio. El orden de los modelos va en filas de 44 px. Los chips de «Compartir con» van en la misma fila del título.
- **Meta:** lo más cerca posible de 1366×850 sin scroll, sin sacrificar los paneles azules.

## 7. Informe de gestión (vista y PDF)

- **Cabecera (~120 px):**
  - La ilustración de estado del veredicto a 96 px: sugerencia lista, modo alternativo o no se pudo, según cuántas metas se cumplen.
  - A su lado, la frase titular («0 de 3 metas cumplidas: acierto, sugerencia y respuesta bajo la meta»), el período y las descargas.
- **Banda de KPI**, como en Resumen, con 6 indicadores.
- **Pestañas** Calidad · Rapidez · Costos · Rentabilidad · Incidentes · Datos. Cada pestaña tiene **una** visualización protagonista con el lenguaje orbital (las mismas de Resumen y Negocio) y como máximo 3 datos de apoyo en una banda. Las tablas van solo en «Datos», plegadas.
- **PDF:** la cabecera y los KPI en la página 1, una página por pestaña con su visual protagonista y el anexo de tablas al final.
- **Meta:** el cuerpo sin «Datos» ocupa ≤ 1 pantalla por pestaña.

## 8. Revisión antes de entregar

Por cada vista, en las capturas de 390 y 1366 px:

1. ¿Se reconoce la identidad Núcleo a primera vista, comparada con la lámina?
2. ¿Hay algún bloque con más de 16 px vacíos, o alguna tarjeta que no hace falta?
3. ¿Hay texto de contexto, «sin datos» en grande o referencias al informe académico?
4. ¿Cada cifra tiene unidad, color de estado y su ícono?
5. ¿La visual protagonista reemplaza de verdad a los bloques que dice reemplazar?
6. ¿Se cumple la altura meta de la vista?
7. ¿Hay scroll horizontal en móvil?
8. ¿El rendimiento se mantiene (TTFB ≈ 0,05 s, ~450 KB, CPU en reposo baja)?
