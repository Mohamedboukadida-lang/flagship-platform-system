# The demo environment: one k3s node in eu-central-1 and what it needs to be deployed to.
# The object store, the KMS key and the backup bucket join with the milestones that use them.

data "aws_caller_identity" "current" {}

locals {
  # The bucket itself, with its policy and the pods' access to it, lands with M1 slice 10.
  # The API only needs the name to start.
  files_bucket = "${var.name}-files-${data.aws_caller_identity.current.account_id}"
}

module "network" {
  source            = "../../modules/network"
  name              = var.name
  availability_zone = var.availability_zone
}

module "registry" {
  source       = "../../modules/registry"
  repositories = ["lotse-api", "charts/lotse"]
}

module "secrets" {
  source = "../../modules/secrets"
  name   = var.name
}

module "node" {
  source              = "../../modules/node"
  name                = var.name
  region              = var.region
  subnet_id           = module.network.subnet_id
  security_group_id   = module.network.security_group_id
  instance_type       = var.instance_type
  root_volume_gb      = var.root_volume_gb
  domain_name         = var.domain_name
  k3s_channel         = var.k3s_channel
  registry            = module.registry.registry
  ecr_repository_arns = module.registry.repository_arns
  secret_arn          = module.secrets.arn
  secret_name         = module.secrets.name
  files_bucket        = local.files_bucket
}

module "github_oidc" {
  source                = "../../modules/github_oidc"
  name                  = var.name
  github_repo           = var.github_repo
  github_environment    = "demo"
  existing_provider_arn = var.existing_github_oidc_provider_arn
  ecr_repository_arns   = module.registry.repository_arns
  instance_arn          = module.node.instance_arn
  deploy_document_arn   = module.node.release_document_arn
}

resource "aws_route53_record" "demo" {
  count   = var.route53_zone_id != "" && var.domain_name != "" ? 1 : 0
  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [module.node.public_ip]
}

# Whole account on purpose: a tag filter only counts tags activated for cost allocation,
# and an alarm that silently tracks nothing is worse than a broad one.
resource "aws_budgets_budget" "monthly" {
  name         = "${var.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
