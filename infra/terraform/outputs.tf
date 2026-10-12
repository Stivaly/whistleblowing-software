output "grupo_recursos" {
  value = azurerm_resource_group.rg.name
}

output "acr_nombre" {
  value = azurerm_container_registry.acr.name
}

output "acr_servidor" {
  value = azurerm_container_registry.acr.login_server
}

output "imagen" {
  value = local.imagen
}

output "key_vault_nombre" {
  value = azurerm_key_vault.kv.name
}

output "jobs" {
  value = [for j in azurerm_container_app_job.pipeline : j.name]
}

output "repositorio_pipeline" {
  value = "${azurerm_container_registry.acr.login_server}/kerna-pipeline"
}

output "postgres_servidor" {
  value = var.crear_postgres ? azurerm_postgresql_flexible_server.veridy[0].fqdn : null
}

output "postgres_base" {
  value = var.crear_postgres ? azurerm_postgresql_flexible_server_database.veridy[0].name : null
}

output "postgres_admin" {
  value = var.crear_postgres ? var.postgres_admin_login : null
}
