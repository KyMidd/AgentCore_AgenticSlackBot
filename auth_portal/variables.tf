variable "naming_prefix" {
  description = "Naming prefix for resources (e.g., Ue1TiVera)"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "oauth_table_name" {
  description = "DynamoDB OAuth tokens table name"
  type        = string
}

variable "oauth_table_arn" {
  description = "DynamoDB OAuth tokens table ARN"
  type        = string
}

variable "oauth_kms_key_arn" {
  description = "KMS key ARN for OAuth token encryption"
  type        = string
}

variable "oauth_kms_key_id" {
  description = "KMS key ID for OAuth token encryption"
  type        = string
}

variable "secret_name" {
  description = "Secrets Manager secret name containing OAuth client credentials"
  type        = string
}
