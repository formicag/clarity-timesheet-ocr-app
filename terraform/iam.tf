# IAM Role for OCR Lambda Function
resource "aws_iam_role" "ocr_lambda" {
  name = "TimesheetOCR-OCRLambda-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = local.common_tags
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "ocr_lambda_basic" {
  role       = aws_iam_role.ocr_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Custom policy for OCR Lambda
resource "aws_iam_role_policy" "ocr_lambda_custom" {
  name = "TimesheetOCR-OCRPolicy-${var.environment}"
  role = aws_iam_role.ocr_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.input.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.output.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.timesheets.arn,
          "${aws_dynamodb_table.timesheets.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:${local.region}::foundation-model/${var.model_id}",
          "arn:aws:bedrock:${local.region}::foundation-model/anthropic.claude-*"
        ]
      }
    ]
  })
}

# IAM Role for Report Lambda Function
resource "aws_iam_role" "report_lambda" {
  name = "TimesheetOCR-ReportLambda-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = local.common_tags
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "report_lambda_basic" {
  role       = aws_iam_role.report_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Custom policy for Report Lambda
resource "aws_iam_role_policy" "report_lambda_custom" {
  name = "TimesheetOCR-ReportPolicy-${var.environment}"
  role = aws_iam_role.report_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.timesheets.arn,
          "${aws_dynamodb_table.timesheets.arn}/index/*"
        ]
      }
    ]
  })
}
