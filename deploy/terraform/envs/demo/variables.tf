variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "availability_zone" {
  description = "Pinned, so the subnet never moves when AWS adds a zone"
  type        = string
  default     = "eu-central-1a"
}

variable "name" {
  description = "Prefix for every resource name"
  type        = string
  default     = "lotse-demo"
}

variable "github_repo" {
  description = "owner/name of the repository allowed to deploy, with GitHub's exact casing"
  type        = string
}

variable "existing_github_oidc_provider_arn" {
  description = "Set this if the account already has the GitHub OIDC provider (only one can exist)"
  type        = string
  default     = null
}

variable "domain_name" {
  description = "Public hostname of the demo. Empty: use <elastic-ip>.sslip.io"
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Hosted zone to create the A record for domain_name in. Empty: manage DNS yourself"
  type        = string
  default     = ""
}

variable "instance_type" {
  description = "4 GiB is the floor for k3s, Postgres, Keycloak and the API together"
  type        = string
  default     = "t3.medium"
}

variable "root_volume_gb" {
  type    = number
  default = 30
}

variable "k3s_channel" {
  type    = string
  default = "stable"
}

variable "monthly_budget_usd" {
  type    = number
  default = 30
}

variable "alert_email" {
  description = "Receives the budget alerts. Lives in terraform.tfvars, which is not committed"
  type        = string
}
