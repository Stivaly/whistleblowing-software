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
- **En curso al cerrar**: agente que rediseña el evaluador (citas por ID de frase/hecho, puntaje 0–3, memoria de hechos) iterando con nano y midiendo con mini, tope 4 USD. Revisar su informe en `kerna/evaluacion/informe-embeddings.md` y `registro-pruebas.md`.

## Pendientes de la usuaria
- Ingresos de Negocio en UF (ver `kerna-pendientes.md`).
- Arreglar el informe de gestión al estilo de la maqueta (solo recordatorio).
- «Probar Kerna» (enviar denuncia y ver capas en vivo): bloqueado; elegir entre crear el secreto `front-demo` en Key Vault (lo hace la usuaria) o reutilizar la credencial del conector.
- Página de Ajustes real (App Configuration) — diseñada en la maqueta, sin implementar.
- Anonimizador: faltan reglas (empresas, cargos, edades, salud, ubicaciones, direcciones) y excepciones a términos jurídicos; números de causa ¿se ocultan?
- ~98 denuncias en revisión manual se reintentan solas (de a 5).
- Cuenta `kerna-e2e` para pruebas e2e (la crea la usuaria).
- Cambiar `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` en `~/.claude/settings.json` (propuesto, sin aplicar).
