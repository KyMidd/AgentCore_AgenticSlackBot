variable "agent_runtime_arn" {
  description = "ARN of the AgentCore runtime to invoke"
  type        = string
}

variable "bot_name" {
  description = "Name of the bot"
  type        = string
}

variable "account_short_code" {
  description = "Short code for the account"
  type        = string
}

variable "region_short_code" {
  description = "Short code for the region"
  type        = string
}
