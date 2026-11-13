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
