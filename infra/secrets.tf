resource "aws_secretsmanager_secret" "db" {
  name = "${var.project}/database-url"
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  # Discrete fields, not a prebuilt DSN: the Lambda (Python/SQLAlchemy DSN)
  # and the Grafana EC2 host (Postgres datasource YAML) each need the parts
  # in a different shape, so building the connection string is left to each
  # consumer rather than baked in once here.
  secret_string = jsonencode({
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    dbname   = aws_db_instance.this.db_name
    username = aws_db_instance.this.username
    password = random_password.db.result
  })
}
