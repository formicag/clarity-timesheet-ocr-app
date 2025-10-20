terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Data source for AWS region
data "aws_region" "current" {}

# Local variables
locals {
  account_id       = data.aws_caller_identity.current.account_id
  region          = data.aws_region.current.name
  function_name   = "TimesheetOCR-ocr-${var.environment}"
  report_function_name = "TimesheetOCR-report-${var.environment}"
  table_name      = "TimesheetOCR-${var.environment}"
  input_bucket    = "timesheetocr-input-${var.environment}-${local.account_id}"
  output_bucket   = "timesheetocr-output-${var.environment}-${local.account_id}"

  common_tags = {
    Project     = "TimesheetOCR"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
