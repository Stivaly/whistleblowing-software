# Encargo del orquestador (Opus), 2026-11-13 00:00

Eres el orquestador. No editas código tú mismo: encargas el trabajo a agentes Sonnet 5.5 de esfuerzo medio (Agent con `model: sonnet`, `effort: medium`) y **siempre en primer plano** (`run_in_background: false`), porque en modo sin chat los agentes en segundo plano mueren al terminar la tanda. Auditas personalmente cada entrega mirando las capturas de producción y no aceptas nada que no cumpla. Iteras sin límite de tiempo hasta alcanzar el estándar más alto de UX/UI.

Lee primero:
- `.claude/CLAUDE.md`
- `kerna/front/diseno-v2/direccion-diseno.md`
- la lámina `kerna/diseno/identidad-v3/lamina-comparativa.png`
- la sección «Rediseño Núcleo» de `pendientes/kerna-pendientes.md`
- `pendientes/resumen-sesion-2026-11-12.md`
- tu memoria (MEMORY.md), sobre todo: optimizar no es quitar, UX en lenguaje simple, desplegar solo con script, relevo a 300k.

## Reglas para cada agente (inclúyelas en cada encargo)

- **Relevo:** máximo 300.000 tokens. Hacia los ~250.000 cierra lo que tenga a medias, corre las pruebas, commitea, anota en pendientes lo que falta (en orden, con archivo y línea) y entrega. Después lanzas un agente nuevo; nunca retomas uno viejo.
- **Despliegue:** solo con `kerna/front/desplegar.sh --ref HEAD`, y solo con las pruebas del front pasando.
- **Capturas:** reales de producción a 390 y 1366 px, y también a 1920 px (la usuaria tiene pantalla muy ancha), con `kerna/front/herramientas/medir_vistas.sh` (Chromium del contenedor Playwright).
- **Archivos:** nunca eliminar; mover a `.papelera/` y anotarlo.
- **Rama:** solo `feature/kerna-pipeline-azure`.
- **Fuera de alcance:** no tocar Terraform. El conector se toca solo según el punto 7.
- **Rendimiento:** mantener el actual (TTFB < 100 ms, CPU en reposo < 1 %). La usuaria quiere que todo el panel se sienta tan fluido como el Resumen actual, **pero con movimiento**: animar solo `transform` y `opacity`, con capas rasterizadas para la decoración y SVG vivo solo en lo que reacciona; nada de `steps()` que se note a saltos.

## Lo que pidió la usuaria (2026-11-12, 22:30), por vista

### 1. Ajustes (prioridad alta; el rediseño fue insuficiente)
- **Los paneles azules no tienen ningún movimiento.** Deben moverse otra vez, fluidos y suaves: órbitas que giran lento, satélites que se desplazan al mover un control con una transición, el arco de «Meta de respuesta» que se anima. Todo optimizado como el Resumen.
- **Rediseño de fondo, no solo compactar.** Audita Ajustes con el estándar más alto de UX/UI (jerarquía, agrupación, previsualización del efecto de cada ajuste, estados, accesibilidad, teclado, foco). Itera hasta que sea excelente.
- El panel de «Compartir» muestra siglas cortadas («AN», «CE», «AU», «FL») y los íconos «?» desaparecieron en algunas filas; revisa ambas cosas.

### 2. Resumen (el diseño gusta mucho: NO cambiarlo más allá de esto)
- **Distribución:** «no tener ninguna tarjeta» se tomó demasiado a pecho; no hay fondo y las divisiones casi no se ven. Delimitar las zonas con las formas de la identidad (núcleo y circunferencias), de forma ordenada; por ejemplo, superficies suaves con corte de esquina o arcos orbitales que enmarquen cada banda.
- **Ancho máximo:** la pantalla de la usuaria es muy ancha y todo estirado se ve mal. Contenido de ~1.440 px, centrado o alineado con el menú.
- **Color:** más viveza con la paleta de la identidad (lima, verde, azul, amarillo, naranja, coral, cian, violeta). Ojo: no solo en el código de estados. Busca ideas: fondos tintados por banda, satélites a color, degradados suaves de la identidad, acentos lima en el núcleo. Hoy se ve opaco.
- **Proveedores (arriba a la derecha):** gustan el ícono y el lugar, pero no se entiende qué son. Que cada uno tenga su nombre y estado (por ejemplo «Azure · operativo») aprovechando el espacio libre de la barra.

### 3. Clientes y márgenes (Negocio)
- El gráfico de barras (proyección) ocupa todo el ancho y se ve enorme. Usa 2 o 3 columnas: una para las barras y las otras para otra información útil.
- «4 con contrato, sin uso registrado» puede ser un gráfico de torta o anillo (clientes con uso y sin uso, o por plan), en lugar de solo una línea.
- Los **nombres de los indicadores no dicen qué son**: renómbralos para que se entiendan solos.
- Las **explicaciones («?») son largas**: concretas y directas, de una línea.
- La proyección a 5 años también está demasiado ancha.

### 4. Informe de gestión
- Colores más vivos, como en el Resumen.
- Rediseña con la identidad las tarjetas de borde izquierdo de color «Acierto con el artículo exacto 49,2 %», «Acierto con la ley 96,7 %» y «Pruebas automáticas pasadas 333/333». Ese estilo no corresponde a la identidad.
- **Faltan logos o íconos en «Generar informe»**: revisa todos los `<use>` y las imágenes de esa vista y de los botones (Otro período, Excel, CSV aparecen sin ícono).
- El PDF le encantó y no le falta nada: no lo cambies salvo para colores.

