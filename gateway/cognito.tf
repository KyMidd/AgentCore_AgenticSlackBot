##
# Cognito User Pool for Gateway Authentication
##

resource "aws_cognito_user_pool" "gateway" {
  name = "${var.gateway_name}-${var.environment}"

  deletion_protection = "INACTIVE"
  mfa_configuration   = "OFF"

  password_policy {
    minimum_length    = 16
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
  }

  tags = {
    Name        = "${var.gateway_name}-${var.environment}"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

##
# Cognito Domain for OAuth Endpoints
##

resource "aws_cognito_user_pool_domain" "gateway" {
  domain       = lower("${var.gateway_name}-${var.environment}")
  user_pool_id = aws_cognito_user_pool.gateway.id
}

##
# Resource Server - Defines OAuth Scope
##

resource "aws_cognito_resource_server" "gateway" {
  identifier   = var.gateway_name
  name         = var.gateway_name
  user_pool_id = aws_cognito_user_pool.gateway.id

  scope {
    scope_name        = "invoke"
    scope_description = "Scope for invoking the ${var.gateway_name} AgentCore gateway"
  }
}

##
# App Client - Generates JWT Tokens
##

resource "aws_cognito_user_pool_client" "gateway" {
  name         = "${var.gateway_name}-client-${var.environment}"
  user_pool_id = aws_cognito_user_pool.gateway.id

  # OAuth 2.0 client credentials flow (machine-to-machine)
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes = [
    "${aws_cognito_resource_server.gateway.identifier}/invoke"
  ]

  # Token settings
  refresh_token_validity        = 30
  enable_token_revocation       = true
  prevent_user_existence_errors = "ENABLED"

  # Identity provider
  supported_identity_providers = ["COGNITO"]
}
