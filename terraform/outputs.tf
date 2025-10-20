output "input_bucket_name" {
  description = "Name of the S3 input bucket"
  value       = aws_s3_bucket.input.id
}

output "output_bucket_name" {
  description = "Name of the S3 output bucket"
  value       = aws_s3_bucket.output.id
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.timesheets.name
}

output "ocr_function_name" {
  description = "Name of the OCR Lambda function"
  value       = aws_lambda_function.ocr.function_name
}

output "ocr_function_arn" {
  description = "ARN of the OCR Lambda function"
  value       = aws_lambda_function.ocr.arn
}

output "report_function_name" {
  description = "Name of the Report Lambda function"
  value       = aws_lambda_function.report.function_name
}

output "report_function_arn" {
  description = "ARN of the Report Lambda function"
  value       = aws_lambda_function.report.arn
}

output "api_gateway_url" {
  description = "Base URL for API Gateway"
  value       = "${aws_api_gateway_stage.reports.invoke_url}"
}

output "api_gateway_id" {
  description = "ID of the API Gateway"
  value       = aws_api_gateway_rest_api.reports.id
}

output "deployment_info" {
  description = "Deployment information"
  value = {
    environment      = var.environment
    region          = local.region
    account_id      = local.account_id
    input_bucket    = aws_s3_bucket.input.id
    output_bucket   = aws_s3_bucket.output.id
    dynamodb_table  = aws_dynamodb_table.timesheets.name
    api_url         = "${aws_api_gateway_stage.reports.invoke_url}"
  }
}
