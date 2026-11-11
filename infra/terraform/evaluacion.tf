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
