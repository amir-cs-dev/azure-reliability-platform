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