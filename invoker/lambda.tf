###
# Build invoker lambda
###
data "archive_file" "invoker_lambda" {
  type        = "zip"
  source_file = "${path.module}/src/invoker.py"
  output_path = "${path.module}/invoker.zip"
}

###
# Invoker Lambda - calls AgentCore synchronously
###

resource "aws_lambda_function" "invoker" {
  filename      = "${path.module}/invoker.zip"
  function_name = "${local.regionalized_lambda_function_name}Invoker"
  role          = aws_iam_role.invoker_role.arn
  handler       = "invoker.lambda_handler"
  timeout       = 900
  memory_size   = 256
  runtime       = "python3.12"
  architectures = ["arm64"]

  source_code_hash = data.archive_file.invoker_lambda.output_base64sha256

  environment {
    variables = {
      AGENT_RUNTIME_ARN = var.agent_runtime_arn
    }
  }
}
