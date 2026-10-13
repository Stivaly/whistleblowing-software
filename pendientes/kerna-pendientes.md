# Kerna AI — pendientes (actualizado 2026-10-02)

Punto de partida para retomar en otra sesión. Contexto y porqués: doc **Resumen técnico**
https://claude.ai/code/artifact/f09070a4-0a25-42a1-85fc-9d75e55b0b71
(pestaña principal = extractor; pestaña "Arquitectura en Azure" = diseño aprobado).

## Estado actual (hecho)

- Extractor BCN reescrito y probado: `kerna/pipeline_bcn/` (12 tests OK, `README.md`).
- MongoDB Atlas (Azure eastus2), base `kerna` creada con `crear_bd.py`; corpus cargado: 6 normas, 201 fragmentos,
  172 pendientes de embedding. URI en `kerna/pipeline_bcn/.env` (usuario de mínimo privilegio).
- Terraform escrito, **nunca aplicado**: `infra/terraform/` (+ `README.md` paso a paso) e `infra/scripts/subir_imagen.sh`.
- Arquitectura Azure diseñada (fases A y C aprobadas, B descartada) — solo diseño, sin Terraform ni código.
- Dataset de evaluación: `kerna/evaluacion/datos/denuncias_publicas.xlsx` (+ `.json`), 113 casos públicos. Fuera de git.
- Commiteado y subido en la rama `feature/kerna-pipeline-azure` (sin `.env`, `terraform.tfvars`, `backend.hcl` ni datos de
  evaluación; se versionan solo los `.example`).

## Reglas para retomar

- La usuaria ejecuta todo comando de instalación, `az` y `terraform apply`; Claude entrega comandos y espera la salida.
- No cambiar la capa de datos (MongoDB Atlas + Qdrant). Modelos: Google Gemini (demo con datos públicos).
- No eliminar nada: mover a `.papelera/` y registrar en `pendientes/eliminaciones-pendientes.md`.

## 1. Infraestructura (lo ejecuta la usuaria — `infra/terraform/README.md`)

- [x] Paso 0: Azure CLI 2.91.0 y Terraform 1.16.5 instalados (2026-10-12).
- [x] Paso 1: `az login` OK, suscripción "Azure for Students".
- [x] Paso 2: eastus2 NO permitida. Permitidas: chilecentral, mexicocentral, westus, canadacentral, southafricanorth.
      Decisión de la usuaria: `chilecentral` siempre que esté disponible y no sea caro (ya es el default en Terraform).
- [x] Paso 3: registrar proveedores + verificar disponibilidad de cada servicio en chilecentral (README, paso 2).
      Mongo Atlas sigue en Azure eastus2: tráfico entre regiones (poco volumen) y más latencia, aceptable.
- [x] Disponibilidad en chilecentral verificada (2026-10-12): Container Apps (env + jobs), ACR, Key Vault, Log Analytics,
      identidad administrada y PostgreSQL Flexible (B1ms y B2s, sin restricciones).
      Precios (API pública): ACR Basic US$0,1666/día igual que westus; PG B1ms US$0,0238/h (~US$17/mes) vs westus
      US$0,022/h (~US$16/mes), ~8% más. Diferencia menor → todo en chilecentral.
- [x] Paso 4 (2026-10-12, lo corrió Claude con autorización puntual): estado en la cuenta `stkernatf*` de `rg-kerna-tfstate` (nombre en `backend.hcl`)
      (chilecentral); `backend.hcl` y `terraform.tfvars` creados (fuera de git). El tenant de Inacap exige MFA para
      escribir: si `az` responde AADSTS50076, la usuaria repite `az login` con el `--claims-challenge` que indica el error.
- [~] Paso 5: `terraform init` (azurerm 4.81.0) y `validate` OK. Aplicados 10 de 11 recursos con `-target`
      (grupo `rg-kerna-dev`, ACR Standard y Key Vault (nombres con `terraform output`), Log Analytics,
      identidad y 4 roles). Falta `azurerm_container_app_environment.env`: `Microsoft.App` quedó en "Registering"
      más de 45 min. Cuando diga "Registered": `terraform plan -out=fase1.tfplan` (debe agregar solo el entorno) y apply.
