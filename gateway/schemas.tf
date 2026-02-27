##
# S3 bucket for custom schemas
##

resource "aws_s3_bucket" "custom_schemas" {
  bucket = var.schemas_bucket_name

  tags = {
    Name        = var.schemas_bucket_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_versioning" "custom_schemas" {
  bucket = aws_s3_bucket.custom_schemas.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "custom_schemas" {
  bucket = aws_s3_bucket.custom_schemas.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "custom_schemas" {
  bucket = aws_s3_bucket.custom_schemas.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

##
# S3 objects for each schema
##

resource "aws_s3_object" "jira_schema" {
  bucket       = aws_s3_bucket.custom_schemas.id
  key          = "jira-open-api.json"
  source       = "${path.module}/custom_schemas/jira-open-api.json"
  content_type = "application/json"
  etag         = filemd5("${path.module}/custom_schemas/jira-open-api.json")
}

resource "aws_s3_object" "confluence_schema" {
  bucket       = aws_s3_bucket.custom_schemas.id
  key          = "confluence-open-api.json"
  source       = "${path.module}/custom_schemas/confluence-open-api.json"
  content_type = "application/json"
  etag         = filemd5("${path.module}/custom_schemas/confluence-open-api.json")
}
