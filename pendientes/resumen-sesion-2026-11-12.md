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