- [x] Paso 7: imagen `kerna-pipeline:v1` (+ `latest`) subida al registro.
- [ ] Paso 6: cargar `mongodb-uri` (lo bloqueó el clasificador de permisos de Claude → lo corre la usuaria) y crear
      Qdrant Cloud + API key de Gemini para los otros 3 secretos.
- [ ] Paso 8: `crear_jobs = true` + plan/apply.
- [ ] Paso 9: Atlas → Network Access → `0.0.0.0/0` (temporal, 1-2 meses; revisar fecha de cierre).
- [ ] Paso 10: `infra/scripts/subir_imagen.sh --desplegar --probar diario` y revisar logs.
- [ ] Atlas: eliminar o rotar el usuario anterior con `atlasAdmin` (su clave quedó expuesta en un error).
- [ ] Respaldo de MongoDB (M0 no tiene backups): `mongodump` semanal programado.

## 2. Código pendiente

- [x] `embed_sync.py`: proveedor Gemini por defecto (`gemini-embedding-2`, estable desde abr-2026; 2026-10-12).
      Se mantiene `DIMS = 1024` (el modelo acepta 128-3072 y normaliza solo). Formato de documento
      `title: none | text: …`; las consultas del retriever deben usar `task: search result | query: …` con 1024 dims.
      Prueba en `test_embed_sync.py` (sin red).
- [ ] Correr los 172 embeddings (local, apenas existan Qdrant y la API key) y medir recall@5 (meta ≥ 0,8).
- [ ] Orquestador (`fable upgrades/kerna_entrega2.zip` → `kerna_orquestador/`): reemplazar el cliente de Anthropic por
      Gemini (`gemini-3.5-flash-lite` clasificar, `gemini-3.8-flash` generar), con thinking budget bajo y salida JSON.
- [ ] Orquestador: clave `kerna:llm:capa` (gratuita/pagada) y bloqueo de mensajes no sintéticos con capa gratuita;
      guardar `modelo`, `version_prompt`, `modelo_provisional` en cada sugerencia.
- [ ] `run.sh` / extractor: publicar evento `kerna.corpus.norma_actualizada` y quitar los embeddings del job diario
      cuando exista el job de embeddings disparado por evento.
- [ ] `crontab.txt` quedó como referencia para una VM; en Azure lo reemplazan los Container Apps Jobs.

## 3. Fase A (aprobada) — Terraform + código

- [x] Container Registry Standard, script de subida, `ignore_changes` de imagen en los jobs.
- [ ] Application Insights (sobre el Log Analytics existente).
- [ ] App Configuration (Free): corpus, modelos, presupuesto, top-k, feature flags (`kerna.llm.modelo_provisional`,
      vigencia anticipada, reranking por feedback, validador juez); refresco por centinela cada 1 h (cuota 1.000/día).
- [ ] Key Vault: secretos con vencimiento a 90 días + Event Grid `SecretNearExpiry` → alerta.
- [ ] OpenTelemetry (distro Azure Monitor) en pipeline, orquestador y Functions; filtro que impida texto de denuncias
      en telemetría; métricas `kerna.*` (ver pestaña de arquitectura).
- [ ] Workbook "Kerna AI — Resultados" con KQL + alertas por correo + presupuesto del grupo de recursos.

## 4. Fase C (aprobada) — Terraform + código

- [ ] Service Bus **Basic**: colas `denuncias` (3 entregas, TTL 24 h) y `corpus-cambios`; SAS desactivado.
- [ ] Event Grid tema `kerna-eventos` (CloudEvents, 5 tipos) y suscripciones (cola `corpus-cambios`, Function eventos).
- [ ] Function App Flex Consumption (Python): `api_denuncias`, `api_sugerencias`, `api_feedback`, `eventos_kerna`,
      `dlq_denuncias`, `rotacion_secretos`.
- [ ] Orquestador como Container App sin ingress, KEDA 0–3 sobre la cola `denuncias` (1 réplica mínima en demos).
- [ ] Job de embeddings disparado por evento (KEDA sobre `corpus-cambios`).
- [ ] Identidades separadas (`pipeline`, `orquestador`, `funciones`) y roles de la tabla de la pestaña de arquitectura.
- [ ] Laboratorio aparte (crear y destruir): Service Bus Standard con temas y suscripciones; AKS; Redis.

