output "ecr_repository_url" {
  value       = aws_ecr_repository.ingest.repository_url
  description = "Push the Lambda image here (see Dockerfile.lambda), then set lambda_image_uri and re-apply."
}

output "lambda_function_name" {
  value = aws_lambda_function.ingest.function_name
}

output "rds_endpoint" {
  value = aws_db_instance.this.endpoint
}

output "db_secret_arn" {
  value = aws_secretsmanager_secret.db.arn
}

output "grafana_url" {
  value = "http://${aws_instance.grafana.public_ip}:3000"
}
