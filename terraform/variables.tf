variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod"
  }
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 300
}

variable "lambda_memory" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 1024
}

variable "model_id" {
  description = "Bedrock model ID for OCR"
  type        = string
  default     = "us.anthropic.claude-sonnet-4-5-v1:0"
}

variable "max_tokens" {
  description = "Maximum tokens for Claude response"
  type        = number
  default     = 4096
}
