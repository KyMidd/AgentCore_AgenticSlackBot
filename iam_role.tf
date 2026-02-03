############################################################
# OIDC role/policy for TfAwsVeraSlackBot to SyncKnowledgeBase
############################################################

# Role for GitHub Actions to assume
resource "aws_iam_role" "kb_sync_role" {
  name = "${local.bot_name}KBSyncRole"

  max_session_duration = 43200 # 12 hours
  assume_role_policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "GitHubActionsOIDC",
        "Effect" : "Allow",
        "Principal" : {
          "Federated" : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
        },
        "Action" : [
          "sts:AssumeRoleWithWebIdentity",
          "sts:TagSession"
        ],
        "Condition" : {
          "StringEquals" : {
            "token.actions.githubusercontent.com:aud" : "sts.amazonaws.com"
          },
          StringLike : {
            "token.actions.githubusercontent.com:sub" : [
              "repo:YOUR_ORG/YOUR_REPO:environment:*:job_workflow_ref:YOUR_ORG/YOUR_REPO/.github/workflows/sync.yml@refs/heads/*",
            ]
          }
        }
      }
    ]
  })
}

# policy for oidc assume role
resource "aws_iam_policy" "kb_sync_policy" {
  name        = "${local.bot_name}KBSyncPolicy"
  description = "Permissions to sync bedrock knowledge base"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          # Bedrock
          "bedrock:SyncKnowledgeBase",
          "bedrock:GetKnowledgeBase",
          "bedrock:GetDataSource",
          "bedrock:GetIngestionJob",
          "bedrock:ListIngestionJobs",
          "bedrock:StartIngestionJob",
          "bedrock:ListDataSources",
          "bedrock:GetDataSources",

          # KMS
          "kms:Decrypt",

          # Secrets Manager
          # needed for confluence credentials
          "secretsmanager:GetSecretValue",
        ],
        Resource = "*"
      }
    ]
  })
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "kb_sync_role_policy_attach" {
  role       = aws_iam_role.kb_sync_role.name
  policy_arn = aws_iam_policy.kb_sync_policy.arn
}
