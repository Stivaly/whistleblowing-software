output "url" {
  description = "Dirección pública de Veridy"
  value       = var.crear_contenedor ? "https://${azurerm_container_group.veridy[0].fqdn}" : null
}

output "grupo_recursos" {
  value = azurerm_resource_group.rg.name
}

output "contenedor" {
  value = local.nombre_grupo
}

output "key_vault_nombre" {
  value = azurerm_key_vault.kv.name
}

output "storage_nombre" {
  value = azurerm_storage_account.st.name
}

output "postgres_servidor" {
  value = azurerm_postgresql_flexible_server.veridy.fqdn
}

output "postgres_nombre" {
  value = azurerm_postgresql_flexible_server.veridy.name
}

output "imagen" {
  value = local.imagen
}
