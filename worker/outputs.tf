# Outputs for AgentCore module
output "runtime_arn" {
  value       = aws_bedrockagentcore_agent_runtime.veraslack.agent_runtime_arn
  description = "AgentCore Runtime ARN"
}

output "runtime_id" {
  value       = aws_bedrockagentcore_agent_runtime.veraslack.agent_runtime_id
  description = "AgentCore Runtime ID"
}

output "worker_task_role_arn" {
  value       = aws_iam_role.veraslack_runtime.arn
  description = "Worker Task IAM Role ARN (for memory execution)"
}
