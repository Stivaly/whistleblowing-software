# Servicio local de Kerna AI (kerna/servicio_local): embeddings abiertos (multilingual-e5-large-instruct) e índice
# en memoria para la recuperación de contingencia. Container App con escala a cero: sin tráfico no hay réplicas
# y no se cobra cómputo. El índice (vectores + payload) se carga desde Qdrant y queda copiado en el contenedor de
# blobs "indice-local" de la cuenta del núcleo, para arrancar aunque Qdrant Cloud esté caído.

locals {
  imagen_servicio_local = "${azurerm_container_registry.acr.login_server}/kerna-servicio-local:${var.imagen_servicio_local_tag}"

  secretos_servicio_local = {
    "kerna-local-token" = "KERNA_LOCAL_TOKEN"
    "qdrant-url"        = "QDRANT_URL"
    "qdrant-api-key"    = "QDRANT_API_KEY"
  }
}

variable "crear_servicio_local" {
  description = "true cuando la imagen kerna-servicio-local esté en el registro (infra/scripts/subir_imagen_kerna.sh servicio_local)"
  type        = bool
  default     = false
}

variable "imagen_servicio_local_tag" {
  description = "Tag de la imagen con que se CREA el servicio local. Las versiones siguientes se despliegan con subir_imagen_kerna.sh servicio_local --desplegar"
  type        = string
  default     = "v1"
}

# ------------------------------------------------------------- copia del índice
resource "azurerm_storage_container" "indice_local" {
  name                  = "indice-local"
  storage_account_id    = azurerm_storage_account.nucleo.id
  container_access_type = "private"
}

# -------------------------------------------------------------------- identidad
resource "azurerm_user_assigned_identity" "servicio_local" {
  name                = "id-${local.base}-servicio-local"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.etiquetas
}

resource "azurerm_role_assignment" "servicio_local_acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.servicio_local.principal_id
}

resource "azurerm_role_assignment" "servicio_local_kv_lectura" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.servicio_local.principal_id
}

resource "azurerm_role_assignment" "servicio_local_blobs" {
  scope                = azurerm_storage_container.indice_local.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.servicio_local.principal_id
}

# ------------------------------------------------------------------------- app
resource "azurerm_container_app" "servicio_local" {
  count = var.crear_servicio_local ? 1 : 0

  name                         = "ca-${local.base}-servicio-local"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azapi_resource.env.id
  workload_profile_name        = "Consumption"
  revision_mode                = "Single"
  tags                         = local.etiquetas

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.servicio_local.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.servicio_local.id
  }

  dynamic "secret" {
    for_each = local.secretos_servicio_local
    content {
      name                = secret.key
      key_vault_secret_id = "${azurerm_key_vault.kv.vault_uri}secrets/${secret.key}"
      identity            = azurerm_user_assigned_identity.servicio_local.id
    }
  }

  secret {
    name  = "appinsights-conexion"
    value = azurerm_application_insights.kerna.connection_string
  }

  ingress {
    external_enabled           = true
    target_port                = 8080
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # Una sola réplica: el índice vive en memoria. Sin tráfico baja a cero; el arranque en frío descarga el
    # modelo (~2,2 GB) y /salud responde 503 hasta que está listo, así que el ingress retiene la primera solicitud.
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "servicio-local"
      image  = local.imagen_servicio_local
      cpu    = 2
      memory = "4Gi"

      dynamic "env" {
        for_each = local.secretos_servicio_local
        content {
          name        = env.value
          secret_name = env.key
        }
      }

      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-conexion"
      }
      env {
        name  = "KERNA_BLOB_URL"
        value = trimsuffix(azurerm_storage_account.nucleo.primary_blob_endpoint, "/")
      }
      env {
        name  = "KERNA_BLOB_CONTENEDOR"
        value = azurerm_storage_container.indice_local.name
      }
      env {
        name  = "KERNA_LOCAL_COLECCION"
        value = "normativa_cl_local"
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.servicio_local.client_id
      }

      # Hasta 10 x 30 s para descargar y cargar el modelo antes de considerarlo fallido.
      startup_probe {
        transport               = "HTTP"
        path                    = "/salud"
        port                    = 8080
        interval_seconds        = 30
        timeout                 = 5
        failure_count_threshold = 10
      }
      liveness_probe {
        transport               = "HTTP"
        path                    = "/salud"
        port                    = 8080
        interval_seconds        = 30
        timeout                 = 5
        failure_count_threshold = 5
      }
    }
  }

  # Las versiones nuevas de la imagen las despliega infra/scripts/subir_imagen_kerna.sh servicio_local --desplegar.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [
    azurerm_role_assignment.servicio_local_acr_pull,
    azurerm_role_assignment.servicio_local_kv_lectura,
    azurerm_role_assignment.servicio_local_blobs,
  ]
}

output "servicio_local_url" {
  value = var.crear_servicio_local ? "https://${azurerm_container_app.servicio_local[0].ingress[0].fqdn}" : null
}

output "repositorio_servicio_local" {
  value = "${azurerm_container_registry.acr.login_server}/kerna-servicio-local"
}
