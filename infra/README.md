# Deploying

Terraform in this directory provisions: RDS Postgres, the ingestion Lambda
(container image) + EventBridge Scheduler, Secrets Manager, ECR, and a small
EC2 host running Grafana. It does **not** create a VPC/subnets — bring your own
(`var.vpc_id`, `var.private_subnet_ids`, `var.grafana_subnet_id`).

Not yet run against real AWS from this environment — no AWS credentials or
`terraform` CLI were available here (installing `terraform` needed elevated
permissions this environment didn't have). Review the `.tf` files and run
`terraform validate`/`plan` yourself before `apply`.

## Prerequisites

- An existing VPC with private subnets that have outbound internet access
  (NAT gateway or NAT instance) — the Lambda needs to reach lender websites,
  and Secrets Manager/ECR.
- A public (or VPN-reachable) subnet for the Grafana host.
- Docker, for building the Lambda image.

## 1. Build and push the Lambda image

Building is deliberately a manual/CI step, not something `terraform apply`
does — image builds belong in CI, not infra state.

```bash
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com

# First apply (below) to create the ECR repo, or reference an existing one.
docker build -f Dockerfile.lambda -t <ecr_repo_url>:latest .
docker push <ecr_repo_url>:latest
```

## 2. Apply

```bash
cd infra
terraform init
terraform apply \
  -var vpc_id=vpc-xxxx \
  -var 'private_subnet_ids=["subnet-aaa","subnet-bbb"]' \
  -var grafana_subnet_id=subnet-ccc \
  -var grafana_allowed_cidr=1.2.3.4/32 \
  -var lambda_image_uri=<account>.dkr.ecr.<region>.amazonaws.com/mortgage-rates-ingest:latest
```

First apply creates the ECR repo (empty) — build/push the image (step 1), then
`terraform apply` again so the Lambda points at a real image.

## 3. Verify

```bash
aws lambda invoke --function-name mortgage-rates-ingest out.json && cat out.json
```

Then open the Grafana URL from `terraform output grafana_url` (default admin
password is `admin` — change it) and confirm the "Mortgage Rates Overview"
dashboard shows data.

## Notes

- `skip_final_snapshot = true` on the RDS instance is a dev-friendly default
  so `terraform destroy` doesn't hang on a snapshot name — turn it off before
  tearing down a real prod DB.
- The Lambda resolves its DB connection string from Secrets Manager at cold
  start (`DB_SECRET_ARN` env var — see `handler.py`), not from a plaintext
  Lambda environment variable.
- `var.schedule_expression` defaults to `cron(0 13 * * ? *)` (13:00 UTC).
  Adjust to your preferred run time.
