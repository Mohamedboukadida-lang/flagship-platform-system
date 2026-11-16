# ECR repositories. Tags are immutable: an image or chart version, once pushed, never changes.

variable "repositories" {
  type = set(string)
}

resource "aws_ecr_repository" "this" {
  #checkov:skip=CKV_AWS_136:Default AES-256 encryption is enough; the source is public anyway
  for_each             = var.repositories
  name                 = each.value
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 20 versions"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 20 }
      action       = { type = "expire" }
    }]
  })
}

output "repository_arns" {
  value = [for r in aws_ecr_repository.this : r.arn]
}

output "registry" {
  description = "Registry host, e.g. <account>.dkr.ecr.eu-central-1.amazonaws.com"
  value       = split("/", values(aws_ecr_repository.this)[0].repository_url)[0]
}
