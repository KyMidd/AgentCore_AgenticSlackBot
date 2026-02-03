locals {
  regionalized_lambda_function_name = "${title(var.region_short_code)}${title(var.account_short_code)}${title(var.bot_name)}" # Ue1SgVeraSlack
}
