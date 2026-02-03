###
# IAM Role and policies for Invoker Lambda
###

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_iam_policy_document" "invoker_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "invoker_role" {
  name               = "${local.regionalized_lambda_function_name}InvokerRole"
  assume_role_policy = data.aws_iam_policy_document.invoker_assume_role.json
}

resource "aws_iam_role_policy" "bedrock_agentcore" {
  name = "InvokeAgentRuntime"
  role = aws_iam_role.invoker_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:InvokeAgentRuntime"
        ]
        Resource = [
          var.agent_runtime_arn,
          "${var.agent_runtime_arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "cloudwatch" {
  name = "Cloudwatch"
  role = aws_iam_role.invoker_role.id

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
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.id}:log-group:/aws/lambda/${local.regionalized_lambda_function_name}Invoker:*"
        ]
      }
    ]
  })
}
