# MCP gateway for Vera and Vera-like bots
module "gateway" {
  source = "./gateway"

  gateway_name        = local.gateway_name
  runtime_name        = local.runtime_name
  environment         = var.environment
  secret_name         = var.secret_name
  schemas_bucket_name = local.schemas_bucket_name
}

# Lambda receiver, receives inbound webhook, triggers invoker asynchronously
module "receiver" {
  source = "./receiver"

  # Pass invoker function name from invoker module
  invoker_function_name = module.invoker.invoker_function_name

  # Pass variables
  secret_name        = var.secret_name
  bot_name           = var.bot_name
  account_short_code = var.account_short_code
  region_short_code  = var.region_short_code
  slack_bot_id       = var.slack_bot_id
  slack_bot_user_id  = var.slack_bot_user_id
}

# Invoker lambda, invokes AgentCore worker synchronously
module "invoker" {
  source = "./invoker"

  # Pass runtime info from worker module
  agent_runtime_arn = module.worker.runtime_arn

  # Pass variables
  bot_name           = var.bot_name
  account_short_code = var.account_short_code
  region_short_code  = var.region_short_code
}

# AgentCore Runtime
module "worker" {
  source = "./worker"

  # Runtime configuration
  runtime_name          = local.runtime_name
  ecr_repository_url    = aws_ecr_repository.veraslack.repository_url
  ecr_repository_arn    = aws_ecr_repository.veraslack.arn
  environment           = var.environment
  log_level             = var.log_level
  idle_timeout          = var.idle_timeout
  max_lifetime          = var.max_lifetime
  secret_name           = var.secret_name
  bot_name              = var.bot_name
  knowledge_base_id     = var.knowledge_base_id
  kb_region             = var.kb_region
  guardrails_id         = var.guardrails_id
  debug_enabled         = var.debug_enabled
  audit_logging_enabled = var.audit_logging_enabled
  audit_log_group_name  = "/aws/ai-bots/${var.region_short_code}-audit-logs"

  # Gateway configurations
  gateway_arn       = module.gateway.gateway_arn
  gateway_client_id = module.gateway.cognito_client_id
  gateway_url       = module.gateway.gateway_url
  gateway_token_url = module.gateway.cognito_token_url
  gateway_scope     = module.gateway.gateway_scope

  # Memory configuration
  memory_id        = aws_bedrockagentcore_memory.vera_memory.id
  memory_region    = var.memory_region
  session_ttl_days = var.session_ttl_days

  # Per-user OAuth configuration
  oauth_table_name  = aws_dynamodb_table.oauth_tokens.name
  oauth_table_arn   = aws_dynamodb_table.oauth_tokens.arn
  oauth_kms_key_id  = aws_kms_key.oauth_tokens.key_id
  oauth_kms_key_arn = aws_kms_key.oauth_tokens.arn
  auth_portal_url   = module.auth_portal.function_url
}

# Auth Portal for per-user OAuth authorization
module "auth_portal" {
  source = "./auth_portal"

  naming_prefix     = local.naming_prefix
  environment       = var.environment
  oauth_table_name  = aws_dynamodb_table.oauth_tokens.name
  oauth_table_arn   = aws_dynamodb_table.oauth_tokens.arn
  oauth_kms_key_id  = aws_kms_key.oauth_tokens.key_id
  oauth_kms_key_arn = aws_kms_key.oauth_tokens.arn
  secret_name       = var.secret_name
}
