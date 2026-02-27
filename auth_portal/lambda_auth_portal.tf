# Archive data source for Lambda deployment
data "archive_file" "auth_portal" {
  type        = "zip"
  source_dir  = "${path.module}/src"
  output_path = "${path.module}/build/auth_portal.zip"
}

# IAM role for Lambda execution
resource "aws_iam_role" "auth_portal" {
  name = "${local.function_name}Role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${local.function_name}Role"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# IAM role policy
resource "aws_iam_role_policy" "auth_portal" {
  name = "${local.function_name}Policy"
  role = aws_iam_role.auth_portal.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query"
        ]
        Resource = var.oauth_table_arn
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt"
        ]
        Resource = var.oauth_kms_key_arn
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.secret_name}*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.function_name}*"
      }
    ]
  })
}

# Lambda function
resource "aws_lambda_function" "auth_portal" {
  function_name    = local.function_name
  role             = aws_iam_role.auth_portal.arn
  handler          = "auth_portal.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 256
  architectures    = ["arm64"]
  filename         = data.archive_file.auth_portal.output_path
  source_code_hash = local.source_hash

  environment {
    variables = {
      OAUTH_TABLE_NAME = var.oauth_table_name
      OAUTH_KMS_KEY_ID = var.oauth_kms_key_id
      SECRET_NAME      = var.secret_name
    }
  }

  tags = {
    Name        = local.function_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Lambda Function URL
resource "aws_lambda_function_url" "auth_portal" {
  function_name      = aws_lambda_function.auth_portal.function_name
  authorization_type = "NONE"
}
