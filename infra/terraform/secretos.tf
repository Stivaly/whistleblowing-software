# Secretos propios de Kerna AI generados por Terraform: firma de los tokens del núcleo, token interno del
# servicio local y credencial del Conector Veridy. Los valores viven solo en Key Vault y en el estado
# remoto (privado); nunca en el repositorio. Para rotar uno: terraform apply -replace=random_password.<nombre>.

resource "random_password" "jwt" {
  length  = 64
  special = false
}

resource "random_password" "local_token" {
  length  = 48
  special = false
}

resource "random_password" "cliente_conector" {
  length  = 56
  special = false
}

# Cuenta propia del panel para la demo «Denuncias» (kerna/front/app/demo_denuncias.py): es un cliente más del núcleo, con su
# identificador y su clave. Va en KERNA_CLIENTES y no en la tabla `clientes`, así no aparece en Clientes ni en Negocio.
resource "random_password" "cliente_demo" {
  length  = 56
  special = false
}

locals {
  conector_client_id = "conector-veridy-${var.ambiente}"
  demo_client_id     = "demo-panel-${var.ambiente}"
}

variable "veridy_key_vault" {
  description = "Key Vault de Veridy donde el conector lee su credencial de la API de Kerna"
  type = object({
    nombre = string
    grupo  = string
  })
  default = {
    nombre = "kv-veridy-dev-kdicq"
    grupo  = "rg-veridy-dev"
  }
}

data "azurerm_key_vault" "veridy" {
  name                = var.veridy_key_vault.nombre
  resource_group_name = var.veridy_key_vault.grupo
}

resource "azurerm_key_vault_secret" "jwt" {
  name         = "kerna-jwt-secreto"
  value        = random_password.jwt.result
  key_vault_id = azurerm_key_vault.kv.id
}

resource "azurerm_key_vault_secret" "local_token" {
  name         = "kerna-local-token"
  value        = random_password.local_token.result
  key_vault_id = azurerm_key_vault.kv.id
}

# El núcleo solo conoce el sha256 del secreto del cliente.
resource "azurerm_key_vault_secret" "clientes" {
  name         = "kerna-clientes"
  key_vault_id = azurerm_key_vault.kv.id
  value = jsonencode({
    (local.conector_client_id) = {
      secreto_sha256 = sha256(random_password.cliente_conector.result)
      cliente        = "veridy-${var.ambiente}"
    }
    (local.demo_client_id) = {
      secreto_sha256 = sha256(random_password.cliente_demo.result)
      cliente        = "demo-panel"
    }
  })
}

resource "azurerm_key_vault_secret" "conector_client_id" {
  name         = "kerna-client-id"
  value        = local.conector_client_id
  key_vault_id = data.azurerm_key_vault.veridy.id
}

resource "azurerm_key_vault_secret" "conector_client_secret" {
  name         = "kerna-client-secret"
  value        = random_password.cliente_conector.result
  key_vault_id = data.azurerm_key_vault.veridy.id
}

# Credencial de la demo del panel: el front las lee con referencias de Key Vault (DEMO_CLIENT_ID y DEMO_CLIENT_SECRET en front.tf).
resource "azurerm_key_vault_secret" "demo_client_id" {
  name         = "demo-panel-client-id"
  value        = local.demo_client_id
  key_vault_id = azurerm_key_vault.kv.id
}

resource "azurerm_key_vault_secret" "demo_client_secret" {
  name         = "demo-panel-client-secret"
  value        = random_password.cliente_demo.result
  key_vault_id = azurerm_key_vault.kv.id
}
