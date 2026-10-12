locals {
  base      = "veridy-${var.ambiente}"
  sufijo    = random_string.sufijo.result
  etiquetas = merge(var.etiquetas, { ambiente = var.ambiente })

  imagen       = "${data.azurerm_container_registry.acr.login_server}/veridy:${var.imagen_tag}"
  imagen_socat = "${data.azurerm_container_registry.acr.login_server}/socat:1.8"
  nombre_grupo = "aci-${local.base}"
  grupo_id     = "${azurerm_resource_group.rg.id}/providers/Microsoft.ContainerInstance/containerGroups/${local.nombre_grupo}"
  pg_fqdn      = azurerm_postgresql_flexible_server.veridy.fqdn
  scripts      = { for f in ["arranque.py", "vigia.py"] : f => filebase64("${path.module}/../contenedor/${f}") }
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

# ------------------------------------------------------------------- secretos
# veridy-db-admin-password y veridy-db-app-password. Los VALORES se cargan con
# az keyvault secret set (README): nunca pasan por Terraform ni quedan en su estado.
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

resource "azurerm_role_assignment" "yo_kv_secretos" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.actual.object_id
}

# --------------------------------------------------------------- almacenamiento
# Adjuntos y archivos de Veridy (persisten entre encendidos) y la carpeta de
# control del vigía (veridy.sh mantener). Los logs NO se guardan aquí: viven en
# memoria del grupo y se pierden al apagarlo, así no se conservan IPs.
resource "azurerm_storage_account" "st" {
  name                            = "stveridy${var.ambiente}${local.sufijo}"
  location                        = azurerm_resource_group.rg.location
  resource_group_name             = azurerm_resource_group.rg.name
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  tags                            = local.etiquetas
}

resource "azurerm_storage_share" "share" {
  for_each = { adjuntos = 10, archivos = 1, control = 1 } # cuota en GB

  name               = each.key
  storage_account_id = azurerm_storage_account.st.id
  quota              = each.value
}

# ------------------------------------------------------------------- identidad
# La usan el contenedor de arranque (lee el secreto, abre el firewall) y el vigía
# (apaga PostgreSQL y el grupo). Permisos mínimos con un rol propio.
resource "azurerm_user_assigned_identity" "veridy" {
  name                = "id-${local.base}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.etiquetas
}

resource "azurerm_role_assignment" "veridy_kv_lectura" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.veridy.principal_id
}

data "azurerm_container_registry" "acr" {
  name                = var.acr_nombre
  resource_group_name = var.acr_grupo
}

resource "azurerm_role_assignment" "veridy_acr_pull" {
  scope                = data.azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.veridy.principal_id
}

resource "azurerm_role_definition" "encendido" {
  name        = "Veridy ${var.ambiente}: apagar y autorizar firewall"
  scope       = azurerm_resource_group.rg.id
  description = "Lo que necesita el grupo de Veridy: apagarse a sí mismo y a su PostgreSQL, y autorizar su IP de salida."

  permissions {
    actions = [
      "Microsoft.ContainerInstance/containerGroups/read",
      "Microsoft.ContainerInstance/containerGroups/stop/action",
      "Microsoft.DBforPostgreSQL/flexibleServers/read",
      "Microsoft.DBforPostgreSQL/flexibleServers/stop/action",
      "Microsoft.DBforPostgreSQL/flexibleServers/firewallRules/read",
      "Microsoft.DBforPostgreSQL/flexibleServers/firewallRules/write",
    ]
  }

  assignable_scopes = [azurerm_resource_group.rg.id]
}

resource "azurerm_role_assignment" "veridy_encendido" {
  scope              = azurerm_resource_group.rg.id
  role_definition_id = azurerm_role_definition.encendido.role_definition_resource_id
  principal_id       = azurerm_user_assigned_identity.veridy.principal_id
}

