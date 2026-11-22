# Correo propio del panel de Kerna (avisos de cuentas): Azure Communication Services Email con dominio administrado por Azure.
# El front envía con la cadena de conexión (secreto correo-acs-conexion) desde DoNotReply@<dominio>.azurecomm.net.
# Sin registro de aplicación en Entra ni servidor SMTP propio (Azure bloquea el puerto 25 de salida).

resource "azurerm_email_communication_service" "correo" {
  name                = "ecs-${local.base}-${local.sufijo}"
  resource_group_name = azurerm_resource_group.rg.name
  data_location       = "United States"
  tags                = local.etiquetas
}

resource "azurerm_email_communication_service_domain" "correo" {
  name                             = "AzureManagedDomain"
  email_service_id                 = azurerm_email_communication_service.correo.id
  domain_management                = "AzureManaged"
  user_engagement_tracking_enabled = false
  tags                             = local.etiquetas
}

resource "azurerm_communication_service" "correo" {
  name                = "acs-${local.base}-${local.sufijo}"
  resource_group_name = azurerm_resource_group.rg.name
  data_location       = "United States"
  tags                = local.etiquetas
}

resource "azurerm_communication_service_email_domain_association" "correo" {
  communication_service_id = azurerm_communication_service.correo.id
  email_service_domain_id  = azurerm_email_communication_service_domain.correo.id
}

resource "azurerm_key_vault_secret" "correo_acs_conexion" {
  name         = "correo-acs-conexion"
  value        = azurerm_communication_service.correo.primary_connection_string
  key_vault_id = azurerm_key_vault.kv.id
}

output "correo_remitente" {
  value = "DoNotReply@${azurerm_email_communication_service_domain.correo.from_sender_domain}"
}
