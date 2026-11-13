# Resumen de la sesión 2026-11-11/12 (para retomar)

## Desplegado y funcionando
- **Veridy** (ACI, imagen `be4d2b92b`): bloque de Kerna con identidad Núcleo clara y logo guilloché animado; tooltip y error "Unexpected error" de Usuarios corregidos; lista de denuncias con scroll propio; 113 denuncias cargadas solo con `texto_original` (sin rótulos).
- **Núcleo Kerna** (`c512174ae`): gpt-5-nano (Azure OpenAI) primero, Gemini respaldo; evaluador LLM encendido (N=70); telemetría con modelo y `articulo_sugerido`.
- **Conector** (`c512174ae`): reintento automático (3 veces, cada 24 h), tope de 5 envíos por pasada, comparte con «Auditor Kerna», eventos a Log Analytics.
- **Front Kerna AI** (https://app-kerna-dev-front-g6mzy.azurewebsites.net, App Service F1, clave del panel en Key Vault `kv-kerna-dev-g6mzy` secreto `front-clave-panel`): portada, panel en vivo, informe de gestión (PDF/XLSX/CSV) con costo real a precios de Anthropic (nano=Haiku 5.5, mini=Sonnet 5.5), sección Negocio desde tablas `clientes` y `usodiario`.
- **Infra**: `infra/aplicar.sh veridy|kerna` (Claude lo ejecuta; lee secretos de Key Vault y la telemetría). Tablas `evaluaciones`, `clientes`, `usodiario` por azapi.

## Diseño
- Logo final: guilloché (`kerna/diseno/logo/`, lámina https://claude.ai/artifact/V4s4vpsHtVhzjD3riyuXZN).
- Maqueta consola v3 en `kerna/front/diseno-v2/maqueta.html` (capturas `capturas/v3-*`). Publicada solo la v2 en https://claude.ai/artifact/HYMiH3d26ku4sN18dBQYJb: **falta republicar la v3** (leerla entera antes) y que la usuaria la apruebe; luego llevarla al front real (Tailwind compilado y librerías locales).
- Pendientes de la maqueta: gráficos ECharts sin estilo propio, chip "Sin alertas" del KPI de costo sin criterio, hueco en tramas guilloché, contraste AA sin medir.

## Calidad (recall@5 por artículo, meta 0,80)
- Base 0,393; evaluador con nano 0,426 (en producción); con Gemini Flash-Lite 0,557 (sin cuota); reranker bge empeoró (0,344).
- Evaluador por IDs (variante 3: citas por ID de frase/hecho, puntaje 0–3, hechos extraídos) **en producción con nano**: 0,475 (prueba 0,429); con mini 0,492 a ~0,012 USD/denuncia (4,6× nano), sin ventaja clara. Techo con 70 candidatos 0,902. Gasto 1,45 USD. Decisión abierta: mini o seguir afinando.

## Pendientes de la usuaria
- Ingresos de Negocio en UF (ver `kerna-pendientes.md`).
- Arreglar el informe de gestión al estilo de la maqueta (solo recordatorio).
- «Probar Kerna» (enviar denuncia y ver capas en vivo): bloqueado; elegir entre crear el secreto `front-demo` en Key Vault (lo hace la usuaria) o reutilizar la credencial del conector.
- Página de Ajustes real (App Configuration) — diseñada en la maqueta, sin implementar.
- Anonimizador: faltan reglas (empresas, cargos, edades, salud, ubicaciones, direcciones) y excepciones a términos jurídicos; números de causa ¿se ocultan?
- ~98 denuncias en revisión manual se reintentan solas (de a 5).
- Cuenta `kerna-e2e` para pruebas e2e (la crea la usuaria).
- Cambiar `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` en `~/.claude/settings.json` (propuesto, sin aplicar).

## Maqueta v3 publicada
- La maqueta v3 de la consola (`kerna/front/diseno-v2/maqueta.html`) está publicada como Artifact: https://claude.ai/artifact/WwcmWbJdjYSPVKdksTy1Fx
- El enlace de la v2 (HYMiH3d26ku4sN18dBQYJb) no se pudo leer ni actualizar desde esta cuenta, por eso la v3 quedó en un enlace nuevo.

## Trabajo sin la usuaria (2026-11-12, tarde, vía Continuo)

**Escrito para:** la usuaria, al volver.

**Desplegado en producción** (https://app-kerna-dev-front-g6mzy.azurewebsites.net, último commit desplegado con `desplegar.sh --ref HEAD`; 107 pruebas del front pasan):
- **Rediseño Núcleo completo** según `kerna/front/diseno-v2/direccion-diseno.md`:
  - **Resumen:** diagrama orbital del período (núcleo con 303 denuncias, anillos por modo, leyenda al lado); frase titular; cola de reintentos en línea con diálogo modal; KPI en banda sin tarjetas; «El camino de una denuncia»; anillos de acierto por ley con sus íconos.
  - **Negocio:** frase titular; cascada del ingreso a la utilidad; KPI en banda; Veridy con anillo de capacidad; proyección compacta con chips y tabla plegada.
  - **Ajustes:** se conservan los paneles azules orbitales que reaccionan a los controles. Cada ajuste en una fila, con títulos cortos.
  - **Informe de gestión:** veredicto con baldosa de la identidad, 6 KPI y pestañas con una visual cada una; tablas solo en «Datos».
  - **PDF:** las mismas visuales en vector; página 1 con cabecera, veredicto, KPI, diagrama y camino; anexo de tablas.
- **Identidad:** sprite con las 14 escenas de estado, íconos de ley y más de 30 íconos propios en el mismo lenguaje orbital (candado, oculto, cita, escudo, llave…). Ningún glifo genérico en estados.
- **Portada:** íconos de los 4 pasos y de las leyes recuperados (la causa era un sprite con XML inválido, ya con prueba). El círculo lima suelto era un satélite pintado en la imagen de fondo: eliminado.
- **Porcentajes unificados:** acierto 49,2 % con meta 80 % en la vista, el Excel, el CSV y el PDF.
- **Móvil:** sin scroll horizontal en ninguna vista ni pestaña.
- **Reintentar:** funciona en producción, con diálogo modal; el pedido queda registrado en la tabla `reintentosmanuales`.

**Alturas** (1366 / 390 px):

| Vista | Antes | Ahora |
|---|---|---|
| Resumen | 1.775 / 2.708 | 850 / 1.185 |
| Negocio | 1.477 / 2.485 | 948 / 1.240 |
| Ajustes | 1.213 / 1.894 | 850 / 1.370 |

**Rendimiento:** TTFB de 11 a 94 ms, HTML de 8 a 10 KB, CPU en reposo entre 0 y 0,4 %.

**Qué revisé yo** (capturas prod7, prod8 y prod9 en `kerna/front/diseno-v2/capturas/`):
- En prod7 encontré y devolví:
  - la meta «0,8 %»;
  - el veredicto duplicado;
  - puntitos sueltos de íconos;
  - el diagrama con etiquetas superpuestas;
  - la mancha en los paneles de Ajustes y el hueco en «Compartir»;
  - texto redundante en Negocio.
- En prod9 corregí yo dos detalles de móvil: «+52 % sobre el plan» repetido y «Depreciación» partido a mitad de palabra, que ahora dice «Crédito y equipos».

**Cerrado al final** (commit desplegado d8e33044b; 110 pruebas pasan; capturas prod10-):
- «Datos» agrupa las tablas por sección y en móvil pasó de 1.339 a 992 px.
- El PDF quedó en 8 páginas: Rapidez e Incidentes ahora comparten página.
- El anillo «Global» de Calidad quedó alineado con los demás.

**Falta (menor):** revisar en un celular real el degradado de «Compartir» en Ajustes.

**Sigue pendiente de ti:**
- Valor de la UF (hoy se usan 40.000).
- Subir al plan B1 (unos US$ 13 al mes) para evitar la espera de la primera visita.
- Autorizar el despliegue del conector, para que el reintento manual se ejecute de verdad.
- Crear la cuenta `kerna-e2e`.

### Íconos y Compartir (2026-11-13, agente de íconos)
- Último commit desplegado bueno antes de este despliegue: d8e33044b (front; `/salud` 200).
- Prueba nueva `kerna/operaciones/probar_iconos.sh` (portada y panel, 390/1366/1920 px). Sobre producción previa: ningún `<use>` roto ni imagen sin cargar; los botones Otro período, Excel y CSV ya se ven (los arregló la corrección del sprite XML). Sin falsos positivos: pulso animado de la portada, íconos en plegables cerrados y chips fuera del viewport.
- Compartir: los satélites del panel azul muestran Analistas, Comité, Auditoría, Fiscalía (antes AN, CE, AU, FL).

### Ajustes con movimiento, botón de reintento y «En vivo» (2026-11-13, agente de Ajustes)
- Último commit desplegado bueno antes de este despliegue: 82e9839c7 (front; `/salud` 200). Si algo falla: `kerna/front/desplegar.sh --ref 82e9839c7`.
- Desplegado: ff6732151 (7cb3fc2af, 1d8665ba0, 70531926b y los arreglos siguientes). 118 pruebas del front pasan; `probar_movimiento.sh` pasa (órbitas giran, satélites y arco con transición, teclado, CPU en reposo 0,07 % en Ajustes y 0,01 % en Resumen, sin animaciones con prefers-reduced-motion). Capturas `kerna/front/diseno-v2/capturas/prod12-*.png` (390, 1366, 1920).
- Contraste AA verificado (chips «Se aplica ya» 4,75; botón gris 5,92; barras de guardado 5,37 y 6,57) y `calcular_contraste_v3.py` sin fallas.

### Resumen y Ajustes v13 (2026-11-13, agente de Resumen)
- Último commit desplegado bueno antes de este despliegue: ff6732151 (front). Si algo falla: `kerna/front/desplegar.sh --ref ff6732151`.
- Desplegado: commits 12b665cd4 y siguientes (Resumen con bandas tintadas y arcos orbitales WebP en las esquinas, ancho máximo 1.440 centrado en todas las vistas, proveedores con nombre y estado, «Sin ley registrada 323» convertido en nota «323 artículos sugeridos sin ley identificada en el registro»; Ajustes: equipos de Compartir en HTML a 11,5 px, paneles Compartir y Plazos sin huecos, última fila de Procesamiento a ancho completo). 122 pruebas del front, `probar_iconos.sh` (0 fallos), `probar_movimiento.sh` (CPU 0,01 %) y `probar_front.sh` pasan. Capturas `kerna/front/diseno-v2/capturas/prod13-*.png` (390, 1366, 1920) y `prod13.json`.
- Supuesto, a confirmar: el «(sin nombre) 323» son artículos sugeridos cuyo registro de telemetría no trae la ley; se muestra como nota, no como chip.
- Contraste AA: tintes de banda verificados con `test_front_resumen_v13.py` (texto de estado verde oscurecido a #17622E dentro de las bandas).

### Negocio, Informe y «?» (2026-11-13, agente de Negocio e Informe)
- Último commit desplegado bueno antes de este despliegue: eddb6d7aa (front). Si algo falla: `kerna/front/desplegar.sh --ref eddb6d7aa`.
- Desplegado: ba2980600 y siguientes (último: ver `git log`; 130 pruebas del front pasan). `probar_iconos.sh` 0 fallos en 1.210 elementos; `probar_movimiento.sh` sin fallas (CPU en reposo 0,01 a 0,07 %); `probar_front.sh` todo bien; `calcular_contraste_v3.py` sin fallas; graficos de anillo (verde, amarillo, azul, coral) sobre las bandas ≥ 3:1.
- Negocio: bandas tintadas del Resumen (clase `.zv`, mismas imágenes de arcos), cascada y frase en dos columnas (cascada máx. 860 px), clientes con anillo «con y sin uso» (`orbital.dona`), proyección en 3 columnas (barras, 4 cifras grandes, anillo del reparto del ingreso del último año). Informe: bandas por pestaña, veredicto con tinte según estado (verde, ámbar o coral), baldosas con anillo en lugar de tarjetas de borde de color, gráfico acotado a 960 px.
- Renombres de indicadores: Acierto → Sugerencias acertadas; Respuesta → Tiempo de respuesta; Costo → Costo del período; Sugerencias útiles → Sugerencias útiles según auditores (en el informe, «Sugerencias útiles»); Con sugerencia → Denuncias con sugerencia; Valoradas → Sugerencias calificadas; Margen operativo → Ganancia sobre el ingreso; Costo de servir → Costo de atender clientes; Ingreso → Ingreso del período; Utilidad → Utilidad del período; Denuncias → Denuncias recibidas; Valor actual neto → Ganancia a 5 años, en valor de hoy; Retorno anual → Rentabilidad anual del proyecto; Índice de rentabilidad → Retorno por cada UF invertida; Se recupera en el año → Año en que se recupera la inversión; en la cascada «Costo de servir» → «Atender clientes». Rótulos del informe: Caso típico → Tiempo típico de un caso; Utilidad final → Ganancia final del período.
- «?»: todos de una línea (≤ 80 caracteres, sin «cómo leerlo»), tooltip `#tt` muestra solo `g.q` (en «En vivo» y en la nota de cada cliente, el texto propio). Prueba `test_los_tooltips_son_de_una_linea`.
- Resumen móvil: el «?» de «En espera · próximo reintento…» queda junto al texto (`.cola>.mk{display:block}`).
- Supuesto, a confirmar: el anillo de la proyección reparte el ingreso del último año entre utilidad y «costos e impuestos» (todo lo demás); el anillo de clientes separa clientes con y sin uso registrado.

## Pulido de la banda de KPI (2026-11-13, tanda 15)
Último commit desplegado bueno antes de esta tanda: 9eea6cad1.
Segundo despliegue de la tanda: previo bueno f61fe44d8 (desplegado y sano).
Tanda 15 (desplegado: 301ef5df9; previo f61fe44d8). Capturas `kerna/front/diseno-v2/capturas/prod15-*.png` y `prod15.json`.
- KPI: el Informe usa 3×2 hasta 1799 px y 6 en fila desde 1800; la etiqueta es texto en línea y el «?» queda pegado a su última palabra (macro `kb`).
- Decoración: arcos y satélites solo en el margen derecho de cada banda (arriba y abajo a la derecha, 56 px; 26 px en móvil); nada a la izquierda ni sobre texto.
- Clientes (Negocio): anillo de 104 px y columnas centradas, sin huecos > 16 px. Proyección: cifras sin salto de línea.
- Movimiento: escalonado por banda (`bnIn`, 70 ms por banda, solo opacity/transform, solo con `prefers-reduced-motion: no-preference`) en Resumen, Negocio e Informe.
- Ajustes: caché con vida de 24 h y refresco en segundo plano, precalentada al arrancar; al guardar se reemplaza el valor (`cache.poner`), un refresco viejo en curso no lo pisa.
- TTFB a 1366 en caliente: Resumen 14-15, Informe 15-16, Negocio 13-15, Ajustes 18 ms; justo tras reiniciar: 51 / 42 / 37 / 35 ms. Una muestra de Resumen dio 290 ms (no se repitió en 3 corridas más). CPU en reposo: Ajustes 0,06 %, Resumen 0,01 %.
- Pruebas: probar_iconos 0 fallos (1203 elementos), probar_movimiento sin fallas, probar_front bien; pytest del front 138 pasan. Contraste del texto «muted» sobre todas las tintas de banda ≥ 4,86:1.

## Tanda 16 (2026-11-13)
Último commit desplegado bueno antes de esta tanda: 301ef5df9. Si algo falla: `kerna/front/desplegar.sh --ref 301ef5df9`.
Tanda 16 (desplegado: 88b7c98b7; previo bueno 301ef5df9). Capturas `prod16-*.png` y `prod16-portada-*.png` (m/d/d1920), `prod16.json`.
- Negocio: fila de Veridy en dos líneas (nombre+plan+último uso arriba, cifras abajo), proyección con etiquetas de máx. 2 líneas («Ganancia a 5 años, valor de hoy», «Recuperas la inversión en»), KPI con más interlínea.
- Resumen: «Acierto por ley» reparte el ancho (leyes flex 3, nota flex 1).
- `rasterizar_decoracion.py` ya no genera `bg-orbitas.webp` (retocado a mano).
- Portada 390/1366/1920: sin scroll horizontal, sin huecos > 16 px entre bloques (`kerna/operaciones/medir_portada.py`, vía `playwright.sh script`); menos aire bajo el héroe en escritorio. probar_iconos 0 fallos/1203; probar_movimiento y probar_front bien; pytest 138.

## Orquestador 2026-11-13

**Desplegado en producción:** front `88b7c98b7` (antes: 82e9839c7 → ff6732151 → eddb6d7aa → 9eea6cad1 → 301ef5df9; nunca hubo que volver atrás). Conector con tag `987d2fe98`, aplicado con `infra/aplicar.sh veridy -y` (plan: 2 a crear, 1 a destruir = reemplazo del grupo de contenedores ACI y un rol nuevo; no tocó PostgreSQL, almacenamiento ni Key Vault). 138 pruebas del front y 66 del conector pasan.

**Qué quedó**
- **Conector:** atiende «Reintentar» de verdad: toma la lista real de casos sin sugerencia o en revisión manual, publica el avance y el resultado (contrato en `pendientes/contrato-reintento-conector.md`). Verificado: 99 reintentados, 74 con sugerencia; revisión manual de 93 a 18; eventos de reproceso de 6 a 81 (en `kerna/evaluacion/registro-pruebas.md`). Lo real eran 99 casos, no 271: la cifra antigua contaba 62 casos que ya no existen en Veridy. Lee de `ajustes` casos por ronda, reintentos automáticos, espera, frecuencia de revisión y reintentar revisión manual, y escribe una fila de estado inmediato para «En vivo».
- **Ajustes:** paneles azules con movimiento (órbitas, satélites con transición, arco animado), estado de guardado sin recarga, «Se aplica ya» / «Aún no se aplica», vista previa del efecto, teclado y foco, «Compartir» con nombres completos.
- **Resumen:** bandas tintadas con corte de esquina y arcos orbitales, contenido de 1.440 px como máximo, colores de la identidad, proveedores con nombre y estado, botón de reintento siempre visible (gris y girando mientras está en curso, con el resultado al terminar).
- **Negocio:** las mismas bandas, cascada al lado de la frase, anillo de clientes con y sin uso, proyección en 3 columnas, indicadores renombrados.
- **Informe:** colores vivos, banda de indicadores en 3×2 hasta 1.800 px, baldosas de la identidad en lugar de las tarjetas con borde de color. El PDF no cambia salvo los nombres.
- **Todo el front:** «?» de una sola línea, entrada escalonada por banda, prueba de íconos con navegador real (`kerna/operaciones/probar_iconos.sh`, 0 fallos en 1.203 elementos) y prueba de movimiento (`probar_movimiento.sh`). TTFB en caliente de 12 a 18 ms, CPU en reposo ≤ 0,07 %.
- **Dataset:** 150 relatos sintéticos en `kerna/evaluacion/datos/denuncias_sinteticas_20261113.json`. Solo se generaron.

**Capturas que audité** (en `kerna/front/diseno-v2/capturas/`): prod12-ajustes-d1920, prod12-resumen-d1920, prod13-resumen-{d1920,m}, prod12/prod14-negocio-d1920, prod14-informe-d, prod14-ajustes-m, prod15-{informe,negocio}-d, prod16-negocio-d, prod16-portada-d1920. Devolví: etiquetas de 8 px y huecos en Ajustes; Resumen sin zonas, estirado y opaco; banda de indicadores del Informe apretada; adornos encima del texto; fila de Clientes apretada a 1366.

**Supuestos, a confirmar:** «323 artículos sugeridos sin ley identificada» se muestra como nota; los anillos de Negocio (con o sin uso; utilidad frente a costos del último año); Plazos y Compartir marcados «Aún no se aplica»; los renombres de indicadores (lista en `pendientes/kerna-pendientes.md`).

**Falta:** el estado «en curso» del botón solo se vio con una respuesta simulada; los ajustes de IA los tiene que aplicar el núcleo (anotado para el otro agente); el mapa de calor del Resumen necesita 7 días de datos; el conector todavía cuenta 62 casos que ya no existen en Veridy; `conector_tag` y `kerna_tablas_cuenta` están solo en el `terraform.tfvars` local, que git ignora. `bg-orbitas.webp`, regenerado sin querer, está en la papelera y la versión buena quedó restaurada.

**Necesita a la usuaria:** valor de la UF, plan B1, cuenta `kerna-e2e`, decidir si se cargan o evalúan los 150 relatos y revisar los renombres.

## 2026-11-13 03:40 · pendientes reales en el Resumen
Último desplegado bueno antes de este cambio: 88b7c98b7 (volver con `kerna/front/desplegar.sh --ref 88b7c98b7`).

### Orquestador 2026-11-13 (segunda tanda, 03:00-03:50)
- Conector `c6a17f85b` desplegado (plan: solo reemplazo del ACI de Veridy). Reconcilia con Veridy: 62 casos que ya no existen quedan archivados (marcados, no borrados); `completado` ya no supera a `casos`.
- Botón de reintento verificado con un pedido real: gris, deshabilitado y girando mientras corre; al terminar, «6 reintentados · 2 con sugerencia». Capturas en `kerna/front/diseno-v2/capturas/prod17-reintento-{curso,fin}-{m,d}.png`.
- Front `4780c54cd` desplegado. Lo pendiente del Resumen sale del estado real del conector: 4 casos esperan reintento (antes mostraba 206, sacado de la telemetría acumulada). Si el estado tiene más de 5 minutos, vuelve a la telemetría con el rótulo «Estimado». Capturas `prod18*` (auditada `prod18resumen-d.png`).
- Falta (menor, resuelto en la línea siguiente): que el conector entregue el motivo de cada caso pendiente. Supuesto a confirmar: el estado del conector cuenta como reciente si tiene menos de 5 minutos.
- Conector `0e75d50c8` y front `e1e38e947`+ (HEAD de la tanda) desplegados: la fila `conector` trae `pendientes_por_motivo` y el Resumen vuelve al desglose por motivo con sus íconos (2 no pasó la revisión de calidad · 1 modelos no disponibles · 1 error; suma 4). Planes: solo reemplazo del ACI de Veridy. Primer intento `e1e38e947` tenía un `LIKE '…%'` que PostgreSQL leía como marcador (ProgrammingError en cada pasada); corregido en `0e75d50c8`. Capturas `prod19*` (auditada `prod19resumen-d.png`, `-m.png`); iconos, movimiento y front pasan. Último bueno anterior: `4780c54cd`.

### Front tanda 2026-11-13 (A1-A5)
- Último front bueno antes de esta tanda: `e1e38e947` (volver con `kerna/front/desplegar.sh --ref e1e38e947`).
