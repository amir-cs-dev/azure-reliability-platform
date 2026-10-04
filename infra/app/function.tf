locals {
  function_suffix       = substr(replace(var.subscription_id, "-", ""), 0, 8)
  function_name         = "func-arp-monitor-${local.function_suffix}-wus3"
  function_storage_name = "starpfn${substr(replace(var.subscription_id, "-", ""), 0, 16)}"
  function_vault_name   = "kv-arp-fn-${local.function_suffix}"
}

data "azurerm_client_config" "current" {}

resource "azurerm_user_assigned_identity" "function" {
  name                = "id-arp-function-wus3"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location

  tags = local.tags
}

resource "azurerm_storage_account" "function" {
  name                = local.function_storage_name
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location

  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  access_tier              = "Hot"

  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  allow_nested_items_to_be_public = false

  tags = local.tags
}

resource "azurerm_storage_container" "function_releases" {
  name                  = "function-releases"
  storage_account_id    = azurerm_storage_account.function.id
  container_access_type = "private"
}

resource "azurerm_role_assignment" "function_storage" {
  scope                = azurerm_storage_account.function.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_user_assigned_identity.function.principal_id
  principal_type       = "ServicePrincipal"

  skip_service_principal_aad_check = true
}

resource "azurerm_key_vault" "function" {
  name                = local.function_vault_name
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location
  tenant_id           = data.azurerm_client_config.current.tenant_id

  sku_name                        = "standard"
  rbac_authorization_enabled      = false
  soft_delete_retention_days      = 7
  purge_protection_enabled        = false
  public_network_access_enabled   = true
  enabled_for_template_deployment = false

  network_acls {
    bypass         = "AzureServices"
    default_action = "Allow"
  }

  tags = local.tags
}

resource "azurerm_key_vault_access_policy" "operator" {
  key_vault_id = azurerm_key_vault.function.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = var.key_vault_operator_object_id

  secret_permissions = [
    "Get",
    "List",
    "Set",
  ]
}

resource "azurerm_service_plan" "function" {
  name                = "asp-arp-function-wus3"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location

  os_type  = "Linux"
  sku_name = "FC1"

  tags = local.tags
}

resource "azurerm_function_app_flex_consumption" "monitor" {
  name                = local.function_name
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location
  service_plan_id     = azurerm_service_plan.function.id

  storage_container_type            = "blobContainer"
  storage_container_endpoint        = "${azurerm_storage_account.function.primary_blob_endpoint}${azurerm_storage_container.function_releases.name}"
  storage_authentication_type       = "UserAssignedIdentity"
  storage_user_assigned_identity_id = azurerm_user_assigned_identity.function.id

  runtime_name    = "python"
  runtime_version = "3.12"

  maximum_instance_count = 1
  instance_memory_in_mb  = 512

  https_only                    = true
  public_network_access_enabled = true

  identity {
    type = "SystemAssigned, UserAssigned"

    identity_ids = [
      azurerm_user_assigned_identity.function.id,
    ]
  }

  app_settings = {
    AzureWebJobsStorage__accountName = azurerm_storage_account.function.name
    AzureWebJobsStorage__credential  = "managedidentity"
    AzureWebJobsStorage__clientId    = azurerm_user_assigned_identity.function.client_id

    MONITOR_SCHEDULE  = var.function_schedule
    FAILURE_THRESHOLD = tostring(var.function_failure_threshold)
    TARGET_URL        = var.monitor_target_url

    DATABASE_URL = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.function.name};SecretName=database-url)"
    WEBHOOK_URL  = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.function.name};SecretName=webhook-url)"
  }

  site_config {
    application_insights_connection_string = azurerm_application_insights.app.connection_string
    http2_enabled                          = true
    minimum_tls_version                    = "1.2"
    scm_minimum_tls_version                = "1.2"
  }

  # AzureRM 5.6.0 writes a legacy key-based setting with an empty AccountKey
  # during Flex creation even when shared keys are disabled and the supported
  # identity-based AzureWebJobsStorage__* settings are configured above. The
  # empty legacy setting prevents neither identity use nor deployment, but it
  # is unnecessary and is removed after creation. Ignore only that provider-
  # generated key so subsequent plans do not restore it.
  lifecycle {
    ignore_changes = [app_settings["AzureWebJobsStorage"]]
  }

  tags = local.tags

  depends_on = [
    azurerm_role_assignment.function_storage,
  ]
}

resource "azurerm_key_vault_access_policy" "function" {
  key_vault_id = azurerm_key_vault.function.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_function_app_flex_consumption.monitor.identity[0].principal_id

  secret_permissions = [
    "Get",
    "List",
  ]
}
