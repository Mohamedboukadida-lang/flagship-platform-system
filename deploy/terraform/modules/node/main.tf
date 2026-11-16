# The demo node: one EC2 instance running k3s. No SSH and no inbound port besides 80/443;
# administration and deployment go through Systems Manager.

variable "name" {
  type = string
}

variable "region" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "security_group_id" {
  type = string
}

variable "instance_type" {
  type = string
}

variable "root_volume_gb" {
  type = number
}

variable "domain_name" {
  description = "Public hostname. Empty: derive one from the Elastic IP through sslip.io."
  type        = string
}

variable "k3s_channel" {
  type = string
}

variable "registry" {
  type = string
}

variable "ecr_repository_arns" {
  type = list(string)
}

variable "secret_arn" {
  type = string
}

variable "secret_name" {
  type = string
}

data "aws_ssm_parameter" "ubuntu" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

resource "aws_eip" "node" {
  domain = "vpc"
  tags   = { Name = var.name }
}

locals {
  host = var.domain_name != "" ? var.domain_name : "${replace(aws_eip.node.public_ip, ".", "-")}.sslip.io"
}

# --- Instance role: what the node itself may do -------------------------------------------

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "node" {
  name               = "${var.name}-node"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

# AWS-managed policy, required by the Systems Manager agent (Session Manager, Run Command).
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "node" {
  # Wildcard, justified: GetAuthorizationToken has no resource-level permissions.
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPull"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = var.ecr_repository_arns
  }

  statement {
    sid       = "ReadAppSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.secret_arn]
  }
}

resource "aws_iam_role_policy" "node" {
  name   = "node"
  role   = aws_iam_role.node.id
  policy = data.aws_iam_policy_document.node.json
}

resource "aws_iam_instance_profile" "node" {
  name = "${var.name}-node"
  role = aws_iam_role.node.name
}

# --- Instance -----------------------------------------------------------------------------

resource "aws_instance" "node" {
  #checkov:skip=CKV_AWS_126:Detailed monitoring is a paid extra the demo does not need
  #checkov:skip=CKV_AWS_88:The node is the public entry point; it gets an Elastic IP by design
  ami                    = data.aws_ssm_parameter.ubuntu.insecure_value
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  iam_instance_profile   = aws_iam_instance_profile.node.name
  ebs_optimized          = true

  # IMDSv2 only. Hop limit 1 keeps the instance role out of reach of pods.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_gb
    encrypted             = true
    delete_on_termination = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    k3s_channel = var.k3s_channel
  })

  tags = { Name = var.name }

  lifecycle {
    # A newer AMI must not replace the node behind our back, and user data only ever runs
    # on first boot, so changing either is a deliberate `terraform apply -replace`.
    ignore_changes = [ami, user_data]
  }
}

resource "aws_eip_association" "node" {
  instance_id   = aws_instance.node.id
  allocation_id = aws_eip.node.id
}

# --- Deploy document: the only thing the GitHub deploy role may run on the node ---------------

resource "aws_ssm_document" "release" {
  name            = "${var.name}-release"
  document_type   = "Command"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Deploy a commit of Lotse to the demo node, or roll the release back"
    parameters = {
      action = {
        type          = "String"
        allowedValues = ["deploy", "rollback"]
        default       = "deploy"
      }
      sha = {
        type           = "String"
        description    = "Full commit SHA; also the image tag"
        allowedPattern = "^[0-9a-f]{40}$"
      }
    }
    mainSteps = [{
      action = "aws:runShellScript"
      name   = "release"
      inputs = {
        timeoutSeconds = "1200"
        # Both parameters are constrained above, so they are safe to place in the script.
        runCommand = concat(
          ["#!/bin/bash", "ACTION='{{ action }}'", "SHA='{{ sha }}'"],
          split("\n", templatefile("${path.module}/release.sh.tftpl", {
            region      = var.region
            registry    = var.registry
            host        = local.host
            secret_name = var.secret_name
          }))
        )
      }
    }]
  })
}

output "instance_id" {
  value = aws_instance.node.id
}

output "instance_arn" {
  value = aws_instance.node.arn
}

output "public_ip" {
  value = aws_eip.node.public_ip
}

output "host" {
  value = local.host
}

output "release_document_name" {
  value = aws_ssm_document.release.name
}

output "release_document_arn" {
  value = aws_ssm_document.release.arn
}
