###
# General data sources
###

data "aws_region" "current" {}

data "aws_caller_identity" "current" {}

###
# Secrets Manager data sources
###

# Get the secret version (works for both existing and newly created secrets)
data "aws_secretsmanager_secret_version" "ai_tools_splunk_hec_token" {
  provider = aws.west2

  # Reference secret ID based on whether we're creating it or it exists
  secret_id = var.manage_secrets ? aws_secretsmanager_secret.ai_tools_splunk_hec_token[0].name : "aws-ai-tooling-splunk-hec-token"

  depends_on = [aws_secretsmanager_secret_version.ai_tools_splunk_hec_token]
}