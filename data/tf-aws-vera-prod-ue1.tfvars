# Account Configuration
account_name       = "prod"
account_short_code = "prd"
region_short_code  = "ue1"
environment        = "prd"

# Bot Configuration
bot_name          = "Vera"
knowledge_base_id = "ABCDEFGHIJ" # your-knowledge-base
guardrails_id     = "abcdefghij" # Ue1PrdVeraBotGuardrail
debug_enabled     = "True"
secret_name       = "path/to/SECRET"

# Runtime Configuration
log_level    = "INFO"
idle_timeout = 900   # 15 minutes
max_lifetime = 28800 # 8 hours

# Audit logging
audit_logging_enabled = true

# Slack Bot Identity
slack_bot_id      = "BXXXXXXXXXX"
slack_bot_user_id = "UXXXXXXXXXX"
