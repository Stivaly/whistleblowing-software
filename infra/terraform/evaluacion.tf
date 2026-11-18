# Prueba comparativa de embeddings (PR-01):
#  (a) job manual que corre los modelos abiertos DENTRO de Azure (CPU, perfil Consumption);
#  (b) Azure OpenAI con text-embedding-3-large, cuya clave y endpoint quedan en Key Vault.
# Reutiliza la identidad, el registro, el entorno y el Key Vault de main.tf.

locals {
  imagen_eval = "${azurerm_container_registry.acr.login_server}/kerna-eval-embeddings:${var.imagen_eval_tag}"

  # Secreto en Key Vault => variable de entorno del job (los dos ya existen por el pipeline).
  secretos_eval = {
    "qdrant-url"     = "QDRANT_URL"
    "qdrant-api-key" = "QDRANT_API_KEY"
  }
}

variable "crear_job_eval" {
  description = "true cuando la imagen kerna-eval-embeddings ya esté en el registro (infra/scripts/subir_imagen_eval.sh)"
  type        = bool
  default     = false
}

variable "imagen_eval_tag" {
  description = "Tag de la imagen con que se CREA el job de evaluación. Las versiones siguientes se actualizan con az containerapp job update"
  type        = string
  default     = "v1"
}

variable "eval_modelos" {
  description = "Modelos abiertos que evalúa el job (lista separada por comas; el más pesado al final)"
  type        = string
  default     = "embeddinggemma-300m,bge-m3,multilingual-e5-large-instruct,qwen3-embedding-8b"
}

variable "openai_region" {
  description = "Región de Azure OpenAI (DataZoneStandard procesa dentro de la zona de datos de EE. UU.)"
  type        = string
  default     = "westus"
}

variable "openai_capacidad_miles_tpm" {
  description = "Capacidad del despliegue en miles de tokens por minuto"
  type        = number
  default     = 100
}

# ------------------------------------------------------- job de modelos abiertos
resource "azurerm_container_app_job" "eval_embeddings" {
  count = var.crear_job_eval ? 1 : 0

  name                         = "job-${local.base}-eval-embeddings"
  location                     = azurerm_resource_group.rg.location
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azapi_resource.env.id
  workload_profile_name        = "Consumption"
  replica_timeout_in_seconds   = 9000
  replica_retry_limit          = 1
  tags                         = local.etiquetas

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.pipeline.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.pipeline.id
  }

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  dynamic "secret" {
    for_each = local.secretos_eval
    content {
      name                = secret.key
      key_vault_secret_id = "${azurerm_key_vault.kv.vault_uri}secrets/${secret.key}"
      identity            = azurerm_user_assigned_identity.pipeline.id
    }
  }

  template {
    container {
      name   = "eval-embeddings"
      image  = local.imagen_eval
      cpu    = 4
      memory = "8Gi"

      dynamic "env" {
        for_each = local.secretos_eval
        content {
          name        = env.value
          secret_name = env.key
        }
      }

      env {
        name  = "MODELOS"
        value = var.eval_modelos
      }
      env {
        name  = "EVALUACIONES_TABLA_URL"
        value = azurerm_storage_account.nucleo.primary_table_endpoint
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.pipeline.client_id
      }
    }
  }

  # Las imágenes nuevas se despliegan con az containerapp job update (subir_imagen_eval.sh).
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [
    azurerm_role_assignment.pipeline_acr_pull,
    azurerm_role_assignment.pipeline_kv_lectura,
  ]
}

# ------------------------------------------------------------------ Azure OpenAI
resource "azurerm_cognitive_account" "openai" {
  name                  = "oai-${local.base}-${local.sufijo}"
  location              = var.openai_region
  resource_group_name   = azurerm_resource_group.rg.name
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "oai-${local.base}-${local.sufijo}"
  tags                  = local.etiquetas
}

resource "azurerm_cognitive_deployment" "text_embedding_3_large" {
  name                 = "text-embedding-3-large"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-large"
    version = "1"
  }

  sku {
    name     = "DataZoneStandard"
    capacity = var.openai_capacidad_miles_tpm
  }
}

# La clave y el endpoint quedan en Key Vault; el pipeline los lee como AZURE_OPENAI_KEY y AZURE_OPENAI_ENDPOINT.
resource "azurerm_key_vault_secret" "azure_openai_key" {
  name         = "azure-openai-key"
  value        = azurerm_cognitive_account.openai.primary_access_key
  key_vault_id = azurerm_key_vault.kv.id
  tags         = local.etiquetas

  depends_on = [azurerm_role_assignment.yo_kv_secretos]
}

resource "azurerm_key_vault_secret" "azure_openai_endpoint" {
  name         = "azure-openai-endpoint"
  value        = azurerm_cognitive_account.openai.endpoint
  key_vault_id = azurerm_key_vault.kv.id
  tags         = local.etiquetas

  depends_on = [azurerm_role_assignment.yo_kv_secretos]
}

output "job_eval_embeddings" {
  value = [for j in azurerm_container_app_job.eval_embeddings : j.name]
}

output "repositorio_eval_embeddings" {
  value = "${azurerm_container_registry.acr.login_server}/kerna-eval-embeddings"
}

output "azure_openai_endpoint" {
  value = azurerm_cognitive_account.openai.endpoint
}