### 5. Todo el front
- Aplica la misma fluidez y movimiento del Resumen en todas las vistas.
- Que los nombres de los indicadores se entiendan solos y que los «?» sean de una línea, en todo el front.
- Antes de entregar, revisa a 1366 y a 1920 px de ancho.

### 5b. Logos e íconos invisibles (revisión exhaustiva, prioridad alta)
- Hay logos e íconos que no se ven, aunque su espacio está reservado: se nota el hueco donde deberían estar. Pasa en el panel y **también en la portada de Kerna**.
- Encarga una revisión exhaustiva de todas las vistas, incluida la portada, a 390, 1366 y 1920 px. El agente debe:
  - revisar cada `<use href>` contra los ids reales de cada sprite;
  - revisar cada `<img>` o `background-image`: que cargue (no 404) y que no tenga `opacity` 0 ni tamaño 0;
  - revisar que el color de trazo o relleno no coincida con el fondo;
  - revisar que el `viewBox` sea correcto.
- Debe escribir una prueba con navegador real que, en cada vista, recorra todos los íconos y logos y falle si alguno ocupa espacio pero no pinta píxeles. Por ejemplo, compara la captura del elemento contra un fondo plano.
- Corrige todo lo que encuentre y audítalo en las capturas.

### 6. Botón de reintento: que se vea y que reintente de verdad (prioridad alta)
- **Hoy no se ve el botón.** Desde el pedido del 2026-11-12 21:00 el bloque muestra «Pedido en curso» y oculta el botón, porque nadie atiende el pedido.
- **El botón debe verse siempre.** Si hay un pedido en curso, se muestra su estado al lado y el botón se puede volver a usar.
- **Al pulsarlo, Kerna debe volver a generar la sugerencia** de todas las denuncias que aún no la tienen: las 271 en revisión manual y cualquier otra sin clasificar. Obtén la lista real desde el estado de cada caso en el conector o en Veridy, no la estimación de 7 días.

### 7. Conector y las 271 denuncias en revisión manual
- El reintento manual no se ejecuta porque el conector con soporte para `reintentosmanuales` **no está desplegado**. Para desplegarlo hay que recrear el grupo de contenedores de Veridy y dar un rol. Según `.claude/CLAUDE.md`, si el plan de Terraform reemplaza recursos hay que consultar a la usuaria.
- Prepara todo, revisa el plan con `echo n | infra/aplicar.sh veridy` y, si reemplaza el grupo, **no apliques**: deja el plan resumido en el resumen para que la usuaria lo autorice.
- Si algo se puede hacer sin reemplazar recursos, hazlo.

### 8. Dataset sintético (pista aparte)
Si las 271 no pueden reprocesarse, o hace falta más volumen, lanza un agente que genere denuncias sintéticas. **Ese agente no puede saber nada del contexto**: ni que son para un modelo, ni cómo se evaluarán, ni qué leyes, ni el país.

Diseña tú un encargo muy cuidadoso que solo le pida crear un conjunto de relatos de denuncias laborales y corporativas realistas, en español neutro con modismos locales variados. Que busque situaciones reales en foros públicos (por ejemplo, Reddit) y las adapte a relatos de denuncia específicos, en primera persona y anonimizados. Debe tener variedad de:
- temas (trato en el trabajo, acoso, discriminación, uso indebido de información personal, fraude, sobornos, conflictos de interés, seguridad, otros);
- extensión, tono y nivel de detalle;
- casos ambiguos y casos que no corresponden a ninguna falta;
- datos personales ficticios inventados (nombres, documentos, correos, teléfonos), para probar el anonimizador.

Pide un formato de salida JSON con campos neutros (`id`, `relato`, `fuente_inspiracion`, `extension`) y una cantidad concreta (por ejemplo, 150).

Tú, el orquestador, guardas el resultado en `kerna/evaluacion/datos/` (fuera de git, como el dataset actual) y registras la generación en `kerna/evaluacion/registro-pruebas.md`. No lo cargues en Veridy sin dejarlo anotado. Si el conector está desplegado, puedes enviar un lote pequeño de prueba y registrar el resultado.

## Auditoría (la haces tú, en cada entrega)

Mira tú mismo las capturas, imagen por imagen, a 390, 1366 y 1920 px. Revisa:
- la identidad (lámina);
- que haya movimiento fluido en lo aprobado;
- el color con viveza;
- las zonas delimitadas con formas orbitales;
- el ancho máximo;
- que los nombres se entiendan solos y los «?» sean de una línea;
- los íconos (ninguno vacío ni genérico);
- que no haya huecos de más de 16 px;
- que no haya scroll horizontal;
- el rendimiento.

Lo que no cumpla se lo encargas al agente siguiente. No te detengas mientras quede algo por mejorar que se pueda hacer sin la usuaria.

## Modo de trabajo: auditor e iterativo

- Sigue iterando (encargar, auditar, volver a encargar) hasta que **todo** lo que pidió la usuaria esté resuelto.
- Si algo depende de una decisión suya, no te detengas: avanza con un **supuesto razonable**, aplícalo y anótalo como «supuesto, a confirmar». Ejemplos: el valor de la UF, el texto que falta sobre el PDF, la paleta concreta para dar viveza.
- Deja para el final solo lo que de verdad requiere su autorización, como reemplazar recursos de Azure.

## Al terminar

Actualiza `pendientes/resumen-sesion-2026-11-12.md` con una sección «Orquestador 2026-11-13» que diga qué quedó, qué auditaste (con las rutas de las capturas), qué falta y qué necesita la autorización de la usuaria. Commitea.
