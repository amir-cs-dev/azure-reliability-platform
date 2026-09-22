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
