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

locals {
  project = "azure-reliability-platform"

  registry_name = "arp${substr(replace(var.subscription_id, "-", ""), 0, 20)}"

  tags = {
    project     = local.project
    environment = "lab"
    managed_by  = "terraform"
  }
}

resource "azurerm_resource_group" "app" {
  name     = "rg-arp-app-wus3"
  location = var.location

  tags = local.tags
}

resource "azurerm_container_registry" "app" {
  name                = local.registry_name
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location

  sku                  = "Basic"
  admin_enabled        = false
  role_assignment_mode = "LegacyRegistryPermissions"

  tags = local.tags
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "id-arp-app-wus3"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location

  tags = local.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.app.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id

  principal_type = "ServicePrincipal"

  skip_service_principal_aad_check = true
}

resource "azurerm_log_analytics_workspace" "app" {
  name                = "log-arp-app-wus3"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location

  sku               = "PerGB2018"
  retention_in_days = 30

  tags = local.tags
}

resource "azurerm_container_app_environment" "app" {
  name                = "cae-arp-wus3"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location

  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.app.id

  tags = local.tags

  lifecycle {
    ignore_changes = [
      workload_profile
    ]
  }
}