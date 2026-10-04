output "cluster_name" {
  description = "Temporary Phase 9 AKS cluster name."
  value       = azurerm_kubernetes_cluster.phase9.name
}

output "resource_group_name" {
  description = "Existing resource group containing the AKS control-plane resource."
  value       = data.azurerm_resource_group.app.name
}

output "node_resource_group_name" {
  description = "AKS-managed resource group destroyed with the cluster."
  value       = azurerm_kubernetes_cluster.phase9.node_resource_group
}

output "kubernetes_version" {
  description = "Provisioned Kubernetes version."
  value       = azurerm_kubernetes_cluster.phase9.kubernetes_version
}

output "kubelet_identity_object_id" {
  description = "Kubelet identity receiving ACR pull access."
  value       = azurerm_kubernetes_cluster.phase9.kubelet_identity[0].object_id
}

output "existing_registry_login_server" {
  description = "Existing ACR login server used by the Helm deployment."
  value       = data.azurerm_container_registry.app.login_server
}
