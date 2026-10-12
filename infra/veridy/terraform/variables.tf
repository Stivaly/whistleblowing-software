variable "subscription_id" {
  description = "ID de la suscripción Azure for Students (az account show --query id -o tsv)"
  type        = string
}

variable "region" {
  description = "Región de todos los recursos. chilecentral salvo que un servicio no esté disponible o salga caro ahí"
  type        = string
  default     = "chilecentral"
}

variable "ambiente" {
  description = "Ambiente (dev, prod)"
  type        = string
  default     = "dev"
}

variable "etiquetas" {
  type = map(string)
  default = {
    proyecto = "veridy"
    gestion  = "terraform"
  }
}

# ------------------------------------------------------------- imagen (Kerna)
# Veridy usa el Container Registry de Kerna: Azure for Students incluye un solo
# registro Standard sin costo.
variable "acr_nombre" {
  description = "Nombre del Container Registry (terraform -chdir=infra/terraform output -raw acr_nombre)"
  type        = string
}

variable "acr_grupo" {
  description = "Grupo de recursos del Container Registry"
  type        = string
  default     = "rg-kerna-dev"
}

variable "crear_contenedor" {
  description = <<-EOF
    false en la primera aplicación: crea grupo, Key Vault, almacenamiento e identidad.
    true cuando los secretos estén en Key Vault y la imagen en el registro.
  EOF
  type        = bool
  default     = false
}

variable "imagen_tag" {
  description = "Tag de la imagen veridy con que se crea el contenedor"
  type        = string
  default     = "v1"
}

variable "cpu" {
  description = "vCPU del contenedor de Veridy"
  type        = number
  default     = 1
}

variable "memoria_gb" {
  description = "Memoria del contenedor de Veridy"
  type        = number
  default     = 1.5
}

variable "inactividad_min" {
  description = "Minutos sin uso tras los que el vigía apaga Veridy y PostgreSQL"
  type        = number
  default     = 60
}

# ------------------------------------------------------------------ PostgreSQL
variable "postgres_admin_login" {
  description = "Usuario administrador del servidor PostgreSQL"
  type        = string
  default     = "veridyadmin"
}

variable "postgres_admin_password" {
  description = <<-EOT
    Contraseña del administrador. Se pasa con TF_VAR_postgres_admin_password leyéndola
    de Key Vault (README). Es de solo escritura: no queda en el estado.
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
  description = <<-EOT
    Nombre de la regla => IPv4 pública que puede conectarse a PostgreSQL además del contenedor
    (por ejemplo, la máquina de administración). El contenedor se autoriza solo al arrancar.
  EOT
  type        = map(string)
  default     = {}
}

variable "postgres_nombre" {
  description = "Nombre del servidor PostgreSQL (ya existe: se importó, no se recrea)"
  type        = string
}
