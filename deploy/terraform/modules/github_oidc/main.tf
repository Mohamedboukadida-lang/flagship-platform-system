# Lets GitHub Actions deploy without stored AWS keys. The role can be assumed only by
# jobs of one repository that run in one GitHub environment, and it can do two things:
# push to this project's ECR repositories and run the deploy document on the demo node.

variable "name" {
  type = string
}

variable "github_repo" {
  description = "owner/name, with the exact casing GitHub shows"
  type        = string
}

variable "github_environment" {
  type = string
}

variable "existing_provider_arn" {
  description = "ARN of the account's GitHub OIDC provider if it already exists (an account can hold only one)"
  type        = string
  default     = null
}

variable "ecr_repository_arns" {
  type = list(string)
}

variable "instance_arn" {
  type = string
}

variable "deploy_document_arn" {
  type = string
}

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.existing_provider_arn == null ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

locals {
  provider_arn = var.existing_provider_arn != null ? var.existing_provider_arn : aws_iam_openid_connect_provider.github[0].arn
}

data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # A job that names an environment gets this subject, not a branch ref. Restrict the
    # environment to the main branch in the repository settings.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:environment:${var.github_environment}"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "${var.name}-github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "deploy" {
  # Wildcard, justified: GetAuthorizationToken has no resource-level permissions.
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPushAndRead"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = var.ecr_repository_arns
  }

  # Only this document on this instance: the role cannot run arbitrary commands.
  statement {
    sid       = "RunDeployDocument"
    actions   = ["ssm:SendCommand"]
    resources = [var.instance_arn, var.deploy_document_arn]
  }

  # Wildcard, justified: GetCommandInvocation has no resource-level permissions.
  statement {
    sid       = "ReadCommandResult"
    actions   = ["ssm:GetCommandInvocation"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}

output "deploy_role_arn" {
  value = aws_iam_role.deploy.arn
}

output "oidc_provider_arn" {
  value = local.provider_arn
}
