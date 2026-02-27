##
# Gateway Target - Jira
##

resource "aws_bedrockagentcore_gateway_target" "jira" {
  gateway_identifier = aws_bedrockagentcore_gateway.main.gateway_id
  name               = "jira"

  target_configuration {
    mcp {
      open_api_schema {
        s3 {
          uri = "s3://${aws_s3_bucket.custom_schemas.id}/${aws_s3_object.jira_schema.key}"
        }
      }
    }
  }

  credential_provider_configuration {
    api_key {
      provider_arn        = "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:token-vault/default/apikeycredentialprovider/atlassian-vera"
      credential_prefix   = "Basic"
      credential_location = "HEADER"
    }
  }
}

##
# Gateway Target - Confluence
##

resource "aws_bedrockagentcore_gateway_target" "confluence" {
  gateway_identifier = aws_bedrockagentcore_gateway.main.gateway_id
  name               = "confluence"

  target_configuration {
    mcp {
      open_api_schema {
        s3 {
          uri = "s3://${aws_s3_bucket.custom_schemas.id}/${aws_s3_object.confluence_schema.key}"
        }
      }
    }
  }

  credential_provider_configuration {
    api_key {
      provider_arn        = "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:token-vault/default/apikeycredentialprovider/atlassian-vera"
      credential_prefix   = "Basic"
      credential_location = "HEADER"
    }
  }
}
