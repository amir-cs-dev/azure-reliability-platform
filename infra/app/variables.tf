variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
  nullable    = false
}

variable "location" {
  description = "Deployment region."
  type        = string
  default     = "westus3"
}

variable "image_tag" {
  description = "Application image tag. Empty disables initial deployment."
  type        = string
  default     = ""

  validation {
    condition = (
      var.image_tag == "" ||
      can(regex("^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$", var.image_tag))
    )

    error_message = "Provide a valid container image tag."
  }
}

variable "key_vault_operator_object_id" {
  description = "Object ID allowed to populate the Function Key Vault without reading secrets into Terraform."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9a-fA-F-]{36}$", var.key_vault_operator_object_id))
    error_message = "Provide the operator Microsoft Entra object ID as a UUID."
  }
}

variable "monitor_target_url" {
  description = "External health endpoint checked by the timer-triggered Function."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^https://[^[:space:]]+/health$", var.monitor_target_url))
    error_message = "Provide an HTTPS health endpoint ending in /health."
  }
}

variable "function_schedule" {
  description = "Azure Functions NCRONTAB schedule for the reliability monitor."
  type        = string
  default     = "0 * * * * *"
  nullable    = false

  validation {
    condition     = length(trimspace(var.function_schedule)) > 0
    error_message = "The Function schedule must not be empty."
  }
}

variable "function_failure_threshold" {
  description = "Consecutive unhealthy checks required to open an incident."
  type        = number
  default     = 2
  nullable    = false

  validation {
    condition     = var.function_failure_threshold >= 1 && floor(var.function_failure_threshold) == var.function_failure_threshold
    error_message = "The Function failure threshold must be a positive integer."
  }
}
