# Observabilidad de Kerna AI: Workbook "Kerna AI: resultados" y alertas por correo sobre el workspace log-kerna-dev.
# Las consultas viven versionadas en kerna/docs/observabilidad/consultas/*.kql y se leen con file().
# Costo: el Workbook es gratuito; cada alerta de consulta programada cobra una evaluación por periodo (centavos al mes).

locals {
  dir_consultas = "${path.module}/../../kerna/docs/observabilidad/consultas"

  # Consultas del Workbook: archivo => título. "ago(7d)" se sustituye por el parámetro {Dias} del Workbook.
  consultas_workbook = [
    { archivo = "disponibilidad_efectiva", titulo = "Disponibilidad efectiva (con sugerencia / válidas)" },
    { archivo = "solicitudes_por_modo", titulo = "Solicitudes por modo y recuperación" },
    { archivo = "tasa_conmutacion", titulo = "Tasa de conmutación por día" },
    { archivo = "latencia_solicitud_p95", titulo = "Latencia de la solicitud (P50 y P95 por hora)" },
    { archivo = "latencia_por_etapa", titulo = "Latencia por etapa" },
    { archivo = "citas_y_json", titulo = "JSON válido y citas rechazadas" },
    { archivo = "tokens_por_solicitud", titulo = "Tokens por solicitud" },
    { archivo = "errores_por_proveedor", titulo = "Errores por proveedor" },
    { archivo = "jobs_pipeline", titulo = "Resultado de los jobs del pipeline" },
  ]

  workbook_items = concat(
    [
      {
        type = 1
        content = {
          json = "## Kerna AI: resultados\nSeñales del núcleo (Application Insights `appi-kerna-dev`) y de los jobs del pipeline. No contienen texto de denuncias: solo identificadores opacos, conteos, duraciones, códigos y nombres de modelo."
        }
      },
      {
        type = 9
        content = {
          version = "KqlParameterItem/1.0"
          parameters = [{
            id         = "d0a8f1c2-4b7e-4c55-9a51-6f0e0c3a1b01"
            version    = "KqlParameterItem/1.0"
            name       = "Dias"
            label      = "Ventana (días)"
            type       = 2
            isRequired = true
            value      = "7"
            jsonData = jsonencode([
              { value = "1", label = "1 día" },
              { value = "7", label = "7 días" },
              { value = "30", label = "30 días" },
            ])
            typeSettings = { additionalResourceOptions = [], showDefault = false }
          }]
          style                   = "pills"
          queryType               = 0
          resourceType            = "microsoft.operationalinsights/workspaces"
          crossComponentResources = [azurerm_log_analytics_workspace.logs.id]
        }
      },
    ],
    [for c in local.consultas_workbook : {
      type = 3
      content = {
        version                 = "KqlItem/1.0"
        title                   = c.titulo
        query                   = replace(file("${local.dir_consultas}/${c.archivo}.kql"), "ago(7d)", "ago({Dias}d)")
        size                    = 1
        queryType               = 0
        resourceType            = "microsoft.operationalinsights/workspaces"
        crossComponentResources = [azurerm_log_analytics_workspace.logs.id]
        visualization           = "table"
      }
    }]
  )
}

variable "correo_alertas" {
  description = "Correo que recibe las alertas. Va en terraform.tfvars (fuera de git). Vacío: no se crean grupo de acción ni alertas"
  type        = string
  default     = ""
  sensitive   = true
}

# ------------------------------------------------------------------- Workbook
resource "random_uuid" "workbook_resultados" {}

resource "azurerm_application_insights_workbook" "resultados" {
  name                = random_uuid.workbook_resultados.result # el nombre de un Workbook es un GUID
  display_name        = "Kerna AI: resultados"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  source_id           = lower(azurerm_application_insights.kerna.id)
  tags                = local.etiquetas

  data_json = jsonencode({
    version = "Notebook/1.0"
    items   = local.workbook_items
  })
}

# -------------------------------------------------------------------- alertas
locals {
  alertas_activas = nonsensitive(var.correo_alertas != "")

  # archivo => parámetros de la alerta. La ventana de cada alerta coincide con el ago() de su consulta.
  alertas = {
    job_fallido = {
      nombre      = "Kerna: ejecución fallida de un job del pipeline"
      descripcion = "Un job del pipeline o de la evaluación terminó con error o agotó sus reintentos."
      severidad   = 1
      frecuencia  = "PT15M"
      ventana     = "PT30M"
      silencio    = "PT2H"
    }
    p95_solicitud = {
      nombre      = "Kerna: P95 de la solicitud sobre 15 s"
      descripcion = "El P95 de la duración total de las solicitudes superó 15 s en la última hora."
      severidad   = 2
      frecuencia  = "PT30M"
      ventana     = "PT1H"
      silencio    = "PT6H"
    }
    conmutacion = {
      nombre      = "Kerna: tasa de conmutación sobre 10 %"
      descripcion = "Más del 10 % de las solicitudes de las últimas 6 h salió del camino oficial (modelo de respaldo, local o manual)."
      severidad   = 2
      frecuencia  = "PT1H"
      ventana     = "PT6H"
      silencio    = "PT6H"
    }
    cadena_agotada = {
      nombre      = "Kerna: revisión manual por cadena agotada"
      descripcion = "Una solicitud terminó en revision_manual porque fallaron todos los modelos de la cadena."
      severidad   = 1
      frecuencia  = "PT15M"
      ventana     = "PT30M"
      silencio    = "PT2H"
    }
  }
}

resource "azurerm_monitor_action_group" "kerna" {
  count = local.alertas_activas ? 1 : 0

  name                = "ag-${local.base}-alertas"
  resource_group_name = azurerm_resource_group.rg.name
  short_name          = "kerna-alerta"
  tags                = local.etiquetas

  email_receiver {
    name                    = "correo-alertas"
    email_address           = var.correo_alertas
    use_common_alert_schema = true
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "kerna" {
  for_each = local.alertas_activas ? local.alertas : {}

  name                 = "alerta-${local.base}-${replace(each.key, "_", "-")}"
  display_name         = each.value.nombre
  description          = each.value.descripcion
  resource_group_name  = azurerm_resource_group.rg.name
  location             = azurerm_resource_group.rg.location
  scopes               = [azurerm_log_analytics_workspace.logs.id]
  severity             = each.value.severidad
  evaluation_frequency = each.value.frecuencia
  window_duration      = each.value.ventana
  enabled              = true
  tags                 = local.etiquetas

  # Una alerta por evaluación con filas; el aviso no se repite durante el periodo de silencio.
  auto_mitigation_enabled           = false
  mute_actions_after_alert_duration = each.value.silencio

  criteria {
    query                   = file("${local.dir_consultas}/alerta_${each.key}.kql")
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.kerna[0].id]
  }
}

output "workbook_resultados" {
  value = azurerm_application_insights_workbook.resultados.id
}
