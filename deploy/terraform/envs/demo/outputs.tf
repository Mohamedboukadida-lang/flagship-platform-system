# Copy these into the GitHub repository variables (Settings > Secrets and variables > Actions).

output "demo_host" {
  description = "GitHub variable DEMO_HOST"
  value       = module.node.host
}

output "node_instance_id" {
  description = "GitHub variable NODE_INSTANCE_ID"
  value       = module.node.instance_id
}

output "release_document" {
  description = "GitHub variable RELEASE_DOCUMENT"
  value       = module.node.release_document_name
}

output "deploy_role_arn" {
  description = "GitHub variable AWS_DEPLOY_ROLE_ARN"
  value       = module.github_oidc.deploy_role_arn
}

output "secret_name" {
  description = "Secrets Manager secret to fill before the first deploy"
  value       = module.secrets.name
}

output "public_ip" {
  value = module.node.public_ip
}
