# Build and push Docker image for AgentCore Worker
# Automatically triggers on any Python file, Dockerfile, or requirements.txt change
resource "null_resource" "build_and_push_worker_image" {
  triggers = {
    # File content changes - triggers rebuild when code changes
    dockerfile_hash   = filesha256("${path.module}/Dockerfile")
    requirements_hash = filesha256("${path.module}/requirements.txt")
    src_files_hash    = local.python_files_hash

    # Image tag changes when code changes
    image_tag = local.image_tag
  }

  provisioner "local-exec" {
    command     = <<EOF
      echo "================================================"
      echo "Building Worker with image tag: ${local.image_tag}"
      echo "================================================"

      # Login to ECR
      aws ecr get-login-password --region ${data.aws_region.current.name} | docker login --username AWS --password-stdin ${var.ecr_repository_url}

      # Build and push Docker image for ARM64
      docker buildx build \
        --platform linux/arm64 \
        --output=type=registry,compression=gzip,force-compression=true \
        --provenance=false \
        --sbom=false \
        -t ${local.image_uri} \
        --push \
        --progress=plain \
        .

      echo "✅ Image pushed: ${local.image_uri}"
    EOF
    working_dir = path.module
  }
}

# AgentCore Runtime resource
resource "aws_bedrockagentcore_agent_runtime" "veraslack" {
  agent_runtime_name = var.runtime_name
  description        = "VeraSlack agent runtime with multi-gateway MCP access"
  role_arn           = aws_iam_role.veraslack_runtime.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = local.image_uri
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  lifecycle_configuration = [
    {
      idle_runtime_session_timeout = var.idle_timeout
      max_lifetime                 = var.max_lifetime
    }
  ]

  protocol_configuration {
    server_protocol = "HTTP"
  }

  # Environment variables with gateway ARNs
  environment_variables = {
    # Unified Vera Gateway ARN for AgentCore MCP tool access
    VERA_GATEWAY_ARN = local.vera_gateway_arn

    # Gateway authentication
    GATEWAY_CLIENT_ID = var.gateway_client_id
    GATEWAY_URL       = var.gateway_url
    GATEWAY_TOKEN_URL = var.gateway_token_url
    GATEWAY_SCOPE     = var.gateway_scope

    # Runtime configuration
    LOG_LEVEL   = var.log_level
    AWS_REGION  = local.aws_region
    PORT        = "8080"
    SECRET_NAME = var.secret_name

    # Bot configuration
    BOT_NAME              = var.bot_name
    DEBUG_ENABLED         = var.debug_enabled
    KNOWLEDGE_BASE_ID     = var.knowledge_base_id
    KNOWLEDGE_BASE_REGION = var.kb_region
    GUARDRAILS_ID         = var.guardrails_id
    AUDIT_LOGGING_ENABLED = var.audit_logging_enabled ? "True" : "False"
    AUDIT_LOG_GROUP_NAME  = var.audit_log_group_name

    # AgentCore Memory Configuration
    MEMORY_ID        = var.memory_id
    MEMORY_TYPE      = "SESSION_SUMMARY"
    MEMORY_REGION    = var.memory_region
    SESSION_TTL_DAYS = var.session_ttl_days

    # Per-user OAuth configuration
    OAUTH_TABLE_NAME = var.oauth_table_name
    OAUTH_KMS_KEY_ID = var.oauth_kms_key_id
    AUTH_PORTAL_URL  = var.auth_portal_url
  }

  tags = {
    Name    = var.runtime_name
    Purpose = "Multi-gateway agent with MCP tool access"
  }

  # Ensure Docker image is built and pushed before creating runtime
  depends_on = [null_resource.build_and_push_worker_image]
}
