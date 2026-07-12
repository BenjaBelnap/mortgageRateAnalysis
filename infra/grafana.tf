data "aws_ami" "al2023_arm64" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-kernel-*-arm64"]
  }
}

resource "aws_security_group" "grafana" {
  name        = "${var.project}-grafana"
  description = "Grafana host: dashboard access from a narrow CIDR only"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.grafana_allowed_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "grafana" {
  name = "${var.project}-grafana"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "grafana_secrets" {
  name = "${var.project}-grafana-secrets"
  role = aws_iam_role.grafana.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.db.arn]
    }]
  })
}

resource "aws_iam_instance_profile" "grafana" {
  name = "${var.project}-grafana"
  role = aws_iam_role.grafana.name
}

resource "aws_instance" "grafana" {
  ami                         = data.aws_ami.al2023_arm64.id
  instance_type               = "t4g.micro"
  subnet_id                   = var.grafana_subnet_id
  vpc_security_group_ids      = [aws_security_group.grafana.id]
  iam_instance_profile        = aws_iam_instance_profile.grafana.name
  associate_public_ip_address = true

  user_data = templatefile("${path.module}/templates/grafana_user_data.sh.tpl", {
    db_secret_arn            = aws_secretsmanager_secret.db.arn
    aws_region               = var.aws_region
    db_host                  = aws_db_instance.this.address
    db_port                  = aws_db_instance.this.port
    db_name                  = aws_db_instance.this.db_name
    db_user                  = aws_db_instance.this.username
    dashboards_provider_yaml = file("${path.module}/grafana/provisioning/dashboards/dashboards.yaml")
    dashboard_json           = file("${path.module}/grafana/dashboards/mortgage_rates.json")
  })

  tags = {
    Name = "${var.project}-grafana"
  }
}
