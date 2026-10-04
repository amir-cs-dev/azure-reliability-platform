output "resource_group_name" {
  description = "Application resource group."
  value       = azurerm_resource_group.app.name
}

output "registry_name" {
  description = "Azure Container Registry name."
  value       = azurerm_container_registry.app.name
}

output "registry_login_server" {
  description = "Registry hostname used for Docker pushes."
  value       = azurerm_container_registry.app.login_server
}

output "managed_identity_principal_id" {
  description = "Principal used for registry image pulls."
  value       = azurerm_user_assigned_identity.app.principal_id
}

output "container_app_name" {
  description = "Deployed Container App name."
  value = (
    length(azurerm_container_app.app) > 0
    ? azurerm_container_app.app[0].name
    : null
  )
}

output "application_url" {
  description = "Public HTTPS URL after application deployment."
  value = (
    length(azurerm_container_app.app) > 0
    ? "https://${azurerm_container_app.app[0].ingress[0].fqdn}"
    : null
  )
}

output "application_insights_name" {
  value       = azurerm_application_insights.app.name
  description = "Application Insights resource for request telemetry."
}

output "reliability_workbook_id" {
  value       = azurerm_application_insights_workbook.reliability.id
  description = "Azure Monitor Workbook ID."
}

output "function_app_name" {
  value       = azurerm_function_app_flex_consumption.monitor.name
  description = "Timer-triggered reliability monitor Function App."
}

output "function_service_plan_name" {
  value       = azurerm_service_plan.function.name
  description = "Flex Consumption hosting plan for the monitor Function."
}

output "function_storage_account_name" {
  value       = azurerm_storage_account.function.name
  description = "Managed-identity-only host and deployment storage for the Function."
}

output "function_key_vault_name" {
  value       = azurerm_key_vault.function.name
  description = "Vault containing Function runtime secret values populated out of band."
}

output "function_managed_identity_name" {
  value       = azurerm_user_assigned_identity.function.name
  description = "User-assigned identity used for Function storage access."
}
