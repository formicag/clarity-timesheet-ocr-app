# Data source to get the built Lambda code
data "archive_file" "ocr_lambda" {
  type        = "zip"
  source_dir  = "../.aws-sam/build/OCRFunction"
  output_path = "${path.module}/ocr-function.zip"
}

data "archive_file" "report_lambda" {
  type        = "zip"
  source_dir  = "../.aws-sam/build/ReportFunction"
  output_path = "${path.module}/report-function.zip"
}

# OCR Lambda Function
resource "aws_lambda_function" "ocr" {
  function_name = local.function_name
  role          = aws_iam_role.ocr_lambda.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.13"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  filename         = data.archive_file.ocr_lambda.output_path
  source_code_hash = data.archive_file.ocr_lambda.output_base64sha256

  environment {
    variables = {
      OUTPUT_BUCKET   = aws_s3_bucket.output.id
      DYNAMODB_TABLE  = aws_dynamodb_table.timesheets.name
      MODEL_ID        = var.model_id
      MAX_TOKENS      = tostring(var.max_tokens)
      ENVIRONMENT     = var.environment
    }
  }

  tags = merge(local.common_tags, {
    Name = local.function_name
  })

  depends_on = [
    aws_iam_role_policy_attachment.ocr_lambda_basic,
    aws_iam_role_policy.ocr_lambda_custom
  ]
}

# CloudWatch Log Group for OCR Lambda
resource "aws_cloudwatch_log_group" "ocr_lambda" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.environment == "prod" ? 90 : 30

  tags = local.common_tags
}

# Lambda permission for S3 to invoke OCR function
resource "aws_lambda_permission" "s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ocr.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.input.arn
  source_account = local.account_id
}

# Report Lambda Function
resource "aws_lambda_function" "report" {
  function_name = local.report_function_name
  role          = aws_iam_role.report_lambda.arn
  handler       = "report_lambda.lambda_handler"
  runtime       = "python3.13"
  timeout       = 30
  memory_size   = 512

  filename         = data.archive_file.report_lambda.output_path
  source_code_hash = data.archive_file.report_lambda.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.timesheets.name
      ENVIRONMENT    = var.environment
    }
  }

  tags = merge(local.common_tags, {
    Name = local.report_function_name
  })

  depends_on = [
    aws_iam_role_policy_attachment.report_lambda_basic,
    aws_iam_role_policy.report_lambda_custom
  ]
}

# CloudWatch Log Group for Report Lambda
resource "aws_cloudwatch_log_group" "report_lambda" {
  name              = "/aws/lambda/${local.report_function_name}"
  retention_in_days = var.environment == "prod" ? 90 : 30

  tags = local.common_tags
}