## 5. Integración con la plataforma (GlobaLeaks)

> 2026-10-04: plan nuevo en `pendientes/mapa-integracion-kerna-veridy.md` (docs: informe de Veridy, cifrado y plan de
> integración). Decisión propuesta: disparo a pedido del receptor + consulta por pull (sin endpoints entrantes), resultados
> cifrados con la clave de la denuncia. Reemplaza el enfoque de `gl_patches` de los puntos de abajo.

- [ ] Adaptar `gl_patches` (en `fable upgrades/kerna_entrega2.zip`) al flujo asíncrono: `POST /api/denuncias` (202),
      webhook de sugerencia lista, `GET /api/sugerencias/{id}`, `POST /api/feedback`, clave de función.
- [ ] Panel del auditor: aviso "sugerencia generada con un modelo en evaluación".
- [ ] Migración de la plataforma a Postgres/Supabase (doc `fable upgrades/07`): estado no revisado en esta sesión.

## 5b. Base de Veridy en PostgreSQL de Azure (2026-10-04)

- [x] Código de Veridy para PostgreSQL, probado contra PostgreSQL local (114/114 tests en PG, 195/195 en SQLite).
- [x] Suite completa del backend (2026-10-12): SQLite 341/357 y PostgreSQL 340/357 → 16 fallos de `test_migration`
      idénticos en la rama `stable` (upstream: `no such table: internalfile`); el de PostgreSQL (migración 68) ahora
      se salta porque las migraciones son solo para SQLite.
- [x] Decisión de la usuaria (2026-10-12): PostgreSQL Flexible Server (no Azure SQL), encendido solo cuando se usa.
      `infra/scripts/veridy_bd.sh` + cron: apaga tras 60 min sin peticiones a Veridy, enciende al volver a entrar
      (README paso 13; instrucción en `.claude/CLAUDE.md`). Probado con un `az` falso (4 casos).
- [x] `terraform.tfvars`: `crear_postgres = true`, IPv4 del host 181.43.152.136 (el firewall no acepta IPv6).
      Si el proveedor cambia la IP, actualizarla y volver a aplicar.
- [x] Contraseñas en Key Vault (las generó la usuaria). Servidor `psql-veridy-dev-*` creado en chilecentral
      (2026-10-12). El primer apply se cortó a medias: se liberó el bloqueo del estado y se importó el servidor.
- [x] Roles (paso 12): `veridy_app` sin superuser/createdb/createrole; no puede crear ni borrar tablas.
- [x] Prueba previa de arranque contra Azure (imagen de prueba + backend actual): esquema creado (34 tablas,
      versión 68, dueño veridyadmin), Veridy opera como `veridy_app`, segundo arranque sin credencial admin OK.
- [~] Cypress e2e (2026-10-12, 22 escenarios / 86 pruebas, contra backend en contenedor): GlobaLeaks `stable` 77/86;
      Veridy 1ª corrida 78/86 (fallan 6, 12, 15, 18, 22: los mismos escenarios fallan en `stable`). Veridy 2ª corrida
      26/86: desde el escenario 9 no aparece el formulario de login (`[name="username"]`) en cascada; con el mismo
      código que la 1ª corrida → probable estado del ambiente. Repetir aparte antes de concluir.
- [x] Veridy desplegado en Azure Container Instances (2026-10-13), Terraform propio en `infra/veridy/`:
      https://veridy-dev-kdicq.chilecentral.azurecontainer.io — imagen real `veridy:v1` (753 MB, antes 3,34 GB),
      health/public/cliente 200, http→https. Encendido manual con `infra/veridy/veridy.sh encender`; el vigía apaga
      todo tras 60 min sin uso.
- [ ] Usuaria: completar el asistente inicial de Veridy en el link (mientras no se complete, cualquiera que llegue
      al link podría hacerlo y quedar como administrador).
- [ ] Verificar el primer apagado automático del vigía (identidad administrada: stop de PostgreSQL y del grupo) y
      `veridy.sh encender` después.
