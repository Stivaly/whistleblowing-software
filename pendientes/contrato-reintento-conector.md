# Contrato conector ↔ front: reintento manual, ajustes y estado en vivo

Tabla `reintentosmanuales` (la misma que usa el front), PartitionKey `kerna`. El conector la lee y escribe con la identidad del grupo de Veridy (rol Storage Table Data Contributor). Las filas solo tienen conteos y fechas: nunca textos ni identificadores de casos. Requiere el conector desplegado con `KERNA_TABLAS_URL`; sin él, la fila `solicitud` queda en «solicitado» y nada se atiende.

## Fila `solicitud` (RowKey `solicitud`)

El front la escribe como siempre (`estado=solicitado`, `solicitado_en`). El conector también puede escribirla (`origen=ajustes`) cuando se guarda el ajuste «Reintentar los de revisión manual».

| Campo | Cuándo | Significado |
|---|---|---|
| `estado` | siempre | `solicitado` (nadie la tomó aún) → `en_curso` → `atendido`. Ausente/`ninguna` = no hay pedido. |
| `solicitado_en` | desde el pedido | ISO UTC. |
| `origen` | `en_curso`, o `solicitado` si lo creó el conector | `panel` o `ajustes`. |
| `corrida` | `en_curso` | id interno de la corrida (`m<epoch>`). |
| `inicio` | `en_curso` y `atendido` | ISO UTC en que el conector la tomó. |
| `total` | `en_curso` y `atendido` | casos objetivo: los sin sugerencia (nuevos, pendientes, con error) más los de revisión manual (cualquier motivo), más los que esperan turno. Crece mientras el conector los examina (primeras pasadas). |
| `enviados` | `en_curso` | enviados al núcleo en la corrida. |
| `resueltos` | `en_curso` y `atendido` | casos ya cerrados (con o sin sugerencia). |
| `con_sugerencia` | idem | cerrados con sugerencia (`completada`). |
| `sin_sugerencia` | idem | cerrados que siguen en revisión manual o con error (`resueltos - con_sugerencia`). |
| `en_vuelo` | `en_curso` | enviados al núcleo, sin respuesta. El conector manda como máximo 12 a la vez (`KERNA_MANUAL_EN_VUELO`) para no saturar al núcleo. |
| `eta_s` | `en_curso` | segundos estimados para terminar (`-1` = aún sin estimación; `0` al terminar). |
| `actualizado_en` | siempre | ISO UTC del último avance (cada ~10 s en curso). Si lleva más de 5 min sin cambiar con `en_curso`, el conector está caído. |
| `fin`, `atendido_en` | `atendido` | ISO UTC de término (iguales; `atendido_en` es el campo antiguo). |
| `reintentados` | `atendido` | = `total` (campo antiguo, el que ya lee el front). |
| `incompleto` | `en_curso`/`atendido` | `true` si se cerró por tope de 2 h sin terminar todo. |

Textos sugeridos para el botón:
- `en_curso`: botón deshabilitado en gris, «Reintentando… {resueltos} de {total}»; tooltip «en curso desde {inicio}, faltan ~{eta_s/60} min» (si `eta_s >= 0`).
- `atendido`: botón normal y resultado «{reintentados} reintentados · {con_sugerencia} con sugerencia».

Semántica: el conector ya no estima por 7 días. Toma la lista real desde su estado y desde Veridy: casos sin sugerencia (nuevo, pendiente, error) y casos cuya última sugerencia es `revision_manual` (cualquier motivo, sin tope de intentos). Los vuelve a enviar al núcleo con una referencia derivada de la corrida y publica una nota nueva en Veridy si salió sugerencia (el cliente muestra la más reciente). Una nueva pulsación durante `en_curso` no debe escribir nada.

## Fila `conector` (RowKey `conector`): estado en vivo, sin Log Analytics

Se reescribe al final de cada pasada (cada `intervalo_s`, 30 s por defecto; 10 s con una corrida en curso). Es la fuente inmediata para «En vivo»: latencia de segundos en vez de minutos.

`actualizado_en` (hora del último dato; el conector está caído si tiene más de 5 min), `ultima_pasada` (`ok`, `con_errores`, `nucleo_caido`…), `casos` (casos en Veridy), `nuevo`, `pendiente` (esperando al núcleo), `error`, `completado` (con sugerencia publicada, incluidos los de revisión manual), `en_revision_manual` (completados cuya última sugerencia es revisión manual; los más antiguos se rellenan de a 20 por pasada, `resultado_desconocido` cuenta los que faltan), `nucleo_caido`, `enviados`/`sugerencias`/`errores` (de la última pasada), `en_reintento` (hay corrida), `intervalo_s`.

## Ajustes que el conector ya aplica

Lee la fila `ajustes`/`kerna`/`actual` en cada pasada (`ajustes_de_tabla` en la fila `conector` indica si la leyó) y aplica de inmediato, sin reiniciar; la fila `conector` también trae los valores en uso (`envios_max`, `reintentos_max`, `espera_h`, `intervalo_s`, `ajustes_aplicados`):

| Ajuste del panel | Efecto |
|---|---|
| `envios` (Casos por ronda) | tope de envíos al núcleo por pasada |
| `reintentos` (Reintentos automáticos) | veces que se reintenta un caso en revisión manual por fallo de modelos (0 = no) |
| `espera` (Esperar entre reintentos) | horas entre reintentos automáticos |
| `revision` (Revisar Veridy cada) | segundos entre pasadas (5 a 3600) |
| `reprocesar` (Reintentar los de revisión manual) | por cada guardado con el ajuste activo, el conector crea un pedido `origen=ajustes` y corre el reintento manual |

Valores fuera de rango se ignoran (rige el del entorno). **No son del conector** (los aplica el núcleo, ver `kerna-pendientes.md`): `evaluador`, `candidatos`, `cadena`; `compartir`, `maxresp` y `alerta` son del panel.

## Observaciones de la verificación (2026-11-13)
- Los conteos de la fila `conector` salen del estado del conector, que aún guarda casos que ya no existen en Veridy: `completado` puede superar a `casos`, y `resultado_desconocido` incluye esos casos. El primer pedido real tomó 99 casos de 117 en Veridy y tardó 29 min (el núcleo atiende ~3 casos por minuto con 12 en vuelo).
- Con Veridy apagado el conector no corre: un pedido queda en `solicitado` hasta que Veridy se encienda.
