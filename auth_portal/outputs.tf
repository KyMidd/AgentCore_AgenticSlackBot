output "function_url" {
  description = "Auth Portal Lambda Function URL"
  value       = aws_lambda_function_url.auth_portal.function_url
}

output "lambda_function_name" {
  description = "Auth Portal Lambda function name"
  value       = aws_lambda_function.auth_portal.function_name
}

output "lambda_role_arn" {
  description = "Auth Portal Lambda IAM Role ARN"
  value       = aws_iam_role.auth_portal.arn
}
