# Kerna AI

Sugerencia normativa para los casos de Veridy. Cuando llega una denuncia, Kerna propone al auditor los artículos de
la normativa chilena que podrían aplicar, con la cita textual y el enlace a la fuente. Es una ayuda: la decisión y la
clasificación son del auditor.

## Cómo fluye un caso

1. El denunciante envía el caso en Veridy. Veridy lo guarda cifrado.
2. El **conector** (cuenta de servicio `kerna-conector`, destinataria del caso) lo lee con su sesión cada 30 s, lo
   anonimiza y lo envía al **núcleo**.
3. El núcleo vuelve a anonimizar, clasifica, recupera los artículos vigentes (Voyage + Qdrant; si fallan, el
   **servicio local**), genera la sugerencia y valida cada cita contra el texto del artículo.
4. El conector publica el resultado como nota interna del caso (cifrada con la clave del caso).
5. El auditor lo ve en el bloque de Kerna de la vista del caso, lo valora y registra su clasificación. El denunciante
   nunca ve nada de Kerna.

El contrato entre las piezas (notas, API del núcleo, cadena de modelos) está en [`docs/contratos.md`](docs/contratos.md).

## Componentes

| Carpeta | Qué es | Dónde corre |
|---|---|---|
| [`nucleo/`](nucleo/README.md) | API y cadena de sugerencia | Container App `ca-kerna-dev-nucleo` (escala a cero) |
| [`conector/`](conector/README.md) | Reconciliación Veridy ↔ núcleo | Contenedor `conector` del grupo de Veridy |
| [`servicio_local/`](servicio_local/README.md) | Embedding abierto e índice de respaldo | Container App `ca-kerna-dev-servicio-local` (escala a cero) |
| [`pipeline_bcn/`](pipeline_bcn/README.md) | Extracción de la normativa (BCN) y vectorización | Jobs `job-kerna-dev-diario`, `-semanal`, `-vigencia-21719` |
| [`comun/`](comun/README.md) | Anonimizador, notas y telemetría compartidos | Biblioteca |
| [`evaluacion/`](evaluacion/informe-embeddings.md) | Mediciones, informe de embeddings y matriz de pruebas | Local y job `job-kerna-dev-eval-embeddings` |
| [`pruebas/`](pruebas/README.md) | Suite automatizada | `scripts/probar.sh` |
| `docs/diseno/` | Diseño y textos del bloque; opciones de ícono en `docs/diseno/opciones-icono/` | |
| [`docs/observabilidad/`](docs/observabilidad/README.md) | Consultas KQL del Workbook y de las alertas | Workbook «Kerna AI: resultados» |

El bloque de la interfaz está en `client/app/src/shared/partials/kerna/`. La infraestructura de Kerna está en
`infra/terraform` y la de Veridy (con el conector) en `infra/veridy/terraform`.

## Operación

Ningún modelo corre en el servidor de desarrollo: los de lenguaje se usan por API y los de embeddings abiertos corren
en Azure.

| Tarea | Comando |
|---|---|
| Encender, apagar o ver Veridy (y el conector) | `infra/veridy/veridy.sh encender \| apagar \| estado` |
| Logs del conector | `infra/veridy/veridy.sh logs conector` |
| Imagen nueva del núcleo o del conector | `infra/scripts/subir_imagen_kerna.sh nucleo --desplegar` · `... conector --tag <tag>` y `conector_tag` en `infra/veridy/terraform/terraform.tfvars` |
| Imagen nueva del pipeline | `infra/scripts/subir_imagen.sh --desplegar` |
| Lanzar un job a mano | `az containerapp job start -g rg-kerna-dev -n job-kerna-dev-diario` |
| Cambiar la cadena de modelos, la concurrencia o la URL del servicio local | `nucleo_entorno` en `infra/terraform/terraform.tfvars` y `terraform apply` |
| Recargar el índice local tras vectorizar | `POST {servicio_local_url}/recargar` con `X-Token-Interno` |
| Pruebas | `scripts/probar.sh unitarias \| integracion \| e2e \| carga \| veridy \| todo` |

Los secretos están en Key Vault (`kv-kerna-dev-g6mzy` y, los del conector, `kv-veridy-dev-kdicq`); los propios de
Kerna los genera Terraform.

## Diagnóstico

| Síntoma | Dónde mirar |
|---|---|
| El caso queda «en proceso» | Logs del conector: cada pasada informa `casos`, `enviados`, `sugerencias`, `errores`. Si Veridy está apagado, el conector también |
| `revision_manual` con `cadena_agotada` | `AppTraces` (`log-kerna-dev`): eventos `nivel_fallido` (modelo y código) y `recuperacion_nube_fallida` / `recuperacion_local_fallida` |
| Todo sale en modo respaldo o tarda | `nivel_fallido` del modelo oficial: 429 es cuota de la clave, 503 es el proveedor |
| `version_corpus` en 0 | Falta el punto meta de la colección: lo repone cualquier corrida del pipeline |
| El primer caso tras un rato tarda | El núcleo y el servicio local escalan a cero y tardan en despertar |

Las consultas de `docs/observabilidad/consultas/` responden estas preguntas sobre el mismo espacio de trabajo.
