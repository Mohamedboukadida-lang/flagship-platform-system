terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }

  # The bucket name contains the account id, so it is passed at init time and never committed:
  #   terraform init -backend-config="bucket=<state_bucket output of ../../bootstrap>"
  backend "s3" {
    key          = "demo/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { project = "lotse", env = "demo", managed_by = "terraform" }
  }
}
