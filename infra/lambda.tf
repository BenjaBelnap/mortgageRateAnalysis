resource "aws_security_group" "lambda" {
  name        = "${var.project}-lambda"
  description = "Ingestion Lambda: outbound only (scrapes lender sites, writes to RDS)"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "lambda" {
  name = "${var.project}-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "lambda_secrets" {
  name = "${var.project}-lambda-secrets"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.db.arn]
    }]
  })
}

resource "aws_lambda_function" "ingest" {
  function_name = "${var.project}-ingest"
  role          = aws_iam_role.lambda.arn

  package_type = "Image"
  image_uri    = var.lambda_image_uri

  timeout     = 60 # lightweight job: a handful of HTTP fetches + upserts, not a batch workload
  memory_size = 256

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DB_SECRET_ARN            = aws_secretsmanager_secret.db.arn
      MORTGAGE_RATES_LOG_LEVEL = "INFO"
    }
  }
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.ingest.function_name}"
  retention_in_days = var.log_retention_days
}
