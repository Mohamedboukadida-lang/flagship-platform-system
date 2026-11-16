# The container for the application secrets. The value is set out of band (see
# docs/runbooks/demo-deploy.md) so that no secret ever enters Terraform state.

variable "name" {
  type = string
}

resource "aws_secretsmanager_secret" "app" {
  #checkov:skip=CKV_AWS_149:The AWS-managed key is enough; a customer key adds a monthly cost
  #checkov:skip=CKV2_AWS_57:These are database passwords inside the cluster; rotation is a runbook step
  name                    = "${var.name}/app"
  description             = "Lotse application secrets: one JSON object, keys listed in the chart's values.yaml"
  recovery_window_in_days = 7
}

output "arn" {
  value = aws_secretsmanager_secret.app.arn
}

output "name" {
  value = aws_secretsmanager_secret.app.name
}
