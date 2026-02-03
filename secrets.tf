###
# Splunk HEC Token Secret Resources
###

# Create HEC token secret only if it doesn't exist
resource "aws_secretsmanager_secret" "ai_tools_splunk_hec_token" {
  provider = aws.west2
  count    = var.manage_secrets ? 1 : 0

  name        = "aws-ai-tooling-splunk-hec-token"
  description = "Splunk HEC token for AI tools logging - PLACEHOLDER"

  tags = {
    Environment = var.environment
    Account     = var.account_name
    Region      = "us-west-2"
    ManagedBy   = "terraform"
    Purpose     = "placeholder"
  }
}

# Create placeholder value for new secrets only
resource "aws_secretsmanager_secret_version" "ai_tools_splunk_hec_token" {
  provider = aws.west2
  count    = var.manage_secrets ? 1 : 0

  secret_id     = aws_secretsmanager_secret.ai_tools_splunk_hec_token[0].id
  secret_string = "PLACEHOLDER_REPLACE_WITH_REAL_HEC_TOKEN"

  lifecycle {
    ignore_changes = [secret_string]
  }
}