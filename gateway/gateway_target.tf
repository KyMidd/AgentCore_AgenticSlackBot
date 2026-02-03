##
# Gateway Target - PagerDuty
##

resource "aws_bedrockagentcore_gateway_target" "pagerduty" {
  gateway_identifier = aws_bedrockagentcore_gateway.main.gateway_id
  name               = "pagerduty"

  target_configuration {
    mcp {
      open_api_schema {
        s3 {
          uri = "s3://amazonbedrockagentcore-built-sampleschemas455e0815-oj7jujcd8xiu/pagerduty-open-api.json"
        }
      }
    }
  }

  credential_provider_configuration {
    api_key {
      provider_arn        = "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:token-vault/default/apikeycredentialprovider/pagerduty-vera-read-only"
      credential_prefix   = "Token"
      credential_location = "HEADER"
    }
  }
}
