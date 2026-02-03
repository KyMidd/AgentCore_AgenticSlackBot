# Computed locals for Worker module

locals {
  # AWS account and region data
  aws_account_id = data.aws_caller_identity.current.account_id
  aws_region     = data.aws_region.current.name

  # Hash of all Python source files
  python_files_hash = sha256(join("", [
    for f in fileset("${path.module}/src", "*.py") :
    filesha256("${path.module}/src/${f}")
  ]))

  # Use hash as image tag (first 12 chars for readability)
  # Format: abc123def456
  image_tag = substr(local.python_files_hash, 0, 12)

  # Full image URI for runtime configuration
  image_uri = "${var.ecr_repository_url}:${local.image_tag}"

  # Unified Vera gateway ARN
  vera_gateway_arn = var.gateway_arn
}
