terraform {
  required_version = ">= 1.11"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.42"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    # Entorno de Container Apps con environmentMode explícito (azurerm aún no lo expone).
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.13"
    }
  }

  # Estado remoto en Azure Storage. Valores en backend.hcl (ver README.md, paso 4):
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