# ---------------------------------------------------------- grupo de contenedores
# arranque (init) -> veridy + puertos (443->8443, 80->8080 sin abrir el TLS) + vigía.
resource "azurerm_container_group" "veridy" {
  count = var.crear_contenedor ? 1 : 0

  name                = local.nombre_grupo
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "${local.base}-${local.sufijo}"
  restart_policy      = "Always"
  tags                = local.etiquetas

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.veridy.id]
  }

  image_registry_credential {
    server                    = data.azurerm_container_registry.acr.login_server
    user_assigned_identity_id = azurerm_user_assigned_identity.veridy.id
  }

  exposed_port {
    port     = 80
    protocol = "TCP"
  }

  exposed_port {
    port     = 443
    protocol = "TCP"
  }

  init_container {
    name     = "arranque"
    image    = local.imagen
    commands = ["python3", "/opt/veridy/arranque.py"]

    environment_variables = {
      AZURE_CLIENT_ID = azurerm_user_assigned_identity.veridy.client_id
      VERIDY_KV_URL   = azurerm_key_vault.kv.vault_uri
      VERIDY_PG_FQDN  = local.pg_fqdn
      VERIDY_PG_ID    = azurerm_postgresql_flexible_server.veridy.id
    }

    volume {
      name       = "scripts"
      mount_path = "/opt/veridy"
      read_only  = true
      secret     = local.scripts
    }

    volume {
      name       = "pgpass"
      mount_path = "/run/veridy"
      empty_dir  = true
    }
  }

  container {
    name   = "veridy"
    image  = local.imagen
    cpu    = var.cpu
    memory = var.memoria_gb

    ports {
      port     = 8080
      protocol = "TCP"
    }

    ports {
      port     = 8443
      protocol = "TCP"
    }

    environment_variables = {
      GLOBALEAKS_DB_URI = "postgresql+psycopg2://veridy_app@${local.pg_fqdn}:5432/veridy?sslmode=verify-full&sslrootcert=system"
      PGPASSFILE        = "/run/veridy/pgpass"
    }

    volume {
      name       = "pgpass"
      mount_path = "/run/veridy"
      empty_dir  = true
    }

    volume {
      name       = "logs"
      mount_path = "/var/globaleaks/log"
      empty_dir  = true
    }

    volume {
      name                 = "adjuntos"
      mount_path           = "/var/globaleaks/attachments"
      storage_account_name = azurerm_storage_account.st.name
      storage_account_key  = azurerm_storage_account.st.primary_access_key
      share_name           = azurerm_storage_share.share["adjuntos"].name
    }

    volume {
      name                 = "archivos"
      mount_path           = "/var/globaleaks/files"
      storage_account_name = azurerm_storage_account.st.name
      storage_account_key  = azurerm_storage_account.st.primary_access_key
      share_name           = azurerm_storage_share.share["archivos"].name
    }
  }

  container {
    name     = "puertos"
    image    = local.imagen_socat
    cpu      = 0.1
    memory   = 0.1
    commands = ["sh", "-c", "socat TCP-LISTEN:80,fork,reuseaddr TCP:127.0.0.1:8080 & exec socat TCP-LISTEN:443,fork,reuseaddr TCP:127.0.0.1:8443"]

    ports {
      port     = 80
      protocol = "TCP"
    }

    ports {
      port     = 443
      protocol = "TCP"
    }
  }

  container {
    name     = "vigia"
    image    = local.imagen
    cpu      = 0.1
    memory   = 0.2
    commands = ["python3", "/opt/veridy/vigia.py"]

    environment_variables = {
      AZURE_CLIENT_ID        = azurerm_user_assigned_identity.veridy.client_id
      VERIDY_GRUPO_ID        = local.grupo_id
      VERIDY_PG_ID           = azurerm_postgresql_flexible_server.veridy.id
      VERIDY_INACTIVIDAD_MIN = tostring(var.inactividad_min)
    }

    volume {
      name       = "scripts"
      mount_path = "/opt/veridy"
      read_only  = true
      secret     = local.scripts
    }

    volume {
      name       = "logs"
      mount_path = "/var/globaleaks/log"
      read_only  = true
      empty_dir  = true
    }

    volume {
      name                 = "control"
      mount_path           = "/control"
      read_only            = true
      storage_account_name = azurerm_storage_account.st.name
      storage_account_key  = azurerm_storage_account.st.primary_access_key
      share_name           = azurerm_storage_share.share["control"].name
    }
  }

  depends_on = [
    azurerm_role_assignment.veridy_acr_pull,
    azurerm_role_assignment.veridy_kv_lectura,
    azurerm_role_assignment.veridy_encendido,
  ]
}
