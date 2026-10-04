terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.6.0"
    }
  }
}

provider "azurerm" {
  features {}

  subscription_id                 = var.subscription_id
  resource_provider_registrations = "none"
}

data "azurerm_client_config" "current" {}

data "azurerm_resource_group" "app" {
  name = var.existing_resource_group_name
}

data "azurerm_container_registry" "app" {
  name                = var.existing_registry_name
  resource_group_name = data.azurerm_resource_group.app.name
}

locals {
  tags = {
    project     = "azure-reliability-platform"
    environment = "phase9-lab"
    managed_by  = "terraform"
    teardown    = "required"
  }
}
