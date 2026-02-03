# Passed from root
variable "invoker_function_name" {
  description = "Name of the invoker Lambda function"
  type        = string
}

variable "secret_name" {
  description = "Name of the secret in AWS Secrets Manager"
  type        = string
}

variable "bot_name" {
  description = "Name of the bot"
  type        = string
}

variable "account_short_code" {
  description = "Short code for the AWS account"
  type        = string
}

variable "region_short_code" {
  description = "Short code for the AWS region"
  type        = string
}
