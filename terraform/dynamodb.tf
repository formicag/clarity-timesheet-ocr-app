# DynamoDB Table for Timesheet Data
resource "aws_dynamodb_table" "timesheets" {
  name           = local.table_name
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "ResourceName"
  range_key      = "DateProjectCode"

  attribute {
    name = "ResourceName"
    type = "S"
  }

  attribute {
    name = "DateProjectCode"
    type = "S"
  }

  attribute {
    name = "ProjectCodeGSI"
    type = "S"
  }

  attribute {
    name = "YearMonth"
    type = "S"
  }

  # GSI for querying by project code
  global_secondary_index {
    name            = "ProjectCodeIndex"
    hash_key        = "ProjectCodeGSI"
    range_key       = "DateProjectCode"
    projection_type = "ALL"
  }

  # GSI for querying by year/month
  global_secondary_index {
    name            = "YearMonthIndex"
    hash_key        = "YearMonth"
    range_key       = "ResourceName"
    projection_type = "ALL"
  }

  # Point-in-time recovery for production
  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  # Server-side encryption
  server_side_encryption {
    enabled = true
  }

  tags = merge(local.common_tags, {
    Name = local.table_name
  })
}
