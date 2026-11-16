# Offline check: every provider call is mocked, so this needs no AWS account and creates
# nothing. It catches expression and wiring errors that `terraform validate` cannot see.
#   terraform -chdir=deploy/terraform/envs/demo test

mock_provider "aws" {
  mock_data "aws_ssm_parameter" {
    defaults = { insecure_value = "ami-00000000000000000" }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_resource "aws_eip" {
    defaults = { public_ip = "203.0.113.10" }
  }
  mock_resource "aws_ecr_repository" {
    defaults = { repository_url = "registry.example.test/repository" }
  }
}

variables {
  github_repo = "example-owner/example-repo"
  alert_email = "alerts@example.org"
}

run "defaults" {
  command = apply

  assert {
    condition     = output.demo_host == "203-0-113-10.sslip.io"
    error_message = "Without a domain the host must be derived from the Elastic IP."
  }
  assert {
    condition     = length(aws_route53_record.demo) == 0
    error_message = "No DNS record without a zone and a domain."
  }
  assert {
    condition     = output.release_document == "lotse-demo-release"
    error_message = "The release document name is part of the deploy contract."
  }
}

run "own_domain" {
  command = apply

  variables {
    domain_name     = "demo.example.org"
    route53_zone_id = "Z0000000000000"
  }

  assert {
    condition     = output.demo_host == "demo.example.org"
    error_message = "A configured domain must be used as the host."
  }
  assert {
    condition     = length(aws_route53_record.demo) == 1
    error_message = "A zone and a domain must produce one A record."
  }
}

run "existing_oidc_provider_is_reused" {
  command = apply

  variables {
    existing_github_oidc_provider_arn = "arn:aws:iam::000000000000:oidc-provider/token.actions.githubusercontent.com"
  }

  assert {
    condition     = module.github_oidc.oidc_provider_arn == var.existing_github_oidc_provider_arn
    error_message = "An existing provider must be reused, not created a second time."
  }
}
