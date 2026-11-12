# Revisión de diseño independiente (segunda opinión)

Método: Playwright 1.64.0 en Docker, 1440x900 y 400x860, todas las vistas, tooltip abierto, asistente de informe (3 pasos) y Ajustes con cambios pendientes y resumen. Capturas finales `capturas/rev-*` (`-d` escritorio, `-m` móvil). Versión previa de la maqueta en `.papelera/2026-11-12/`. Resultado: sin errores de consola ni desbordamiento horizontal en ninguna vista.

## Lo que ya funcionaba (se conserva)
Estado general con semáforo y frase de lectura; metas junto a cada cifra; "Qué hacer" por incidente; tooltips con "Cómo leerlo"; Negocio separado y rotulado como ejemplo; asistente de informe claro; resumen de cambios antes de guardar.

## Hallazgos por impacto (antes -> después)
| # | Hallazgo | Después |
|---|---|---|
| 1 | La pregunta central de la demo, "¿qué tan buenas son las sugerencias?", quedaba en la 3.ª fila. La tarjeta superior decía "89 % Con sugerencia, dentro de lo esperado" (verde) y el medidor más abajo "74 %, bajo la meta": dos cifras de "bueno" que se contradicen para quien no es técnico | La 2.ª tarjeta ahora es "Acierto de las sugerencias 74 %, bajo la meta, 6 puntos bajo" (ámbar). La cobertura (89 de cada 100 recibieron sugerencia) pasa a la tarjeta "¿Cómo se resolvieron?" |
| 2 | Estado general decía "hay 2 cosas por mejorar" sin llevar a la acción | Enlace "Ver qué hacer" que desplaza a "¿Qué falló y qué hacer?" |
| 3 | Jerga: "Núcleo", "Conector", "Búsqueda normativa", "Resp. penal" | "Motor de Kerna", "Enlace con Veridy", "Búsqueda de leyes", "Responsabilidad penal" |
| 4 | Gráfico de latencia con dos líneas sin leyenda; "menos de 41 s" partido con "s" huérfana | Leyenda (9 de cada 10 casos / Caso típico) y valor sin salto |
| 5 | Proyección con doble eje (US$ y %) y línea de margen casi plana: obliga a leer dos escalas por un dato que ya está en la frase de lectura | Solo ingresos y costo; el margen queda en la frase |
| 6 | Accesibilidad táctil: "?" de 22 px, segmentos de 38 px, botón "Ir a Ajustes" 38 px | Zona táctil de 44 px (el "?" conserva su tamaño visual), segmentos y botón de 44 px |
| 7 | Texto secundario y chips de 12 px | 12,5 px; en móvil el ícono y el título del estado general se reducen para no ocupar media pantalla |

## Pendiente para el front real
- Resumen es largo en móvil (unos 6.000 px). Plegar por secciones (horarios, costo comparado, leyes frecuentes) o dividir en pestañas "Calidad / Velocidad / Fallos / Costo".
- El tooltip móvil se abre sobre el texto que explica; usar hoja inferior (bottom sheet).
- Fechas del informe: el selector nativo sigue el idioma del navegador (mm/dd/aaaa); poner calendario propio dd/mm/aaaa y mostrar los campos solo con "fechas exactas".
- Negocio: "Valoradas como útiles 79 %" aparece en verde con solo 14 valoraciones; mostrar el tamaño de muestra en el chip o usar gris bajo un mínimo.
- Cliente C inactivo con "Margen alto" en verde: el semáforo de margen debería degradarse si no hay uso.
- Las tarjetas de salud y KPI repiten información (estado + chip + frase + meta): en producción dejar chip + una frase.
- Estados de error y carga de los gráficos (esqueleto, "no se pudo cargar", reintentar) no están diseñados; solo hay estados vacíos.
- Compilar Tailwind y alojar librerías localmente; verificar contraste de las barras ámbar (rozan 3:1) siempre con texto al lado.
- Efecto demo: los datos son de ejemplo y están rotulados, lo que da credibilidad; evitar en la demo cifras ficticias de Clientes B y C sin ese rótulo visible.
