# Terraform + provider pins. S3-native state locking requires TF >= 1.10.
terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket       = "phrasaurus-tf-state-534886060250"
    key          = "phrasaurus/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true # S3-native locking (TF 1.10+). No DynamoDB table needed.
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project   = "phrasaurus"
      ManagedBy = "terraform"
    }
  }
}
