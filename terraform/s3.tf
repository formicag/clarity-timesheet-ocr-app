# Input S3 Bucket (for timesheet images)
resource "aws_s3_bucket" "input" {
  bucket = local.input_bucket

  tags = merge(local.common_tags, {
    Name            = "TimesheetOCR Input Bucket"
    DataClassification = "Internal"
  })
}

# Input bucket versioning
resource "aws_s3_bucket_versioning" "input" {
  bucket = aws_s3_bucket.input.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Input bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "input" {
  bucket = aws_s3_bucket.input.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Input bucket public access block
resource "aws_s3_bucket_public_access_block" "input" {
  bucket = aws_s3_bucket.input.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Input bucket lifecycle
resource "aws_s3_bucket_lifecycle_configuration" "input" {
  bucket = aws_s3_bucket.input.id

  rule {
    id     = "DeleteOldImages"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# S3 bucket notification - configured AFTER Lambda is created
# This avoids the circular dependency
resource "aws_s3_bucket_notification" "input" {
  bucket = aws_s3_bucket.input.id

  # Depends on Lambda permission being created first
  depends_on = [aws_lambda_permission.s3_invoke]

  lambda_function {
    lambda_function_arn = aws_lambda_function.ocr.arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".png"
  }

  lambda_function {
    lambda_function_arn = aws_lambda_function.ocr.arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".jpg"
  }
}

# Output S3 Bucket (for CSV/JSON results)
resource "aws_s3_bucket" "output" {
  bucket = local.output_bucket

  tags = merge(local.common_tags, {
    Name = "TimesheetOCR Output Bucket"
  })
}

# Output bucket versioning
resource "aws_s3_bucket_versioning" "output" {
  bucket = aws_s3_bucket.output.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Output bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "output" {
  bucket = aws_s3_bucket.output.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Output bucket public access block
resource "aws_s3_bucket_public_access_block" "output" {
  bucket = aws_s3_bucket.output.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Output bucket lifecycle
resource "aws_s3_bucket_lifecycle_configuration" "output" {
  bucket = aws_s3_bucket.output.id

  rule {
    id     = "TransitionToIA"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }
  }
}
