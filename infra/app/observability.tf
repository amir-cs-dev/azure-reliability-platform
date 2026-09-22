resource "azurerm_application_insights" "app" {
  name                = "appi-arp-app-wus3"
  location            = azurerm_resource_group.app.location
  resource_group_name = azurerm_resource_group.app.name
  workspace_id        = azurerm_log_analytics_workspace.app.id
  application_type    = "web"
  tags                = local.tags
}

resource "azurerm_application_insights_workbook" "reliability" {
  name                = "2b08e0e4-62b8-46eb-b479-6f96ddbb75c5"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location
  display_name        = "ARP reliability and incident investigation"
  data_json           = replace(file("${path.module}/../../docs/observability/workbook.json"), "__ARP_LOG_WORKSPACE_ID__", azurerm_log_analytics_workspace.app.id)
  tags                = local.tags
}