# Chat para el agente evaluador (capacidad baja a propósito: limita el ritmo de gasto).
resource "azurerm_cognitive_deployment" "gpt_5_nano" {
  name                 = "gpt-5-nano"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "gpt-5-nano"
    version = "2025-08-07"
  }

  sku {
    name     = "GlobalStandard"
    capacity = 250
  }
}

resource "azurerm_cognitive_deployment" "gpt_5_mini" {
  name                 = "gpt-5-mini"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "gpt-5-mini"
    version = "2025-08-07"
  }

  sku {
    name     = "GlobalStandard"
    capacity = 600
  }

  depends_on = [azurerm_cognitive_deployment.gpt_5_nano]
}

# ------------------------------------------------------- tabla de resultados de medición
# Cada medición (recall, anonimizador, pruebas, comparación de embeddings, job de Azure) escribe aquí además de su JSONL.
# La tabla se gestiona por ARM (azapi): azurerm_storage_table lee sus ACL por el plano de datos con clave
# compartida, y esta cuenta no admite claves.
removed {
  from = azurerm_storage_table.evaluaciones
  lifecycle {
    destroy = false
  }
}

import {
  to = azapi_resource.tabla_evaluaciones
  id = "${azurerm_storage_account.nucleo.id}/tableServices/default/tables/evaluaciones"
}

resource "azapi_resource" "tabla_evaluaciones" {
  type      = "Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01"
  name      = "evaluaciones"
  parent_id = "${azurerm_storage_account.nucleo.id}/tableServices/default"
  body      = { properties = {} }
}

resource "azurerm_role_assignment" "pipeline_evaluaciones" {
  scope                = "${azurerm_storage_account.nucleo.id}/tableServices/default/tables/${azapi_resource.tabla_evaluaciones.name}"
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_user_assigned_identity.pipeline.principal_id
}

# ------------------------------------------------------- datos de negocio del front
# `clientes` (plan, tarifa, estado) y `uso_diario` (denuncias, adopción y tokens por modelo, por cliente y día).
# Sin textos de denuncias. Las siembra kerna/front/sembrar_negocio.py; el front las lee con rol Table Data Reader.
resource "azapi_resource" "tabla_clientes" {
  type      = "Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01"
  name      = "clientes"
  parent_id = "${azurerm_storage_account.nucleo.id}/tableServices/default"
  body      = { properties = {} }
}

resource "azapi_resource" "tabla_uso_diario" {
  type      = "Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01"
  name      = "usodiario"
  parent_id = "${azurerm_storage_account.nucleo.id}/tableServices/default"
  body      = { properties = {} }
}

resource "azurerm_role_assignment" "front_negocio" {
  for_each             = var.crear_front ? { clientes = azapi_resource.tabla_clientes.name, usodiario = azapi_resource.tabla_uso_diario.name } : {}
  scope                = "${azurerm_storage_account.nucleo.id}/tableServices/default/tables/${each.value}"
  role_definition_name = "Storage Table Data Reader"
  principal_id         = azurerm_linux_web_app.front[0].identity[0].principal_id
}

# Solicitud de reintento manual desde el panel: una sola fila (RowKey "solicitud") que el front escribe con
# «Reintentar ahora» y que el conector lee y marca como atendida. Sin textos de denuncias ni identificadores de casos.
resource "azapi_resource" "tabla_reintentos" {
  type      = "Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01"
  name      = "reintentosmanuales"
  parent_id = "${azurerm_storage_account.nucleo.id}/tableServices/default"
  body      = { properties = {} }
}

resource "azurerm_role_assignment" "front_reintentos" {
  count                = var.crear_front ? 1 : 0
  scope                = "${azurerm_storage_account.nucleo.id}/tableServices/default/tables/${azapi_resource.tabla_reintentos.name}"
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_linux_web_app.front[0].identity[0].principal_id
}

# Ajustes del panel (Ajustes de Kerna): una sola fila (PartitionKey "kerna", RowKey "actual") con los valores en JSON.
# Solo la escribe una sesión del panel (con protección CSRF). El núcleo y el conector aún no la leen.
resource "azapi_resource" "tabla_ajustes" {
  type      = "Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01"
  name      = "ajustes"
  parent_id = "${azurerm_storage_account.nucleo.id}/tableServices/default"
  body      = { properties = {} }
}

resource "azurerm_role_assignment" "front_ajustes" {
  count                = var.crear_front ? 1 : 0
  scope                = "${azurerm_storage_account.nucleo.id}/tableServices/default/tables/${azapi_resource.tabla_ajustes.name}"
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_linux_web_app.front[0].identity[0].principal_id
}

# Administración de clientes desde el panel (vista «Clientes»): agregar y dar de baja escribe en `clientes`; el borrado por ley
# reemplaza el identificador del cliente por un uuid en `usodiario` y `solicitud` (copia la fila y retira la original) y limpia el
# texto libre de las tablas de respuestas. Las tablas `solicitud`, `sugerenciaarticulo`, `valoracion` y `clasificacion` las crea el
# núcleo al arrancar, no Terraform: el permiso apunta a ellas por nombre.
resource "azurerm_role_assignment" "front_clientes_admin" {
  for_each             = var.crear_front ? toset(["clientes", "usodiario", "solicitud", "sugerenciaarticulo", "valoracion", "clasificacion"]) : toset([])
  scope                = "${azurerm_storage_account.nucleo.id}/tableServices/default/tables/${each.value}"
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_linux_web_app.front[0].identity[0].principal_id
}
