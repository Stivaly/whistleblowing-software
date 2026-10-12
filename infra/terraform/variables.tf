variable "subscription_id" {
  description = "ID de la suscripción Azure for Students (az account show --query id -o tsv)"
  type        = string
}

variable "region" {
  description = "Región de todos los recursos. chilecentral salvo que un servicio no esté disponible o salga caro ahí"
  type        = string
  default     = "chilecentral"
}

variable "prefijo" {
  description = "Prefijo de nombres"
  type        = string
  default     = "kerna"
}

variable "ambiente" {
  description = "Ambiente (dev, prod)"
  type        = string
  default     = "dev"
}

variable "crear_jobs" {
  description = <<-EOT
    false en la primera aplicación: crea registro, Key Vault y entorno.
    true cuando los secretos ya estén en Key Vault y la imagen en el registro.
  EOT
  type        = bool
  default     = false
}

variable "imagen_tag" {
  description = "Tag de la imagen con que se CREAN los jobs. Las versiones siguientes se despliegan con infra/scripts/subir_imagen.sh"
  type        = string
  default     = "v1"
}

# Horarios en UTC (Container Apps no maneja zona horaria).
# Santiago: UTC-3 en horario de verano (sep-abr), UTC-4 en invierno.
variable "cron_diario" {
  description = "Extracción + embeddings diaria. 06:00 UTC = 03:00 Santiago en verano"
  type        = string
  default     = "0 6 * * *"
}

variable "cron_semanal" {
  description = "Verificación completa semanal (domingo)"
  type        = string
  default     = "0 7 * * 0"
}

variable "cron_vigencia_21719" {
  description = "1 de diciembre 00:05 Santiago (UTC-3) = 03:05 UTC: fin de la vigencia anticipada de la Ley 19.628 reformada"
  type        = string
  default     = "5 3 1 12 *"
}

variable "etiquetas" {
  type = map(string)
  default = {
    proyecto = "kerna-ai"
    gestion  = "terraform"
  }
}

# ------------------------------------------------------- PostgreSQL de Veridy
variable "crear_postgres" {
  description = <<-EOT
    true para crear el PostgreSQL Flexible Server de Veridy (README, paso 11).
    Antes: verificar que la capa B1ms esté cubierta por la suscripción.
  EOT
  type        = bool
  default     = false
}

variable "postgres_admin_login" {
  description = "Usuario administrador del servidor PostgreSQL"
  type        = string
  default     = "veridyadmin"
}

variable "postgres_admin_password" {
  description = <<-EOT
    Contraseña del administrador. Se pasa con TF_VAR_postgres_admin_password leyéndola
    de Key Vault (README, paso 11). Es de solo escritura: no queda en el estado.
  EOT
  type        = string
  sensitive   = true
  ephemeral   = true
  default     = null
}

variable "postgres_admin_password_version" {
  description = "Subir este número para que Terraform vuelva a enviar la contraseña (rotación)"
  type        = number
  default     = 1
}

variable "postgres_ips_permitidas" {
  description = "Nombre de la regla => IP pública de cada host que corre el contenedor de Veridy"
  type        = map(string)
  default     = {}
}
