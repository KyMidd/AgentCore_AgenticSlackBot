# IAM Role for VeraSlack Runtime
resource "aws_iam_role" "veraslack_runtime" {
  name = "${var.runtime_name}RuntimeRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "${var.runtime_name}RuntimeRole"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# IAM Policy for Runtime - Bedrock Model Access
resource "aws_iam_role_policy" "veraslack_bedrock_access" {
  name = "BedrockModelAccess"
  role = aws_iam_role.veraslack_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Grant permission to invoke bedrock models and inference profiles in multiple regions
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelStream",
          "bedrock:InvokeModelWithResponseStream"
        ]
        # Both foundation models and inference profiles across multiple regions
        Resource = [
          "arn:aws:bedrock:us-east-1::foundation-model/*",
          "arn:aws:bedrock:us-east-2::foundation-model/*",
          "arn:aws:bedrock:us-west-1::foundation-model/*",
          "arn:aws:bedrock:us-west-2::foundation-model/*",
          "arn:aws:bedrock:us-east-1:${data.aws_caller_identity.current.account_id}:inference-profile/*",
          "arn:aws:bedrock:us-east-2:${data.aws_caller_identity.current.account_id}:inference-profile/*",
          "arn:aws:bedrock:us-west-1:${data.aws_caller_identity.current.account_id}:inference-profile/*",
          "arn:aws:bedrock:us-west-2:${data.aws_caller_identity.current.account_id}:inference-profile/*"
        ]
      },
      # Grant permission to invoke bedrock guardrails
      {
        Effect = "Allow"
        Action = [
          "bedrock:ApplyGuardrail"
        ]
        Resource = [
          "arn:aws:bedrock:us-east-1:${data.aws_caller_identity.current.account_id}:guardrail/*",
          "arn:aws:bedrock:us-west-2:${data.aws_caller_identity.current.account_id}:guardrail/*",
        ]
      },
      # Grant permissions to use knowledge bases
      {
        Effect = "Allow"
        Action = [
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate"
        ]
        Resource = "arn:aws:bedrock:us-west-2:${data.aws_caller_identity.current.account_id}:knowledge-base/*"
      }
    ]
  })
}

# IAM Policy for Runtime - Gateway Access
resource "aws_iam_role_policy" "veraslack_gateway_access" {
  name = "GatewayAccess"
  role = aws_iam_role.veraslack_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:InvokeGateway",
          "bedrock-agentcore:CallTool"
        ]
        Resource = "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:gateway/*"
      }
    ]
  })
}

# IAM Policy for Runtime - CloudWatch Logs
resource "aws_iam_role_policy" "veraslack_logs" {
  name = "CloudWatchLogs"
  role = aws_iam_role.veraslack_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:DescribeLogGroups"
        ]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
        ]
        Resource = [
          # AgentCore runtime logs
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/*:*",

          # AgentCore vended logs
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/*",
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/*:*",

          # Custom audit logs
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:${var.audit_log_group_name}:*"
        ]
      }
    ]
  })
}

# IAM Policy for Runtime - ECR Access (to pull container image)
resource "aws_iam_role_policy" "veraslack_ecr_access" {
  name = "ECRAccess"
  role = aws_iam_role.veraslack_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = var.ecr_repository_arn
      }
    ]
  })
}

# IAM Policy for Runtime - Secrets Manager Access (to fetch Slack bot credentials)
resource "aws_iam_role_policy" "veraslack_secrets_access" {
  name = "SecretsManagerAccess"
  role = aws_iam_role.veraslack_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.secret_name}*"
      }
    ]
  })
}

# IAM Policy for Runtime - AWS X-Ray service access (OpenTelemetry traces are sent to AWS X-Ray)
resource "aws_iam_role_policy" "veraslack_xray_access" {
  name = "XRayAccess"
  role = aws_iam_role.veraslack_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Policy for Runtime - STS AssumeRole (for cross-account AWS CLI access)
resource "aws_iam_role_policy" "veraslack_sts_assume" {
  name = "STSAssumeRole"
  role = aws_iam_role.veraslack_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
        Resource = "arn:aws:iam::*:role/vera-research-read-only"
      }
    ]
  })
}

# IAM Policy for Runtime - AgentCore Memory Operations
resource "aws_iam_role_policy" "veraslack_memory_access" {
  name = "MemoryAccess"
  role = aws_iam_role.veraslack_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          # Memory Resource
          "bedrock-agentcore:GetMemory",
          "bedrock-agentcore:ListMemories",
          # Events (short-term memory)
          "bedrock-agentcore:CreateEvent",
          "bedrock-agentcore:GetEvent",
          "bedrock-agentcore:ListEvents",
          # Memory Records (long-term memory)
          "bedrock-agentcore:GetMemoryRecord",
          "bedrock-agentcore:ListMemoryRecords",
          "bedrock-agentcore:RetrieveMemoryRecords",
          "bedrock-agentcore:DeleteMemoryRecord"
        ]
        Resource = "arn:aws:bedrock-agentcore:${var.memory_region}:${data.aws_caller_identity.current.account_id}:memory/${var.memory_id}"
      }
    ]
  })
}

# IAM Policy for Runtime - DynamoDB OAuth Token Access
resource "aws_iam_role_policy" "veraslack_oauth_dynamodb" {
  name = "OAuthDynamoDBAccess"
  role = aws_iam_role.veraslack_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = var.oauth_table_arn
      }
    ]
  })
}

# IAM Policy for Runtime - KMS OAuth Token Encryption
resource "aws_iam_role_policy" "veraslack_oauth_kms" {
  name = "OAuthKMSAccess"
  role = aws_iam_role.veraslack_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt"
        ]
        Resource = var.oauth_kms_key_arn
      }
    ]
  })
}
