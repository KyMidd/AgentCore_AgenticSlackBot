# DynamoDB Table for OAuth Tokens
# Stores per-user OAuth tokens with field-level encryption for third-party service integrations

resource "aws_dynamodb_table" "oauth_tokens" {
  name         = "${local.naming_prefix}OAuthTokens"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.oauth_tokens.arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name        = "${local.naming_prefix}OAuthTokens"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