- [ ] Repetir Cypress sobre Veridy para descartar la cascada de la 2ª corrida.
- [ ] Usuaria: construir la imagen y primer arranque con `docker/README-postgres.md`; quitar luego la URI de admin.
- [ ] Más adelante: script que limpie los registros de red de Veridy y de las máquinas (access.log y logs del
      contenedor, logs del host, diagnósticos de Azure si se activan), para no conservar IPs de quienes entran por
      navegador normal. Pedido por la usuaria el 2026-10-12. Tor se mantiene (quitarlo no reduce la imagen).
- [ ] Pregunta abierta: ¿aviso en la portada de que el anonimato es de contenido y no de red (no denunciar desde la
      red o el equipo del trabajo)?
- [ ] Retirar `etl_incremental.py` cuando ya no se necesite (mover a `.papelera/`, no borrar) y rotar su credencial.
- [ ] Decidir si se eliminan los recursos Docker de prueba (`pendientes/recursos-de-prueba.md`).

## 6. Evaluación del modelo (bloquea uso con denuncias reales)

- [ ] Elegir qué casos del dataset entran al set (58 de 113 son frontera; equilibrar según objetivo).
- [ ] Revisión legal de `ley_principal` y `articulos_candidatos` (son hipótesis del agente).
- [ ] Copia del set con triggers del anonimizador insertados (RUT, correo, teléfono, nombres) para medir recall por tipo.
- [ ] Comparar `gemini-3.8-flash`, `gemini-3.5-flash-lite` y un modelo superior de referencia; medir materia correcta,
      citas correctas, citas huérfanas (0), JSON válido (≥ 99 %), P95 (≤ 15 s), costo (≤ US$0,05).
- [ ] Decidir si el validador juez es obligatorio; decidir modelo definitivo y apagar `modelo_provisional`.
- [ ] Huecos del dataset: Ley 20.393 (cohecho entre privados, receptación, financiamiento del terrorismo);
      datos personales (cámaras en baños/vestidores, venta de bases); relatos de acoso en primera persona post-2024.
      Sugerido: acceso a juris.pjud.cl (tiene reCAPTCHA) y archive.org para subreddits de AR/MX/ES.

## 7. Preguntas abiertas para la usuaria

- [ ] ¿Se agregan los estatutos públicos modificados por la Ley Karin (Leyes 18.575, 18.834, 18.883, 18.695)?
      (comentario abierto en el doc).
- [x] `docker/globaleaks.tar` (172 MB) sacado del índice y agregado a `.gitignore` (2026-10-12). Sigue en disco.

## 8. Revisión de git del 2026-10-12 (decisiones para la usuaria)

- El repo `Stivaly/whistleblowing-software` es **público**: todo lo commiteado es visible.
- Historial ya subido revisado: sin credenciales (solo ejemplos `USUARIO:CLAVE`).
- `etl_incremental.py` y `etl_state.json` quedan en `.gitignore`: el ETL tiene la contraseña de Supabase escrita en el
  código. No se modificó. Al retirarlo, rotar esa credencial.
- `docs-auditoria-denuncias/03-puntos-extension.md`: se omitieron el host de Supabase y la contraseña antes de commitear.
- `fable upgrades/` queda en `.gitignore` (referencia, puede estar desactualizada). Si se quiere versionar, quitar la línea.
- [ ] Pie de página: el commit `chore(client): quitar la atribución "Powered by GlobaLeaks"` va contra los términos
      adicionales de la licencia (LICENSE, sección 7): conservar la atribución y mostrar el aviso "This server is running
      a modified version of the GlobaLeaks software..." con enlace al código. Decidir: revertir y agregar el aviso.
- [ ] `client/app/assets/data/l10n/es.json` (commit `i18n(es)`) parece de otra versión de GlobaLeaks: le faltan 14 claves
      que la interfaz usa ("Analyst", "Reopen", "Mask", "Act on behalf of a whistleblower", "Unselect"…) y deja
      "Specify" sin traducir. Revisar o restaurar el de 5.0.85 y agregar encima las claves nuevas.
- `docker/docker-compose.yml` y `pendientes/analisis-veridy/` mencionan la IP privada de la red local: no es un secreto.
