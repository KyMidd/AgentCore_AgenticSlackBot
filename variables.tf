variable "current_account_number" {
  description = "Account number of the AWS account where resources will be created"
  type        = string
  default     = "cmdline_variable"
}

variable "account_name" {
  description = "Name of the AWS account"
  type        = string
}

variable "account_short_code" {
  description = "Short code for the account, e.g., 'dev' for development, 'prd' for production"
  type        = string
}

variable "region" {
  description = "The region in which the bot is deployed"
  type        = string
  default     = "us-east-1"
}

variable "region_short_code" {
  description = "Short code for the region, e.g., 'ue1' for us-east-1"
  type        = string
  default     = "ue1"
}

variable "environment" {
  description = "The environment in which the bot is deployed"
  type        = string
}

# AgentCore Runtime Configuration
variable "log_level" {
  description = "Log level for runtime"
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

# Bot Configuration
variable "bot_name" {
  description = "The name of the Slack bot"
  type        = string
}

variable "secret_name" {
  description = "AWS Secrets Manager secret name for bot credentials"
  type        = string
}

variable "manage_secrets" {
  description = "Whether to create placeholder secrets (set to false if secrets already exist)"
  type        = bool
  default     = false
}

variable "debug_enabled" {
  description = "Enable debug mode for the Slack bot"
  type        = string
  default     = "false"
}

variable "knowledge_base_id" {
  description = "The Knowledge Base ID to be used by the bot"
  type        = string
}

variable "kb_region" {
  description = "AWS region for Bedrock Knowledge Base"
  type        = string
  default     = "us-west-2"
}

variable "guardrails_id" {
  description = "The Guardrails ID to be used by the bot"
  type        = string
}

variable "audit_logging_enabled" {
  description = "Enable audit logging to CloudWatch"
  type        = bool
  default     = false
}

# AgentCore Memory Configuration
variable "session_ttl_days" {
  description = "Number of days to retain conversation sessions in memory"
  type        = number
  default     = 30
}

variable "memory_region" {
  description = "AWS region for AgentCore Memory"
  type        = string
  default     = "us-east-1"
}

# Slack Bot Identity (for receiver Lambda bot-message detection)
variable "slack_bot_id" {
  description = "Slack Bot ID (from auth.test) used by receiver to detect own messages"
  type        = string
  default     = ""
}

variable "slack_bot_user_id" {
  description = "Slack Bot User ID used by receiver to detect own messages (catches file_share events)"
  type        = string
  default     = ""
}