terraform {
  backend "azurerm" {
    container_name   = "tfstate"
    key              = "application.terraform.tfstate"
    use_azuread_auth = true
    use_cli          = true
  }
}