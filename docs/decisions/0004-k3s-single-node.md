# 0004: k3s on one instance for the demo; path to EKS

Status: accepted, 2026-11-16 (M0). Written but not yet applied to an AWS account.

## Decision

The demo runs on one EC2 instance with k3s in `eu-central-1`, provisioned by Terraform and deployed with the Helm chart in `deploy/helm/lotse`. Postgres, Redis and Keycloak run in the cluster.

## Why

Real Kubernetes and real Terraform at the cost of one small instance. A managed control plane and a managed database each add a fixed monthly cost that a demo does not justify.

## Alternatives

- EKS and RDS from day one: the production shape, at several times the cost.
- Docker Compose on a VM: cheaper still, but the chart would never be exercised.

## How deployment works

1. GitHub Actions assumes an AWS role through OIDC. The role trusts one repository and one GitHub environment (`demo`), and may do two things: push to this project's ECR repositories and run one Systems Manager document on the node.
2. The workflow pushes the image and the chart to ECR, both tagged with the commit SHA. Tags are immutable.
3. The Systems Manager document runs on the node: it copies the application secret from Secrets Manager into the cluster, refreshes the registry credentials and runs `helm upgrade --install --atomic`.
4. A smoke test runs against the public URL; if it fails, the same document rolls the release back.

The node has no SSH and no inbound port besides 80 and 443.

## Deviations from the spec, on purpose

- The spec's trust policy matched a branch ref, but a job that names an environment presents `repo:<owner>/<repo>:environment:<name>`. The role trusts that subject; restricting the environment to `main` is a repository setting.
- The deploy role runs a fixed document with two validated parameters instead of `AWS-RunShellScript`, which would let it run anything as root.
- The release script syncs the secret itself. External Secrets Operator can replace that later; it is one more operator on a 4 GiB node.
- The instance metadata hop limit is 1, so pods cannot use the instance role. Pods need no AWS access in M0. This changes when uploads to S3 arrive (M1).
- The object store, the KMS key and the backup bucket are not created yet. They join with the milestones that use them.

## Path to EKS

The chart already separates the stores behind switches (`postgres.enabled`, `redis.enabled`, `keycloak.enabled`) and takes external hosts. Moving to EKS and RDS means a new Terraform environment next to `envs/demo`, not a rewrite.

## Consequences

One node is a single point of failure and its disk holds the database: acceptable for a demo with seed data, not for real tenants. Backups start with M1.
