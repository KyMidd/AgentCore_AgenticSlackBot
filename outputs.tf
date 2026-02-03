# Outputs
output "receiver_lambda_url" {
  value       = module.receiver.receiver_slack_trigger_function_url
  description = "Lambda webhook URL - configure this in Slack App Event Subscriptions"
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.veraslack.repository_url
  description = "ECR repository URL for pushing container images"
}

output "gateway_id" {
  value       = module.gateway.gateway_id
  description = "Gateway identifier"
}

output "gateway_url" {
  value       = module.gateway.gateway_url
  description = "Gateway URL endpoint"
}

output "mcp_gateway_arn" {
  value       = module.gateway.gateway_arn
  description = "Gateway ARN"
}

output "mcp_gateway_scope" {
  value       = module.gateway.gateway_scope
  description = "OAuth scope for gateway access"
}

output "cognito_user_pool_id" {
  value       = module.gateway.cognito_user_pool_id
  description = "Cognito user pool ID for gateway authentication"
}

output "cognito_user_pool_arn" {
  value       = module.gateway.cognito_user_pool_arn
  description = "Cognito user pool ARN for IAM policy"
}

output "cognito_client_id" {
  value       = module.gateway.cognito_client_id
  description = "Cognito client ID for gateway authentication"
  sensitive   = true
}

output "cognito_client_secret" {
  value       = module.gateway.cognito_client_secret
  description = "Cognito client secret for gateway authentication"
  sensitive   = true
}

output "cognito_token_url" {
  value       = module.gateway.cognito_token_url
  description = "Cognito OAuth token endpoint URL"
}

# Memory Outputs (shared with VeraTeams)
output "memory_id" {
  description = "AgentCore Memory ID (shared between Vera bots)"
  value       = aws_bedrockagentcore_memory.vera_memory.id
}

output "memory_arn" {
  description = "AgentCore Memory ARN"
  value       = aws_bedrockagentcore_memory.vera_memory.arn
}

output "memory_name" {
  description = "AgentCore Memory name"
  value       = aws_bedrockagentcore_memory.vera_memory.name
}