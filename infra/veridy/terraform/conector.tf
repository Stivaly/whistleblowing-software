# --------------------------------------------------------------------------
# Conector Veridy (Kerna): contenedor `conector` dentro del grupo de Veridy.
#
# El bloque `dynamic "container"` está en main.tf (un contenedor solo puede ir dentro del
# grupo); aquí están sus variables, su definición y su base de datos de estado.
#
# - Habla con Veridy dentro del grupo: Veridy solo responde en su nombre público (si el Host
#   es una IP redirige a https://<hostname> y el certificado es del nombre público), así que
#   usa https://<fqdn>:8443 y entrada.py hace que ese nombre resuelva a 127.0.0.1 en su proceso.
# - Los secretos los lee entrada.py de Key Vault con la identidad del grupo; no van en las
#   variables de entorno del grupo. Los cuatro: veridy-kerna-conector-password, kerna-client-id,
#   kerna-client-secret (infra/terraform/secretos.tf) y conector-pg-password, que se genera aquí.
# - Estado en la base `kerna_conector` del PostgreSQL de Veridy, con el rol `kerna_conector`
#   (infra/sql/conector_roles.sql), sin acceso a la base `veridy`.
# --------------------------------------------------------------------------

variable "crear_conector" {
  description = "true agrega el contenedor `conector` al grupo de Veridy (recrea el grupo) y crea su base de estado"
  type        = bool
  default     = false
}

variable "conector_tag" {
  description = "Tag de la imagen kerna-conector del registro"
  type        = string
  default     = "latest"
}

variable "kerna_api_url" {
  description = "URL del núcleo de Kerna (terraform -chdir=infra/terraform output -raw nucleo_url)"
  type        = string
  default     = ""

  validation {
    condition     = !var.crear_conector || startswith(var.kerna_api_url, "https://")
    error_message = "Con crear_conector = true hay que indicar kerna_api_url (https://...)."
  }
}

variable "kerna_id_empresa" {
  type    = string
  default = "veridy"
}

variable "conector_intervalo_s" {
  type    = number
  default = 30
}

locals {
  veridy_fqdn = "${local.base}-${local.sufijo}.${var.region}.azurecontainer.io" # = fqdn del grupo

  conector = var.crear_conector ? {
    imagen = "${data.azurerm_container_registry.acr.login_server}/kerna-conector:${var.conector_tag}"
    entorno = {
      AZURE_CLIENT_ID       = azurerm_user_assigned_identity.veridy.client_id
      VERIDY_KV_URL         = azurerm_key_vault.kv.vault_uri
      VERIDY_PG_FQDN        = local.pg_fqdn
      VERIDY_URL            = "https://${local.veridy_fqdn}:8443"
      VERIDY_RESOLVER_LOCAL = local.veridy_fqdn
      VERIDY_USUARIO        = "kerna-conector"
      KERNA_API_URL         = var.kerna_api_url
      KERNA_ID_EMPRESA      = var.kerna_id_empresa
      CONECTOR_INTERVALO_S  = tostring(var.conector_intervalo_s)
    }
  } : null
}

resource "azurerm_postgresql_flexible_server_database" "kerna_conector" {
  count = var.crear_conector ? 1 : 0

  name      = "kerna_conector"
  server_id = azurerm_postgresql_flexible_server.veridy.id
  charset   = "UTF8"
  collation = "en_US.utf8"

  lifecycle {
    prevent_destroy = true
  }
}

# Clave del rol `kerna_conector` de PostgreSQL: generada aquí y guardada en Key Vault.
resource "random_password" "conector_pg" {
  count   = var.crear_conector ? 1 : 0
  length  = 40
  special = false
}

resource "azurerm_key_vault_secret" "conector_pg" {
  count        = var.crear_conector ? 1 : 0
  name         = "conector-pg-password"
  value        = random_password.conector_pg[0].result
  key_vault_id = azurerm_key_vault.kv.id
}
