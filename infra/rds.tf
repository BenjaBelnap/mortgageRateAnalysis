resource "random_password" "db" {
  length  = 24
  special = false # avoid characters that need URL-encoding in a DSN
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.project}-db"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "rds" {
  name        = "${var.project}-rds"
  description = "Allow Postgres from the ingestion Lambda and Grafana only"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "rds_from_lambda" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds.id
  source_security_group_id = aws_security_group.lambda.id
}

resource "aws_security_group_rule" "rds_from_grafana" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds.id
  source_security_group_id = aws_security_group.grafana.id
}

resource "aws_db_instance" "this" {
  identifier     = "${var.project}-db"
  engine         = "postgres"
  engine_version = "16"

  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage_gb
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "mortgage_rates"
  username = "mortgage_rates"
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  multi_az                = false # keep this cheap; the daily job can retry on a transient outage
  backup_retention_period = 7
  apply_immediately       = true

  # NOTE: skip_final_snapshot=true is a dev-friendly default so `terraform
  # destroy` doesn't hang waiting for a snapshot name. Set this to false
  # (and set final_snapshot_identifier) before tearing down a real prod DB.
  skip_final_snapshot = true
}
