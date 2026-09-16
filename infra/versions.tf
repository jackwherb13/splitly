terraform {
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  //record of what terraform manages in aws
  backend "s3" {
    bucket       = "splitly-tfstate-725423737107"
    key          = "splitly/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
