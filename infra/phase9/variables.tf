variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
  nullable    = false
}

variable "location" {
  description = "AKS lab region."
  type        = string
  default     = "westus3"
}

variable "existing_resource_group_name" {
  description = "Existing application resource group reused by the temporary cluster."
  type        = string
  default     = "rg-arp-app-wus3"
}

variable "existing_registry_name" {
  description = "Existing ACR reused for immutable application images."
  type        = string
  default     = "arp3e6c8737fb3a44be8477"
}

variable "aks_operator_object_id" {
  description = "Microsoft Entra object ID receiving temporary AKS RBAC cluster-admin access."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9a-fA-F-]{36}$", var.aks_operator_object_id))
    error_message = "Provide the operator Microsoft Entra object ID as a UUID."
  }
}

variable "kubernetes_version" {
  description = "Supported AKS Kubernetes version selected at the cost gate."
  type        = string
  default     = "1.35"

  validation {
    condition     = can(regex("^1\\.[0-9]{2}$", var.kubernetes_version))
    error_message = "Use a supported AKS major.minor version such as 1.35."
  }
}

variable "system_node_vm_size" {
  description = "Single system-node VM SKU for the temporary lab."
  type        = string
  default     = "Standard_D2as_v5"
}
