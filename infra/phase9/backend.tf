terraform {
  backend "azurerm" {
    container_name   = "tfstate"
    key              = "phase9.terraform.tfstate"
    use_azuread_auth = true
    use_cli          = true
  }
}
