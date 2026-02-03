output "invoker_function_name" {
  value       = aws_lambda_function.invoker.function_name
  description = "Name of the invoker Lambda function"
}

output "invoker_function_arn" {
  value       = aws_lambda_function.invoker.arn
  description = "ARN of the invoker Lambda function"
}
