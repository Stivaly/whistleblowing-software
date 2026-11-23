# Pasarela de identidad para la instalación local de prueba (entregable/, kerna/pasarela/).
# El panel de Kerna y el conector de Veridy que corren en el computador de quien prueba piden aquí, por HTTPS (443),
# tokens de corta duración de esta identidad para leer Log Analytics, las tablas del núcleo y los costos. Así
# funcionan desde cualquier red que permita navegar por HTTPS, sin puertos extra ni VPN. La clave de la pasarela
# va en el paquete local (variable IDENTITY_HEADER). Escala a cero: sin uso no cobra cómputo.

variable "crear_pasarela" {
  description = "true cuando la imagen kerna-pasarela esté en el registro (infra/scripts/subir_imagen_kerna.sh pasarela)"
  type        = bool
  default     = true
}

variable "imagen_pasarela_tag" {
  description = "Tag de la imagen kerna-pasarela con que se crea la app; las siguientes se despliegan con subir_imagen_kerna.sh pasarela --desplegar"
  type        = string
  default     = "v1"
}

resource "random_password" "pasarela" {
  length  = 48
  special = false
}

resource "azurerm_key_vault_secret" "pasarela" {
  name         = "pasarela-clave"
  value        = random_password.pasarela.result
  key_vault_id = azurerm_key_vault.kv.id
}

resource "azurerm_user_assigned_identity" "pasarela" {
  name                = "id-${local.base}-pasarela"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.etiquetas
}

resource "azurerm_role_assignment" "pasarela_acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.pasarela.principal_id
}

# Los mismos permisos de datos que la identidad del panel en Azure (front.tf y evaluacion.tf), sin Key Vault.
resource "azurerm_role_assignment" "pasarela_logs" {
  scope                = azurerm_log_analytics_workspace.logs.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = azurerm_user_assigned_identity.pasarela.principal_id
}

resource "azurerm_role_assignment" "pasarela_tablas" {
  scope                = "${azurerm_storage_account.nucleo.id}/tableServices/default"
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_user_assigned_identity.pasarela.principal_id
}

resource "azurerm_role_assignment" "pasarela_metricas_openai" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Monitoring Reader"
  principal_id         = azurerm_user_assigned_identity.pasarela.principal_id
}

resource "azurerm_role_assignment" "pasarela_costos" {
  scope                = "/subscriptions/${data.azurerm_client_config.actual.subscription_id}"
  role_definition_name = "Cost Management Reader"
  principal_id         = azurerm_user_assigned_identity.pasarela.principal_id
}

resource "azurerm_container_app" "pasarela" {
  count = var.crear_pasarela ? 1 : 0

  name                         = "ca-${local.base}-pasarela"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azapi_resource.env.id
  workload_profile_name        = "Consumption"
  revision_mode                = "Single"
  tags                         = local.etiquetas

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.pasarela.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.pasarela.id
  }

  secret {
    name  = "pasarela-clave"
    value = random_password.pasarela.result
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
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "pasarela"
      image  = "${azurerm_container_registry.acr.login_server}/kerna-pasarela:${var.imagen_pasarela_tag}"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name        = "PASARELA_CLAVE"
        secret_name = "pasarela-clave"
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.pasarela.client_id
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.pasarela_acr_pull]
}

output "pasarela_url" {
  value = var.crear_pasarela ? "https://${azurerm_container_app.pasarela[0].ingress[0].fqdn}" : null
}
