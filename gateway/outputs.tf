# Gateway Infrastructure Outputs

##
# Cognito Outputs
##

output "cognito_user_pool_id" {
  value       = aws_cognito_user_pool.gateway.id
  description = "Cognito user pool ID for gateway authentication"
}

output "cognito_user_pool_arn" {
  value       = aws_cognito_user_pool.gateway.arn
  description = "Cognito user pool ARN for IAM policy"
}

output "cognito_domain" {
  value       = aws_cognito_user_pool_domain.gateway.domain
  description = "Cognito domain for OAuth token endpoint"
}

output "cognito_client_id" {
  value       = aws_cognito_user_pool_client.gateway.id
  description = "Cognito app client ID"
}

output "cognito_client_secret" {
  value       = aws_cognito_user_pool_client.gateway.client_secret
  description = "Cognito app client secret (sensitive)"
  sensitive   = true
}

output "cognito_token_url" {
  value       = "https://${aws_cognito_user_pool_domain.gateway.domain}.auth.${data.aws_region.current.name}.amazoncognito.com/oauth2/token"
  description = "Cognito OAuth token endpoint URL"
}

output "cognito_discovery_url" {
  value       = "https://cognito-idp.${data.aws_region.current.name}.amazonaws.com/${aws_cognito_user_pool.gateway.id}/.well-known/openid-configuration"
  description = "OIDC discovery URL for JWT validation"
}

output "gateway_scope" {
  value       = "${aws_cognito_resource_server.gateway.identifier}/invoke"
  description = "OAuth scope for gateway access"
}

##
# Gateway Outputs
##

output "gateway_id" {
  value       = aws_bedrockagentcore_gateway.main.gateway_id
  description = "Gateway identifier"
}

output "gateway_arn" {
  value       = aws_bedrockagentcore_gateway.main.gateway_arn
  description = "Gateway ARN"
}

output "gateway_url" {
  value       = aws_bedrockagentcore_gateway.main.gateway_url
  description = "Gateway URL endpoint"
}

output "gateway_role_arn" {
  value       = aws_iam_role.gateway.arn
  description = "Gateway IAM role ARN"
}
