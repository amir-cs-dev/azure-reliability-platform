resource "azurerm_container_app" "app" {
  count = var.image_tag == "" ? 0 : 1

  name                         = "ca-arp-api-wus3"
  resource_group_name          = azurerm_resource_group.app.name
  container_app_environment_id = azurerm_container_app_environment.app.id
  workload_profile_name        = "Consumption"

  revision_mode = "Single"

  identity {
    type = "UserAssigned"

    identity_ids = [
      azurerm_user_assigned_identity.app.id
    ]
  }

  registry {
    server   = azurerm_container_registry.app.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  ingress {
    external_enabled           = true
    target_port                = 8000
    allow_insecure_connections = false

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name = "fastapi"

      image = "${azurerm_container_registry.app.login_server}/reliability-api:${var.image_tag}"

      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.app.connection_string
      }

      env {
        name  = "APP_VERSION"
        value = var.image_tag
      }

      cpu    = 0.25
      memory = "0.5Gi"

      startup_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/health"
        interval_seconds        = 5
        timeout                 = 3
        failure_count_threshold = 12
      }

      liveness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/health"
        interval_seconds        = 20
        timeout                 = 3
        failure_count_threshold = 3
      }

      readiness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/health"
        interval_seconds        = 10
        timeout                 = 3
        failure_count_threshold = 3
      }
    }
  }

  tags = local.tags

  depends_on = [
    azurerm_role_assignment.acr_pull
  ]
}