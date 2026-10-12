terraform {
  required_version = ">= 1.11" # atributos de solo escritura (postgres.tf)

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.42"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Estado remoto en la misma cuenta de Storage que Kerna, con otra clave
  # (veridy-dev.tfstate). Valores en backend.hcl (README, paso 2):
  #   terraform init -backend-config=backend.hcl
  backend "azurerm" {}
}

provider "azurerm" {
  subscription_id = var.subscription_id

  features {
    key_vault {
      # Nunca purgar secretos al destruir: quedan recuperables (soft delete).
      purge_soft_delete_on_destroy = false
    }
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }
}
