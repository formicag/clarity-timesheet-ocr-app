# API Gateway REST API
resource "aws_api_gateway_rest_api" "reports" {
  name        = "TimesheetOCR-API-${var.environment}"
  description = "Timesheet reporting API"

  tags = local.common_tags
}

# /resources resource
resource "aws_api_gateway_resource" "resources" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_rest_api.reports.root_resource_id
  path_part   = "resources"
}

# GET /resources method
resource "aws_api_gateway_method" "get_resources" {
  rest_api_id   = aws_api_gateway_rest_api.reports.id
  resource_id   = aws_api_gateway_resource.resources.id
  http_method   = "GET"
  authorization = "NONE"
}

# Integration for GET /resources
resource "aws_api_gateway_integration" "get_resources" {
  rest_api_id             = aws_api_gateway_rest_api.reports.id
  resource_id             = aws_api_gateway_resource.resources.id
  http_method             = aws_api_gateway_method.get_resources.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.report.invoke_arn
}

# /report resource
resource "aws_api_gateway_resource" "report" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_rest_api.reports.root_resource_id
  path_part   = "report"
}

# /report/{resource_name} resource
resource "aws_api_gateway_resource" "report_resource" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.report.id
  path_part   = "{resource_name}"
}

# GET /report/{resource_name} method
resource "aws_api_gateway_method" "get_report" {
  rest_api_id   = aws_api_gateway_rest_api.reports.id
  resource_id   = aws_api_gateway_resource.report_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

# Integration for GET /report/{resource_name}
resource "aws_api_gateway_integration" "get_report" {
  rest_api_id             = aws_api_gateway_rest_api.reports.id
  resource_id             = aws_api_gateway_resource.report_resource.id
  http_method             = aws_api_gateway_method.get_report.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.report.invoke_arn
}

# /report/{resource_name}/html resource
resource "aws_api_gateway_resource" "report_html" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.report_resource.id
  path_part   = "html"
}

# GET /report/{resource_name}/html method
resource "aws_api_gateway_method" "get_report_html" {
  rest_api_id   = aws_api_gateway_rest_api.reports.id
  resource_id   = aws_api_gateway_resource.report_html.id
  http_method   = "GET"
  authorization = "NONE"
}

# Integration for GET /report/{resource_name}/html
resource "aws_api_gateway_integration" "get_report_html" {
  rest_api_id             = aws_api_gateway_rest_api.reports.id
  resource_id             = aws_api_gateway_resource.report_html.id
  http_method             = aws_api_gateway_method.get_report_html.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.report.invoke_arn
}

# API Gateway deployment
resource "aws_api_gateway_deployment" "reports" {
  rest_api_id = aws_api_gateway_rest_api.reports.id

  depends_on = [
    aws_api_gateway_integration.get_resources,
    aws_api_gateway_integration.get_report,
    aws_api_gateway_integration.get_report_html
  ]

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.resources.id,
      aws_api_gateway_method.get_resources.id,
      aws_api_gateway_integration.get_resources.id,
      aws_api_gateway_resource.report_resource.id,
      aws_api_gateway_method.get_report.id,
      aws_api_gateway_integration.get_report.id,
      aws_api_gateway_resource.report_html.id,
      aws_api_gateway_method.get_report_html.id,
      aws_api_gateway_integration.get_report_html.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway stage
resource "aws_api_gateway_stage" "reports" {
  deployment_id = aws_api_gateway_deployment.reports.id
  rest_api_id   = aws_api_gateway_rest_api.reports.id
  stage_name    = var.environment

  tags = local.common_tags
}

# Lambda permission for API Gateway to invoke report function
resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.report.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.reports.execution_arn}/*/*"
}

# Enable CORS for all methods
resource "aws_api_gateway_method" "options_resources" {
  rest_api_id   = aws_api_gateway_rest_api.reports.id
  resource_id   = aws_api_gateway_resource.resources.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_resources" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  resource_id = aws_api_gateway_resource.resources.id
  http_method = aws_api_gateway_method.options_resources.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_resources" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  resource_id = aws_api_gateway_resource.resources.id
  http_method = aws_api_gateway_method.options_resources.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_resources" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  resource_id = aws_api_gateway_resource.resources.id
  http_method = aws_api_gateway_method.options_resources.http_method
  status_code = aws_api_gateway_method_response.options_resources.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}
