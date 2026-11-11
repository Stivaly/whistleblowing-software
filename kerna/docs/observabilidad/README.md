# Observabilidad de Kerna AI

El núcleo (y el servicio local) emiten telemetría con `kerna_comun.telemetria` hacia Application Insights
`appi-kerna-dev` (workspace `log-kerna-dev`) mediante OpenTelemetry (`telemetria_azure.py`). Terraform:
`infra/terraform/observabilidad.tf` (Workbook y alertas) y `nucleo.tf` (Application Insights).

## Señales reales

Todas las propiedades llegan como texto en `Properties` (dinámica); las consultas convierten con `todouble`/`toint`.

| Señal | Dónde | Propiedades |
|---|---|---|
| Eventos y etapas del núcleo | `AppTraces`, `AppRoleName == "kerna.kerna-nucleo"`, `Message` = nombre | `clase` (`evento`/`etapa`), `id_solicitud`, `etapa`, `modo`, `proveedor`, `modelo`, `recuperacion`, `embedding`, `coleccion`, `tokens_entrada`, `tokens_salida`, `duracion_ms`, `json_valido`, `articulos`, `citas_rechazadas`, `estado`, `motivo`, `contingencia`, `codigo`, `intento` |
| Mensajes | `solicitud_aceptada`, `anonimizacion`, `clasificacion`, `recuperacion`, `generacion`, `validacion`, `solicitud_terminada`, `nivel_fallido`, `cortocircuito_abierto`/`cerrado`, `recuperacion_nube_fallida`, `recuperacion_local_fallida`, `feedback`, `clasificacion_auditor` | |
| Duración de etapas | `AppMetrics`, `kerna.etapa.duracion` (histograma, ms) | dimensiones `etapa`, `modo`, `proveedor`, `modelo`, `recuperacion`, `embedding`, `coleccion`, `json_valido` |
| Jobs del pipeline | `ContainerAppSystemLogs_CL` (`JobName_s`, `ExecutionName_s`, `Reason_s`, `Log_s`) | |

`solicitud_terminada` resume cada solicitud (modo, recuperación, estado, motivo, tokens, citas rechazadas, duración).
La que cierra por plazo (`tiempo_agotado`) solo trae `estado` y `motivo`; las consultas asumen `modo = manual`.

## Consultas (`consultas/*.kql`)

| Archivo | Muestra |
|---|---|
| `latencia_por_etapa` | P50, P95 y máximo por etapa de la cadena |
| `latencia_solicitud_p95` | P50 y P95 de la solicitud completa por hora |
| `solicitudes_por_modo` | Solicitudes por modo y recuperación, con tasa de conmutación |
| `tasa_conmutacion` | Tasa de conmutación diaria (modo no oficial o recuperación local) |
| `disponibilidad_efectiva` | Con sugerencia / válidas por día (válidas excluye `sin_normativa_aplicable`) |
| `citas_y_json` | JSON válido de la generación y citas rechazadas por la validación |
| `tokens_por_solicitud` | Tokens de entrada y salida por solicitud, por modo |
| `errores_por_proveedor` | Niveles fallidos, recuperación fallida y cortocircuitos, por proveedor, modelo y código |
| `jobs_pipeline` | Una fila por ejecución de job: completada, fallida o en curso |
| `alerta_*` | Las cuatro condiciones de alerta (devuelven filas solo si se cumplen) |

Cada archivo filtra con `ago(7d)`. El Workbook lo reemplaza por el parámetro `{Dias}` (1, 7 o 30 días).

## Workbook y alertas

- Workbook "Kerna AI: resultados": una tabla por consulta de arriba (menos las alertas), sobre el workspace.
- Las alertas existen solo si la variable `correo_alertas` tiene valor; ese valor va en `terraform.tfvars` (fuera de
  git). Sin él no se crean el grupo de acción ni las alertas.

| Alerta | Condición | Evaluación (frecuencia / ventana) | Silencio |
|---|---|---|---|
| Job fallido | Código de salida distinto de 0, `BackoffLimitExceeded` o `DeadlineExceeded` | 15 min / 30 min | 2 h |
| P95 de la solicitud | P95 de `duracion_ms` sobre 15 s, con al menos 3 solicitudes | 30 min / 1 h | 6 h |
| Tasa de conmutación | Más del 10 % de solicitudes fuera del camino oficial, con al menos 5 | 1 h / 6 h | 6 h |
| Cadena agotada | Alguna solicitud en `revision_manual` con motivo `cadena_agotada` | 15 min / 30 min | 2 h |

## Regla de privacidad

Ningún texto de denuncia, nota, consulta, prompt ni respuesta va a la telemetría. Solo identificadores opacos,
conteos, duraciones, códigos y nombres de modelo. `telemetria.filtrar` descarta todo atributo fuera de
`ATRIBUTOS_PERMITIDOS` y los textos de más de 64 caracteres; las métricas solo usan las dimensiones de baja
cardinalidad de `telemetria_azure.DIMENSIONES` (nunca `id_solicitud`, `ref_opaca` ni valores continuos). Las
instrumentaciones automáticas de HTTP están desactivadas, porque registrarían las URL de Veridy con el identificador
real del caso. La prueba `pruebas/unitarias/test_telemetria_privacidad.py` lo verifica sin red.
