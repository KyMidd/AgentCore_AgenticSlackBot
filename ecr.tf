# ECR Repository for VeraSlack Container Images
resource "aws_ecr_repository" "veraslack" {
  name                 = local.ecr_repository_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name        = local.ecr_repository_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Purpose     = "Container images for Vera AgentCore runtime"
  }
}

# ECR Lifecycle Policy - Keep last 10 images
resource "aws_ecr_lifecycle_policy" "veraslack" {
  repository = aws_ecr_repository.veraslack.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
