# --------------------------------------------------------------------------
# Base de datos operativa de Veridy: Azure Database for PostgreSQL (Flexible Server)
#
# Se creó primero desde infra/terraform (Kerna) y se trasladó aquí el 2026-10-12:
# se movió de grupo de recursos e importó al estado de Veridy, sin recrearlo.
# La contraseña del administrador se genera fuera de Terraform, se guarda en
# Key Vault y entra como atributo de solo escritura: nunca queda en el estado.
#
# Se apaga solo (vigía del grupo de contenedores) y se enciende con veridy.sh.
#
# Roles dentro de la base (infra/sql/veridy_roles.sql):
#   veridyadmin  administrador del servidor; solo para crear o actualizar el esquema
#   veridy_app   rol de la aplicación: lectura y escritura, sin DDL
# --------------------------------------------------------------------------

resource "azurerm_postgresql_flexible_server" "veridy" {
  name                = var.postgres_nombre
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  version             = "16"

  # Burstable B1ms: la capa más pequeña.
  sku_name          = "B_Standard_B1ms"
  storage_mb        = 32768
  storage_tier      = "P4"
  auto_grow_enabled = false

  backup_retention_days        = 7
  geo_redundant_backup_enabled = false

  # Acceso público restringido por firewall (reglas abajo) y TLS obligatorio.
  public_network_access_enabled = true

  administrator_login               = var.postgres_admin_login
  administrator_password_wo         = var.postgres_admin_password
  administrator_password_wo_version = var.postgres_admin_password_version

  authentication {
    password_auth_enabled         = true
    active_directory_auth_enabled = false
  }

  tags = local.etiquetas

  lifecycle {
    # Azure asigna la zona al crear; cambiarla después obliga a recrear.
    ignore_changes = [zone]
  }
}

resource "azurerm_postgresql_flexible_server_database" "veridy" {
  name      = "veridy"
  server_id = azurerm_postgresql_flexible_server.veridy.id
  charset   = "UTF8"
  collation = "en_US.utf8"

  lifecycle {
    # Evita que un cambio accidental destruya la base con sus datos.
    prevent_destroy = true
  }
}

# TLS 1.2 como mínimo y conexión cifrada obligatoria (valores por defecto,
# fijados aquí para que queden explícitos y auditables).
resource "azurerm_postgresql_flexible_server_configuration" "tls" {
  for_each = {
    require_secure_transport = "ON"
    ssl_min_protocol_version = "TLSv1.2"
  }

  name      = each.key
  server_id = azurerm_postgresql_flexible_server.veridy.id
  value     = each.value
}

# IPs de administración (postgres_ips_permitidas). La IP del contenedor la
# autoriza el propio grupo al arrancar (regla aci-veridy, fuera de Terraform).
resource "azurerm_postgresql_flexible_server_firewall_rule" "veridy" {
  for_each = var.postgres_ips_permitidas

  name             = each.key
  server_id        = azurerm_postgresql_flexible_server.veridy.id
  start_ip_address = each.value
  end_ip_address   = each.value
}
