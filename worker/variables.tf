# Passed from root
variable "runtime_name" {
  description = "Name of the AgentCore runtime"
  type        = string
}

variable "ecr_repository_url" {
  description = "ECR repository URL for the container image"
  type        = string
}

variable "ecr_repository_arn" {
  description = "ECR repository ARN for IAM policies"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "log_level" {
  description = "Log level for the runtime"
  type        = string
  default     = "INFO"
}

variable "idle_timeout" {
  description = "Idle runtime session timeout in seconds"
  type        = number
  default     = 900
}

variable "max_lifetime" {
  description = "Maximum runtime lifetime in seconds"
  type        = number
  default     = 28800
}

variable "secret_name" {
  description = "Name of the secret in AWS Secrets Manager"
  type        = string
}

variable "bot_name" {
  description = "Name of the bot"
  type        = string
}

variable "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID"
  type        = string
}

variable "kb_region" {
  description = "AWS region for Bedrock Knowledge Base"
  type        = string
}

variable "guardrails_id" {
  description = "Bedrock Guardrails ID"
  type        = string
}

variable "debug_enabled" {
  description = "Enable debug logging"
  type        = string
  default     = "False"
}

variable "audit_logging_enabled" {
  description = "Enable audit logging"
  type        = bool
  default     = false
}

variable "audit_log_group_name" {
  description = "CloudWatch log group name for audit logs (passed from parent)"
  type        = string
}

# Gateway configurations
variable "gateway_arn" {
  description = "Gateway ARN for the unified Vera gateway"
  type        = string
}

variable "gateway_client_id" {
  description = "Cognito client ID for gateway authentication"
  type        = string
}

variable "gateway_url" {
  description = "Gateway MCP endpoint URL"
  type        = string
}

variable "gateway_token_url" {
  description = "Cognito OAuth token endpoint URL"
  type        = string
}

variable "gateway_scope" {
  description = "OAuth scope for gateway access"
  type        = string
}

# AgentCore Memory Configuration
variable "memory_id" {
  description = "AgentCore Memory ID (shared with VeraTeams)"
  type        = string
}

variable "session_ttl_days" {
  description = "Number of days to retain conversation sessions"
  type        = number
}

variable "memory_region" {
  description = "AWS region for AgentCore Memory"
  type        = string
}