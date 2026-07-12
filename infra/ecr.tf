resource "aws_ecr_repository" "ingest" {
  name                 = "${var.project}-ingest"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}
