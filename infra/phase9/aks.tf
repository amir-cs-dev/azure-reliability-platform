resource "azurerm_kubernetes_cluster" "phase9" {
  name                = "aks-arp-phase9-wus3"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.app.name
  node_resource_group = "rg-arp-phase9-nodes-wus3"
  dns_prefix          = "aks-arp-phase9-wus3"

  kubernetes_version        = var.kubernetes_version
  sku_tier                  = "Free"
  support_plan              = "KubernetesOfficial"
  automatic_upgrade_channel = "patch"
  node_os_upgrade_channel   = "NodeImage"

  role_based_access_control_enabled = true
  local_account_disabled            = true
  oidc_issuer_enabled               = true
  workload_identity_enabled         = true

  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    tenant_id          = data.azurerm_client_config.current.tenant_id
  }

  node_provisioning_profile {
    mode = "Manual"
  }

  default_node_pool {
    name                 = "system"
    vm_size              = var.system_node_vm_size
    node_count           = 1
    auto_scaling_enabled = false
    max_pods             = 30

    type                         = "VirtualMachineScaleSets"
    os_disk_type                 = "Managed"
    os_disk_size_gb              = 30
    os_sku                       = "Ubuntu"
    only_critical_addons_enabled = false

    upgrade_settings {
      max_surge                     = "1"
      drain_timeout_in_minutes      = 15
      node_soak_duration_in_minutes = 0
    }

    tags = local.tags
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    network_policy      = "azure"
    load_balancer_sku   = "standard"
    outbound_type       = "loadBalancer"

    pod_cidr       = "10.244.0.0/16"
    service_cidr   = "10.240.0.0/16"
    dns_service_ip = "10.240.0.10"
  }

  azure_policy_enabled             = false
  http_application_routing_enabled = false
  open_service_mesh_enabled        = false

  tags = local.tags
}

resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                = data.azurerm_container_registry.app.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.phase9.kubelet_identity[0].object_id
  principal_type       = "ServicePrincipal"

  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "operator_cluster_admin" {
  scope                = azurerm_kubernetes_cluster.phase9.id
  role_definition_name = "Azure Kubernetes Service RBAC Cluster Admin"
  principal_id         = var.aks_operator_object_id
  principal_type       = "User"
}
