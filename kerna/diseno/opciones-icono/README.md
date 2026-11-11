# Opciones de ícono para el indicador de Kerna

Las cuatro opciones son SVG propios, monocromos (`currentColor`), de caja `0 0 24 24`, en `svg/`. No se recomienda
ninguna: la elige la usuaria. Los códigos (`S`, `A`, `P`) remiten a `../investigacion-asistente-ia.md`. En todas las
opciones la transparencia la da el **texto** del indicador y del panel ("Sugerencia asistida", modo de generación), no el
dibujo (P1, P2).

Capturas: `<opcion>--<estado>.png` (12 estados, más dos variantes de contingencia), `iconos-tamanos.png` (24, 20 y 16
px). Maqueta: `maqueta/maqueta.html`. Regenerar: `./generar_capturas.sh`.

## a) `robot.svg`: robot

- **Ventajas**: se reconoce al instante como "asistente automático"; no hay duda de que es una máquina, lo que
  cumple con claridad la idea de no hacer pasar una sugerencia automática por trabajo humano (S10); no se confunde con
  otros íconos del cliente.
- **Riesgos**: es la marca de IA más evidente: la investigación asocia mencionar IA con menor confianza emocional,
  sobre todo en usos de riesgo alto (A12, solo comunicado de prensa) y el rechazo a lo demasiado evidente es el
  motivo de la usuaria; un personaje tiende a antropomorfizar el sistema y a inflar la inteligencia percibida (S7,
  S17); resalta más que la tarea (revisar normativa); a 16 px las facciones se funden (ver `iconos-tamanos.png`).

## b) `v-veridy.svg`: la "V" de Veridy

- **Ventajas**: integra el indicador en la identidad del producto, sin hablar de "IA"; es sobria, legible a 16 px y
  siempre coherente con el logo de la instalación; cumple la advertencia de Carbon de no usar la marca de IA como adorno
  (S13).
- **Riesgos**: no comunica por sí sola que se trata de una función automática; si el texto del indicador no lo dice
  ("Sugerencia asistida"), la transparencia se pierde (S17, S10) y podría leerse como parte del producto "que decide"
  (riesgo de "AI-washing" inverso: ocultar la IA); Veridy no tiene hoy un logotipo propio en el cliente (el
  logo que se usa es el de la instalación), así que esta "V" es un monograma provisional; puede confundirse con un
  signo de verificación o con una flecha hacia abajo.

## c) `articulo-marcado.svg`: artículo con marcador de cita

- **Ventajas**: remite a la tarea y no a "la IA" (el artículo de ley y su cita), en línea con el consejo de describir
  funciones y beneficios y evitar las palabras de moda de IA (A12); refuerza el mensaje de fundamentación y citas
  verificables (S7, P5); neutro y no antropomórfico (S7).
- **Riesgos**: puede confundirse con un ícono de documento o de "archivo" del cliente; no señala que es automático;
  a 16 px el marcador y las líneas son pequeños; también debe acompañarse de texto para marcar la asistencia.

## d) `balanza.svg`: balanza

- **Ventajas**: asociada de inmediato al derecho y a la normativa; tarea y no tecnología; legible a 16 px y con
  silueta distinta a los demás íconos del cliente.
- **Riesgos**: es un símbolo de justicia que podría sugerir que Kerna "juzga" o dictamina, justo lo que se quiere
  evitar ("no es un dictamen jurídico", P1; la sobredependencia aumenta en tareas de alto riesgo, A9); es un tópico
  muy usado; no indica que es automático.

## Cómo se evaluó (limitaciones)

No encontré estudios que comparen un robot con símbolos de la tarea en herramientas jurídicas; las comparaciones de
arriba son inferencias a partir de la investigación y deben probarse con auditores (P14). El destello (✨) se descartó
(S9, S13, S16). Cambiar de opción en el cliente es reemplazar el `<svg>` del componente `src-kerna-icono` (ver la
propuesta, sección 1).
