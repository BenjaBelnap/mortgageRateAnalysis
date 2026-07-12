variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "project" {
  type    = string
  default = "mortgage-rates"
}

variable "vpc_id" {
  type        = string
  description = "Existing VPC to deploy into. This module does not create networking."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets (with NAT/VPC endpoints for internet-bound scraping + AWS APIs) for RDS and the Lambda."
}

variable "grafana_subnet_id" {
  type        = string
  description = "Subnet for the Grafana EC2 host. Public subnet unless you're fronting it with a VPN/ALB."
}

variable "grafana_allowed_cidr" {
  type        = string
  description = "CIDR allowed to reach Grafana on port 3000 (e.g. your office/home IP as x.x.x.x/32). Kept narrow since this is a small, cheap deployment, not a public service."
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 20
}

variable "lambda_image_uri" {
  type        = string
  description = "Full ECR image URI:tag for the Lambda, e.g. built and pushed via Dockerfile.lambda. Left as a variable rather than built by Terraform — image builds belong in CI, not in `terraform apply`."
}

variable "schedule_expression" {
  type        = string
  default     = "cron(0 13 * * ? *)"
  description = "EventBridge Scheduler cron, UTC. Default 13:00 UTC (~7am Mountain), after lenders typically post daily rates."
}

variable "log_retention_days" {
  type    = number
  default = 14
}
