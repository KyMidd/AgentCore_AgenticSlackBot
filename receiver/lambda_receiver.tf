###
# IAM Role and policies for Message Receiver Lambda
###

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_iam_policy_document" "receiver_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "receiver_role" {
  name               = "${local.regionalized_lambda_function_name}ReceiverRole"
  assume_role_policy = data.aws_iam_policy_document.receiver_assume_role.json
}

resource "aws_iam_role_policy" "invoke_lambda" {
  name = "InvokeLambda"
  role = aws_iam_role.receiver_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.id}:function:${var.invoker_function_name}",
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.id}:function:${var.invoker_function_name}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "cloudwatch" {
  name = "Cloudwatch"
  role = aws_iam_role.receiver_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "logs:CreateLogGroup"
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.id}:log-group:/aws/lambda/${local.regionalized_lambda_function_name}Receiver:*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "secrets_manager" {
  name = "SecretsManager"
  role = aws_iam_role.receiver_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.id}:secret:${var.secret_name}*"
      }
    ]
  })
}

###
# Build receiver lambda
###

data "archive_file" "receiver_lambda" {
  type        = "zip"
  source_file = "${path.module}/src/receiver.py"
  output_path = "${path.module}/receiver.zip"
}

resource "aws_lambda_function" "receiver" {
  filename      = "${path.module}/receiver.zip"
  function_name = "${local.regionalized_lambda_function_name}Receiver"
  role          = aws_iam_role.receiver_role.arn
  handler       = "receiver.lambda_handler"
  timeout       = 10
  memory_size   = 512
  runtime       = "python3.12"
  architectures = ["arm64"]

  source_code_hash = data.archive_file.receiver_lambda.output_base64sha256

  environment {
    variables = {
      INVOKER_FUNCTION_NAME = var.invoker_function_name
      SECRET_NAME           = var.secret_name
    }
  }
}

# Publish alias of new version
resource "aws_lambda_alias" "receiver_alias" {
  name             = "Newest"
  function_name    = aws_lambda_function.receiver.arn
  function_version = aws_lambda_function.receiver.version

  # Add ignore for routing_configuration
  lifecycle {
    ignore_changes = [
      routing_config, # This sometimes has a race condition, so ignore changes to it
    ]
  }
}

# Point lambda function url at new version
resource "aws_lambda_function_url" "receiver_slack_trigger_function_url" {
  function_name      = aws_lambda_function.receiver.function_name
  qualifier          = aws_lambda_alias.receiver_alias.name
  authorization_type = "NONE"
}

# Output the URL we can use to trigger the bot
output "receiver_slack_trigger_function_url" {
  value = aws_lambda_function_url.receiver_slack_trigger_function_url.function_url
}
