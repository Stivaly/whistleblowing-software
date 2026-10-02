locals {
  base      = "${var.prefijo}-${var.ambiente}"
  sufijo    = random_string.sufijo.result
  imagen    = "${azurerm_container_registry.acr.login_server}/kerna-pipeline:${var.imagen_tag}"
  etiquetas = merge(var.etiquetas, { ambiente = var.ambiente })

  # Nombre del secreto en Key Vault => variable de entorno del contenedor.
  # Los VALORES se cargan con az keyvault secret set (README, paso 6):
  # nunca pasan por Terraform ni quedan en su estado.
  secretos = {
    "mongodb-uri"    = "MONGODB_URI"
    "qdrant-url"     = "QDRANT_URL"
    "qdrant-api-key" = "QDRANT_API_KEY"
    "gemini-api-key" = "GEMINI_API_KEY"
  }

  jobs = {
    diario = {
      cron = var.cron_diario
      args = ["diario"]
    }
    semanal = {
      cron = var.cron_semanal
      args = ["semanal"]
    }
    vigencia-21719 = {
      cron = var.cron_vigencia_21719
      args = ["vigencia-21719"]
    }
  }
}

data "azurerm_client_config" "actual" {}

resource "random_string" "sufijo" {
  length  = 5
  special = false
  upper   = false
}

resource "azurerm_resource_group" "rg" {
  name     = "rg-${local.base}"
  location = var.region
  tags     = local.etiquetas
}

# ------------------------------------------------------------------ registros
resource "azurerm_log_analytics_workspace" "logs" {
  name                = "log-${local.base}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.5 # tope de gasto: el pipeline genera muy poco log
  tags                = local.etiquetas
}

# ------------------------------------------------------------------- imágenes
resource "azurerm_container_registry" "acr" {
  name                = "acr${var.prefijo}${var.ambiente}${local.sufijo}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  # Standard: 1 registro incluido gratis en Azure for Students (Basic se cobra).
  sku                 = "Standard"
  admin_enabled       = false
  tags                = local.etiquetas
}

# Permite a quien corre Terraform subir la imagen con docker push.
resource "azurerm_role_assignment" "yo_acr_push" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPush"
  principal_id         = data.azurerm_client_config.actual.object_id
}

# ------------------------------------------------------------------- secretos
resource "azurerm_key_vault" "kv" {
  name                       = "kv-${local.base}-${local.sufijo}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.actual.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 7
  purge_protection_enabled   = false
  tags                       = local.etiquetas
}

# Quien corre Terraform puede escribir los secretos (README, paso 6).
resource "azurerm_role_assignment" "yo_kv_secretos" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.actual.object_id
}

# --------------------------------------------------------- identidad del job
resource "azurerm_user_assigned_identity" "pipeline" {
  name                = "id-${local.base}-pipeline"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.etiquetas
}

resource "azurerm_role_assignment" "pipeline_acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.pipeline.principal_id
}

resource "azurerm_role_assignment" "pipeline_kv_lectura" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.pipeline.principal_id
}

# ------------------------------------------------------------------- entorno
resource "azurerm_container_app_environment" "env" {
  name                       = "cae-${local.base}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
  tags                       = local.etiquetas
}

# ---------------------------------------------------------------------- jobs
resource "azurerm_container_app_job" "pipeline" {
  for_each = var.crear_jobs ? local.jobs : {}

  name                         = "job-${local.base}-${each.key}"
  location                     = azurerm_resource_group.rg.location
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  replica_timeout_in_seconds   = 3600
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

  schedule_trigger_config {
    cron_expression          = each.value.cron
    parallelism              = 1
    replica_completion_count = 1
  }

  dynamic "secret" {
    for_each = local.secretos
    content {
      name                = secret.key
      key_vault_secret_id = "${azurerm_key_vault.kv.vault_uri}secrets/${secret.key}"
      identity            = azurerm_user_assigned_identity.pipeline.id
    }
  }

  template {
    container {
      name   = "pipeline"
      image  = local.imagen
      args   = each.value.args
      cpu    = 0.5
      memory = "1Gi"

      dynamic "env" {
        for_each = local.secretos
        content {
          name        = env.value
          secret_name = env.key
        }
      }
    }
  }

  # Terraform fija la imagen solo al crear el job. Las versiones nuevas las despliega
  # infra/scripts/subir_imagen.sh (az containerapp job update); sin esto, cada
  # terraform apply devolvería el job al tag inicial.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [
    azurerm_role_assignment.pipeline_acr_pull,
    azurerm_role_assignment.pipeline_kv_lectura,
  ]
}
