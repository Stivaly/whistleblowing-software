# Investigación: diseño de dashboards e informes de gestión

Se consultaron 4 fuentes genéricas (sin datos del proyecto). Lo que se aplica en `/panel/informe`:

| Principio | Fuente | Cómo se aplica |
|---|---|---|
| Una pantalla, lo esencial, sin desplazarse para entender el estado; formas de posición y longitud (barras, bullet, sparkline) en vez de medidores decorativos | Stephen Few, *Information Dashboard Design* ([reseña UXmatters](https://uxmatters.com/mt/archives/2007/04/book-review-information-dashboard-design.php), [resumen](https://blogs.ischool.berkeley.edu/i247s13/files/2013/02/WhyMostDashboardsFail.pdf)) | Fila de 6 KPI con color, ícono, tendencia y sparkline arriba, sin medidores de aguja |
| Pirámide invertida: lo más importante primero, detalle después; quien lee 5 segundos ya sabe el estado | [NN/g, inverted pyramid](https://www.nngroup.com/articles/inverted-pyramid/) | Veredicto de una línea + KPI primero; secciones después; tablas al final |
| Divulgación progresiva: mostrar poco y dejar abrir el detalle | [UX Collective](https://uxdesign.cc/inverted-pyramids-progressive-disclosure-in-design-5b63cb54c8cb) | Pestañas por sección; explicaciones solo en el «?»; tablas en la pestaña «Datos» |
| SUCCESS (IBCS): titular que dice la conclusión (SAY), estructura clara (STRUCTURE), notación uniforme (UNIFY), condensar (CONDENSE), simplificar (SIMPLIFY) | [IBCS, estándares](https://ibcs.com/standards/) | Títulos de gráfico con la conclusión, mismas unidades y colores en toda la página, un gráfico por idea, sin adornos |
| Distinguir tablero de presentación (estado actual) de exploración (filtros, detalle) | [Carbon Design System, Dashboards](https://carbondesignsystem.com/data-visualization/dashboards) | Informe = presentación; filtros de período y la pestaña «Datos» = exploración; títulos descriptivos y lenguaje simple |

Reglas derivadas: (1) cuerpo principal ≤ 2 pantallas; (2) nada de párrafos, cada explicación va al «?»; (3) color de estado siempre con ícono (no solo color); (4) tablas fuera del cuerpo (pestaña «Datos», XLSX/CSV); (5) pocos gráficos vivos a la vez y decoración como imagen rasterizada, no como cientos de nodos.
