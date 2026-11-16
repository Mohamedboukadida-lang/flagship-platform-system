# Runbook: first deployment of the demo

Status: written from the Terraform and chart in this repository, **never executed**. Expect to fix things on the first run and record them in `docs/what-broke.md`.

Rules: never use root credentials. Read every `terraform plan` before `apply`. Nothing here is run by CI except the last step.

## What it costs

One `t3.medium` with a 30 GB disk and an Elastic IP: roughly 40 USD a month running all the time, far less if stopped outside demo hours (the disk and the address still cost a little). A budget alarm emails at 80 percent of `monthly_budget_usd` (default 30).

## 1. State bucket (once per AWS account)

```bash
terraform -chdir=deploy/terraform/bootstrap init
```

```bash
terraform -chdir=deploy/terraform/bootstrap apply
```

Note the `state_bucket` output. This directory keeps local state: do not delete `terraform.tfstate` there, and never destroy this root.

## 2. Infrastructure

```bash
cp deploy/terraform/envs/demo/terraform.tfvars.example deploy/terraform/envs/demo/terraform.tfvars
```

Edit `terraform.tfvars`: your alert email, and `existing_github_oidc_provider_arn` if the account already has the GitHub OIDC provider (an account can hold only one; another project may have created it).

```bash
terraform -chdir=deploy/terraform/envs/demo init -backend-config="bucket=<state_bucket>"
```

```bash
terraform -chdir=deploy/terraform/envs/demo plan -out demo.tfplan
```

```bash
terraform -chdir=deploy/terraform/envs/demo apply demo.tfplan
```

Commit the `.terraform.lock.hcl` files that `init` creates. The node installs k3s on first boot, which takes a few minutes; the log is `/var/log/lotse-bootstrap.log` on the node (reach it with Session Manager).

## 3. Application secret

Terraform creates the secret empty so that no password enters the state. Fill it once with six generated values. They go into URLs, so use hex:

```bash
python3 - <<'PY' > /tmp/lotse-secret.json
import json, secrets
keys = ["POSTGRES_PASSWORD", "LOTSE_APP_DB_PASSWORD", "LOTSE_PLATFORM_DB_PASSWORD",
        "KEYCLOAK_DB_PASSWORD", "KEYCLOAK_ADMIN_PASSWORD", "LOTSE_DEMO_PASSWORD"]
print(json.dumps({k: secrets.token_hex(16) for k in keys}))
PY
```

```bash
aws secretsmanager put-secret-value --secret-id lotse-demo/app --secret-string file:///tmp/lotse-secret.json
```

```bash
rm /tmp/lotse-secret.json
```

The database passwords take effect when Postgres first starts. Changing them later means changing them in Postgres too.

## 4. GitHub settings

Repository variables (Settings, Secrets and variables, Actions, Variables), from `terraform output`:

| Variable | Terraform output |
| --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | `deploy_role_arn` |
| `NODE_INSTANCE_ID` | `node_instance_id` |
| `RELEASE_DOCUMENT` | `release_document` |
| `DEMO_HOST` | `demo_host` |

Create an environment named `demo` (Settings, Environments). Limit its deployment branches to `main` and add yourself as a required reviewer. The AWS role trusts this environment only. Optionally add an environment secret `DEMO_PASSWORD` with the value of `LOTSE_DEMO_PASSWORD`: the smoke test then also logs in.

## 5. Deploy

Every push to `main` that passes `ci` starts `deploy`, which waits for your approval. To check from your machine afterwards:

```bash
deploy/smoke.sh "https://<demo_host>"
```

The M0 exit gate is met when this prints that a user logged in and got their tenant (run it with `SMOKE_PASSWORD` set).

## Stop and start

```bash
aws ec2 stop-instances --instance-ids <node_instance_id>
```

```bash
aws ec2 start-instances --instance-ids <node_instance_id>
```

The address, the disk and the cluster state survive. Pods restart from images cached on the node.

## Tear down

```bash
terraform -chdir=deploy/terraform/envs/demo destroy
```

This deletes the node and its database. ECR repositories that still hold images block the destroy; empty them first. Never destroy `bootstrap`.

## Known limits

- The registry pull secret lasts 12 hours. A pod that restarts later starts from the image cached on the node; if the cache was pruned, run a deploy to refresh the secret.
- The k3s channel and the cert-manager chart are not pinned to exact versions yet.
- No HTTP to HTTPS redirect yet.
- No database backups yet (M1). The demo holds seed data only.
