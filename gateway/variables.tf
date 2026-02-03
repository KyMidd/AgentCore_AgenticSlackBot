# Gateway Infrastructure Variables

variable "gateway_name" {
  description = "Name of the gateway"
  type        = string
  default     = "Ue1LiVeraGateway"
}

variable "runtime_name" {
  description = "Name of the AgentCore runtime that will use this gateway"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, production)"
  type        = string
}

variable "secret_name" {
  description = "Name of the Secrets Manager secret containing MCP credentials"
  type        = string
}