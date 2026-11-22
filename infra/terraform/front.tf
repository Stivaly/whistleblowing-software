# Front web de Kerna AI (kerna/front): portada pública y panel /panel con métricas agregadas de Log Analytics.
# App Service Linux en plan F1 (gratis, sin always-on). La identidad administrada de la app tiene
# Log Analytics Reader sobre el workspace y Key Vault Secrets User sobre el Key Vault de Kerna.
#
# Autenticación del panel: la cuenta de estudiante no puede crear registros de aplicación de Entra
# (allowedToCreateApps = false), así que /panel y /api/* se protegen con una clave guardada en Key Vault
# (secreto "front-clave-panel", que se carga con az y nunca pasa por Terraform). Para pasar a Entra ver
# kerna/front/README.md.

variable "crear_front" {
  description = "Crea el App Service del front web de Kerna AI."
  type        = bool
  default     = true
}

resource "azurerm_service_plan" "front" {
  count               = var.crear_front ? 1 : 0
  name                = "asp-${local.base}-front"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "B1"
  tags                = local.etiquetas
}

resource "azurerm_linux_web_app" "front" {
  count                   = var.crear_front ? 1 : 0
  name                    = "app-${local.base}-front-${local.sufijo}"
  location                = azurerm_resource_group.rg.location
  resource_group_name     = azurerm_resource_group.rg.name
  service_plan_id         = azurerm_service_plan.front[0].id
  https_only              = true
  client_affinity_enabled = false
  tags                    = local.etiquetas

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on           = false # F1 no lo admite
    ftps_state          = "Disabled"
    http2_enabled       = true
    minimum_tls_version = "1.2"
    app_command_line    = "gunicorn -k uvicorn.workers.UvicornWorker -w 1 -b 0.0.0.0:8000 --timeout 120 app.principal:app"
    application_stack {
      python_version = "3.12"
    }
  }

  app_settings = merge({
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
    WEBSITES_PORT                  = "8000"
    LOG_ANALYTICS_WORKSPACE_ID     = azurerm_log_analytics_workspace.logs.workspace_id
    EVALUACIONES_TABLA_URL         = azurerm_storage_account.nucleo.primary_table_endpoint
    NEGOCIO_TABLA_URL              = azurerm_storage_account.nucleo.primary_table_endpoint
    REINTENTOS_TABLA_URL           = azurerm_storage_account.nucleo.primary_table_endpoint
    # Costo de IA: tokens de todas las llamadas a Azure OpenAI (producción, pruebas y mediciones) desde las métricas de la cuenta.
    OPENAI_RECURSO_ID = azurerm_cognitive_account.openai.id
    # Costo real: lo que Azure cobró en la suscripción (Cost Management), por servicio y período.
    AZ_SUSCRIPCION_ID = data.azurerm_client_config.actual.subscription_id
    FRONT_AUTH                     = "clave"
    FRONT_CLAVE                    = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault.kv.vault_uri}secrets/front-clave-panel/)"
    # Demo «Denuncias»: el panel es un cliente del núcleo con su cuenta propia (ver secretos.tf).
    DEMO_CLIENT_ID     = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault.kv.vault_uri}secrets/${azurerm_key_vault_secret.demo_client_id.name}/)"
    DEMO_CLIENT_SECRET = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault.kv.vault_uri}secrets/${azurerm_key_vault_secret.demo_client_secret.name}/)"
    }, var.crear_nucleo ? {
    KERNA_NUCLEO_URL = "https://${azurerm_container_app.nucleo[0].ingress[0].fqdn}"
  } : {})

  lifecycle {
    ignore_changes = [app_settings["WEBSITE_RUN_FROM_PACKAGE"]]
  }
}

resource "azurerm_role_assignment" "front_logs" {
  count                = var.crear_front ? 1 : 0
  scope                = azurerm_log_analytics_workspace.logs.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = azurerm_linux_web_app.front[0].identity[0].principal_id
}

resource "azurerm_role_assignment" "front_evaluaciones" {
  count                = var.crear_front ? 1 : 0
  scope                = "${azurerm_storage_account.nucleo.id}/tableServices/default/tables/${azapi_resource.tabla_evaluaciones.name}"
  role_definition_name = "Storage Table Data Reader"
  principal_id         = azurerm_linux_web_app.front[0].identity[0].principal_id
}

resource "azurerm_role_assignment" "front_metricas_openai" {
  count                = var.crear_front ? 1 : 0
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Monitoring Reader"
  principal_id         = azurerm_linux_web_app.front[0].identity[0].principal_id
}

resource "azurerm_role_assignment" "front_costos" {
  count                = var.crear_front ? 1 : 0
  scope                = "/subscriptions/${data.azurerm_client_config.actual.subscription_id}"
  role_definition_name = "Cost Management Reader"
  principal_id         = azurerm_linux_web_app.front[0].identity[0].principal_id
}

resource "azurerm_role_assignment" "front_kv" {
  count                = var.crear_front ? 1 : 0
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_web_app.front[0].identity[0].principal_id
}

output "front_url" {
  value = var.crear_front ? "https://${azurerm_linux_web_app.front[0].default_hostname}" : null
}

output "front_nombre" {
  value = var.crear_front ? azurerm_linux_web_app.front[0].name : null
}
