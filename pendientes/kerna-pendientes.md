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
- **Nada está commiteado**: `infra/`, `kerna/`, `pendientes/` siguen sin seguimiento en git.

## Reglas para retomar

- La usuaria ejecuta todo comando de instalación, `az` y `terraform apply`; Claude entrega comandos y espera la salida.
- No cambiar la capa de datos (MongoDB Atlas + Qdrant). Modelos: Google Gemini (demo con datos públicos).
- No eliminar nada: mover a `.papelera/` y registrar en `pendientes/eliminaciones-pendientes.md`.

## 1. Infraestructura (lo ejecuta la usuaria — `infra/terraform/README.md`)

- [ ] Paso 0: instalar Azure CLI y Terraform.
- [ ] Paso 1: `az login --use-device-code`.
- [ ] Paso 2: verificar que eastus2 esté entre las regiones permitidas (pegar la salida).
- [ ] Paso 3: registrar proveedores de recursos.
- [ ] Paso 4: storage del estado + `backend.hcl` + `terraform.tfvars`.
- [ ] Paso 5: `terraform init/validate/plan` → **pegar el plan antes de apply**. Posible ajuste: el atributo
      `rbac_authorization_enabled` del Key Vault depende de la versión del proveedor azurerm.
- [ ] Paso 6: crear cluster Qdrant Cloud (gratis, en Azure) y API key de Gemini (AI Studio); agregarlas al `.env`;
      cargar los 4 secretos en Key Vault.
- [ ] Paso 7: `infra/scripts/subir_imagen.sh --tag v1`.
- [ ] Paso 8: `crear_jobs = true` + plan/apply.
- [ ] Paso 9: Atlas → Network Access → `0.0.0.0/0` (temporal, 1-2 meses; revisar fecha de cierre).
- [ ] Paso 10: `infra/scripts/subir_imagen.sh --desplegar --probar diario` y revisar logs.
- [ ] Atlas: eliminar o rotar el usuario anterior con `atlasAdmin` (su clave quedó expuesta en un error).
- [ ] Respaldo de MongoDB (M0 no tiene backups): `mongodump` semanal programado.

## 2. Código pendiente

- [ ] `embed_sync.py`: proveedor Gemini (`gemini-embedding-2`, está en preview). Verificar dimensiones y ajustar `DIMS`
      y la colección de Qdrant. Luego correr los 172 embeddings y medir recall@5 (meta ≥ 0,8).
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

- [ ] Adaptar `gl_patches` (en `fable upgrades/kerna_entrega2.zip`) al flujo asíncrono: `POST /api/denuncias` (202),
      webhook de sugerencia lista, `GET /api/sugerencias/{id}`, `POST /api/feedback`, clave de función.
- [ ] Panel del auditor: aviso "sugerencia generada con un modelo en evaluación".
- [ ] Migración de la plataforma a Postgres/Supabase (doc `fable upgrades/07`): estado no revisado en esta sesión.

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
- [ ] ¿Cuándo se commitea el trabajo y en qué rama? (hoy todo está sin seguimiento en `stable`).
