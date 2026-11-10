# Núcleo de Kerna AI: API y cadena por caso (kerna/nucleo), como Container App con escala a cero.
# Todo es de pago por uso: sin réplicas no hay cobro de cómputo, y la cuenta de almacenamiento
# solo cobra por las pocas entidades que guarda.

locals {
  imagen_nucleo = "${azurerm_container_registry.acr.login_server}/kerna-nucleo:${var.imagen_nucleo_tag}"

  # Secreto en Key Vault => variable de entorno. Los valores se cargan con az keyvault secret set.
  secretos_nucleo = {
    "gemini-api-key"    = "GEMINI_API_KEY"
    "voyage-api-key"    = "VOYAGE_API_KEY"
    "qdrant-url"        = "QDRANT_URL"
    "qdrant-api-key"    = "QDRANT_API_KEY"
    "kerna-jwt-secreto" = "KERNA_JWT_SECRETO"
    "kerna-clientes"    = "KERNA_CLIENTES"
    "kerna-local-token" = "KERNA_LOCAL_TOKEN"
  }
}

variable "crear_nucleo" {
  description = "true cuando la imagen kerna-nucleo esté en el registro y sus secretos en Key Vault"
  type        = bool
  default     = false
}

variable "imagen_nucleo_tag" {
  description = "Tag de la imagen con que se CREA el núcleo. Las versiones siguientes se despliegan con infra/scripts/subir_imagen_nucleo.sh"
  type        = string
  default     = "v1"
}

variable "nucleo_entorno" {
  description = "Variables sin secreto del núcleo (colección, embedding, URL del servicio local, umbrales)"
  type        = map(string)
  default     = {}
}

# ------------------------------------------------------------- almacén (tablas)
resource "azurerm_storage_account" "nucleo" {
  name                            = "st${var.prefijo}${var.ambiente}${local.sufijo}"
  location                        = azurerm_resource_group.rg.location
  resource_group_name             = azurerm_resource_group.rg.name
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false # solo identidades de Entra ID
  tags                            = local.etiquetas
}

# -------------------------------------------------------------------- identidad
resource "azurerm_user_assigned_identity" "nucleo" {
  name                = "id-${local.base}-nucleo"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.etiquetas
}

resource "azurerm_role_assignment" "nucleo_acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.nucleo.principal_id
}

resource "azurerm_role_assignment" "nucleo_kv_lectura" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.nucleo.principal_id
}

resource "azurerm_role_assignment" "nucleo_tablas" {
  scope                = azurerm_storage_account.nucleo.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_user_assigned_identity.nucleo.principal_id
}

# Quien corre Terraform puede leer las tablas (mediciones de KPI y diagnóstico).
resource "azurerm_role_assignment" "yo_tablas" {
  scope                = azurerm_storage_account.nucleo.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = data.azurerm_client_config.actual.object_id
}

# ---------------------------------------------------------------- observabilidad
resource "azurerm_application_insights" "kerna" {
  name                = "appi-${local.base}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  workspace_id        = azurerm_log_analytics_workspace.logs.id
  application_type    = "web"
  tags                = local.etiquetas
}

# ------------------------------------------------------------------------- app
resource "azurerm_container_app" "nucleo" {
  count = var.crear_nucleo ? 1 : 0

  name                         = "ca-${local.base}-nucleo"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azapi_resource.env.id
  workload_profile_name        = "Consumption"
  revision_mode                = "Single"
  tags                         = local.etiquetas

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.nucleo.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.nucleo.id
  }

  dynamic "secret" {
    for_each = local.secretos_nucleo
    content {
      name                = secret.key
      key_vault_secret_id = "${azurerm_key_vault.kv.vault_uri}secrets/${secret.key}"
      identity            = azurerm_user_assigned_identity.nucleo.id
    }
  }

  secret {
    name  = "appinsights-conexion"
    value = azurerm_application_insights.kerna.connection_string
  }

  ingress {
    external_enabled           = true
    target_port                = 8000
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # Una sola réplica: la cadena por caso corre en segundo plano dentro del proceso y el
    # cortocircuito de proveedores vive en memoria. Sin tráfico, baja a cero.
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "nucleo"
      image  = local.imagen_nucleo
      cpu    = 0.5
      memory = "1Gi"

      dynamic "env" {
        for_each = local.secretos_nucleo
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
        name  = "KERNA_ALMACEN"
        value = "tablas"
      }
      env {
        name  = "KERNA_TABLAS_URL"
        value = azurerm_storage_account.nucleo.primary_table_endpoint
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.nucleo.client_id
      }

      dynamic "env" {
        for_each = var.nucleo_entorno
        content {
          name  = env.key
          value = env.value
        }
      }

      liveness_probe {
        transport = "HTTP"
        path      = "/salud"
        port      = 8000
      }
      startup_probe {
        transport = "HTTP"
        path      = "/salud"
        port      = 8000
      }
    }
  }

  # Las versiones nuevas de la imagen las despliega infra/scripts/subir_imagen_nucleo.sh.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [
    azurerm_role_assignment.nucleo_acr_pull,
    azurerm_role_assignment.nucleo_kv_lectura,
    azurerm_role_assignment.nucleo_tablas,
  ]
}

output "nucleo_url" {
  value = var.crear_nucleo ? "https://${azurerm_container_app.nucleo[0].ingress[0].fqdn}" : null
}

output "nucleo_tablas_url" {
  value = azurerm_storage_account.nucleo.primary_table_endpoint
}

output "repositorio_nucleo" {
  value = "${azurerm_container_registry.acr.login_server}/kerna-nucleo"
}

output "app_insights_nombre" {
  value = azurerm_application_insights.kerna.name
}
