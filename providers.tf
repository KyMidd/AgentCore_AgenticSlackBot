terraform {
  required_version = ">= 1.9.8"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.26"
    }
  }
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.current_account_number]

  default_tags {
    tags = {
      CodeAt    = "https://github.com/YOUR_ORG/YOUR_REPO"
      terraform = "true"
      Owner     = "YOUR_TEAM"
    }
  }
}

# Provider in Uw2 region for Bedrock/KB resources
provider "aws" {
  alias  = "west2"
  region = "us-west-2"

  default_tags {
    tags = {
      CodeAt    = "https://github.com/YOUR_ORG/YOUR_REPO"
      terraform = "true"
      Owner     = "YOUR_TEAM"
      Project   = "Vera"
    }
  }
}