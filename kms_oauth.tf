# KMS Key for OAuth Token Encryption
# Provides field-level encryption for OAuth tokens stored in DynamoDB

resource "aws_kms_key" "oauth_tokens" {
  description             = "Encryption key for OAuth tokens in ${local.naming_prefix} bot"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Allow root account full access
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      # Allow worker runtime role to encrypt/decrypt tokens
      {
        Sid    = "Allow Worker Runtime Access"
        Effect = "Allow"
        Principal = {
          AWS = module.worker.worker_task_role_arn
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      },
      # Allow auth portal lambda role to encrypt/decrypt tokens
      {
        Sid    = "Allow Auth Portal Lambda Access"
        Effect = "Allow"
        Principal = {
          AWS = module.auth_portal.lambda_role_arn
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "${local.naming_prefix}OAuthTokensKey"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_kms_alias" "oauth_tokens" {
  name          = "alias/${lower(local.naming_prefix)}-oauth-tokens"
  target_key_id = aws_kms_key.oauth_tokens.key_id
}
