locals {
  naming_prefix = "${title(var.region_short_code)}${title(var.account_short_code)}${title(var.bot_name)}" # Ue1TiVera

  bot_name                   = "${local.naming_prefix}SlackBot"
  uw2_s3_logging_bucket_name = "${var.account_short_code}-${var.environment}-uw2-s3-access-logs"

  # AgentCore naming - constructed from primitives
  gateway_name = "${title(var.region_short_code)}${title(var.account_short_code)}${title(var.bot_name)}Gateway" # Ue1TiVeraGateway

  # Reference secret ID based on whether we're creating it or it exists
  splunk_hec_secret_id = var.manage_secrets ? aws_secretsmanager_secret.ai_tools_splunk_hec_token[0].name : "aws-ai-tooling-splunk-hec-token"

  # Runtime name
  runtime_name        = local.naming_prefix
  ecr_repository_name = "${lower(var.region_short_code)}${lower(var.account_short_code)}-veraslack"            # e.g., ue1ti-veraslack
  schemas_bucket_name = "${lower(var.region_short_code)}${lower(var.account_short_code)}-vera-gateway-schemas" # e.g., ue1ti-vera-gateway-schemas

}