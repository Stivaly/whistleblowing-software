# Ping al front cada 15 min para que el App Service F1 (se duerme a los ~20 min sin visitas) no quede frío.
# Elegido: Logic App de consumo (recurrencia + 2 acciones HTTP GET en paralelo). Sin código, sin almacenamiento, sin claves,
# solo se paga por ejecución (~0,2 USD/mes: 96 corridas/día x 2 acciones). Alternativas descartadas:
# Azure Function con temporizador (exige cuenta de almacenamiento y desplegar código) y Container Apps Job
# (exige entorno e imagen). Las URLs son públicas (/salud y /), no llevan credenciales.

resource "azurerm_logic_app_workflow" "ping_front" {
  count               = var.crear_front ? 1 : 0
  name                = "logic-${local.base}-ping-front"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.etiquetas
}

resource "azurerm_logic_app_trigger_recurrence" "ping_front" {
  count        = var.crear_front ? 1 : 0
  name         = "cada-15-min"
  logic_app_id = azurerm_logic_app_workflow.ping_front[0].id
  frequency    = "Minute"
  interval     = 15
}

resource "azurerm_logic_app_action_http" "ping_salud" {
  count        = var.crear_front ? 1 : 0
  name         = "get-salud"
  logic_app_id = azurerm_logic_app_workflow.ping_front[0].id
  method       = "GET"
  uri          = "https://${azurerm_linux_web_app.front[0].default_hostname}/salud"
}

resource "azurerm_logic_app_action_http" "ping_portada" {
  count        = var.crear_front ? 1 : 0
  name         = "get-portada"
  logic_app_id = azurerm_logic_app_workflow.ping_front[0].id
  method       = "GET"
  uri          = "https://${azurerm_linux_web_app.front[0].default_hostname}/"
}

output "ping_front_nombre" {
  value = var.crear_front ? azurerm_logic_app_workflow.ping_front[0].name : null
}
