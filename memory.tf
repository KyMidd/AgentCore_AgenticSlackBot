# AgentCore Memory Resource
# Provides persistent conversation context across sessions using DynamoDB backend
# Shared between VeraSlack and VeraTeams

resource "aws_bedrockagentcore_memory" "vera_memory" {
  name                      = "${title(var.region_short_code)}${title(var.account_short_code)}VeraMemory"
  event_expiry_duration     = var.session_ttl_days
  memory_execution_role_arn = module.worker.worker_task_role_arn

  tags = {
    Name        = "${title(var.region_short_code)}${title(var.account_short_code)}VeraMemory"
    Environment = var.environment
  }
}

# User preferences path
# long term memory created via dynamically extracted facts, preferences, and patterns
# Distinct for each user (keyed by actorId)
resource "aws_bedrockagentcore_memory_strategy" "user_preferences" {
  name                      = "${title(var.region_short_code)}${title(var.account_short_code)}UserPreferences"
  memory_id                 = aws_bedrockagentcore_memory.vera_memory.id
  type                      = "USER_PREFERENCE"
  namespaces                = ["/preferences/{actorId}"]
  memory_execution_role_arn = module.worker.worker_task_role_arn
}