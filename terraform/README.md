# Terraform Deployment for Timesheet OCR

This directory contains Terraform configuration to deploy the Timesheet OCR system to AWS.

## Advantages Over SAM

✅ **No Circular Dependencies** - Terraform handles S3 bucket notifications correctly
✅ **Better State Management** - Track all infrastructure changes
✅ **Modular** - Clean separation of concerns
✅ **Reusable** - Easy to deploy to multiple environments
✅ **Drift Detection** - See what's changed outside Terraform

## Prerequisites

1. **Terraform installed** - Version >= 1.0
2. **AWS CLI configured** - With valid credentials
3. **Docker running** - For Lambda packaging
4. **SAM build completed** - Run `sam build` from project root first

## Quick Start

```bash
# 1. Navigate to terraform directory
cd terraform

# 2. Initialize Terraform
terraform init

# 3. Plan the deployment
terraform plan

# 4. Apply the changes
terraform apply

# 5. Get outputs
terraform output
```

## Deployment Steps

### 1. Build Lambda Functions

From the project root:

```bash
# Build with SAM (creates .aws-sam/build directory)
sam build
```

### 2. Initialize Terraform

```bash
cd terraform
terraform init
```

### 3. Review Plan

```bash
# See what will be created
terraform plan

# Or save the plan
terraform plan -out=tfplan
```

### 4. Deploy

```bash
# Apply the configuration
terraform apply

# Or use saved plan
terraform apply tfplan
```

### 5. Get Outputs

```bash
# Show all outputs
terraform output

# Get specific output
terraform output api_gateway_url
terraform output input_bucket_name
```

## Environment Configuration

Deploy to different environments:

```bash
# Development (default)
terraform apply -var="environment=dev"

# Staging
terraform apply -var="environment=staging"

# Production
terraform apply -var="environment=prod"
```

## Workspaces

Use Terraform workspaces for environment isolation:

```bash
# Create and switch to dev workspace
terraform workspace new dev
terraform workspace select dev
terraform apply -var="environment=dev"

# Create and switch to prod workspace
terraform workspace new prod
terraform workspace select prod
terraform apply -var="environment=prod"
```

## Custom Variables

Override default variables:

```bash
terraform apply \
  -var="environment=dev" \
  -var="aws_region=us-west-2" \
  -var="lambda_memory=2048" \
  -var="lambda_timeout=600"
```

Or create a `terraform.tfvars` file:

```hcl
environment    = "dev"
aws_region     = "us-east-1"
lambda_timeout = 300
lambda_memory  = 1024
```

## State Management

### Local State (Default)

State is stored in `terraform.tfstate` file locally.

### Remote State (Recommended for Production)

```hcl
# Add to main.tf
terraform {
  backend "s3" {
    bucket         = "my-terraform-state-bucket"
    key            = "timesheet-ocr/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

## Testing the Deployment

```bash
# Get outputs
API_URL=$(terraform output -raw api_gateway_url)
INPUT_BUCKET=$(terraform output -raw input_bucket_name)

# Test upload
aws s3 cp ../Screenshots/2025-10-20_15h54_43.png s3://$INPUT_BUCKET/

# Check logs
aws logs tail /aws/lambda/TimesheetOCR-ocr-dev --follow

# Test API
curl "$API_URL/resources"
open "$API_URL/report/Barry%20Breden/html"
```

## Updating the Deployment

After code changes:

```bash
# 1. Rebuild Lambda functions
cd ..
sam build

# 2. Apply changes
cd terraform
terraform apply
```

Terraform will detect changes in the Lambda function code and update only what changed.

## Destroying Resources

```bash
# Preview what will be destroyed
terraform plan -destroy

# Destroy all resources
terraform destroy

# Destroy specific resource
terraform destroy -target=aws_lambda_function.ocr
```

## Troubleshooting

### Issue: S3 bucket already exists

```bash
# Import existing bucket into Terraform state
terraform import aws_s3_bucket.input timesheetocr-input-dev-123456789012
```

### Issue: Lambda function code hasn't changed

```bash
# Force Lambda update
terraform taint aws_lambda_function.ocr
terraform apply
```

### Issue: API Gateway not updating

```bash
# Force redeployment
terraform taint aws_api_gateway_deployment.reports
terraform apply
```

## File Structure

```
terraform/
├── main.tf              # Provider and locals
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── dynamodb.tf          # DynamoDB table
├── s3.tf                # S3 buckets and notifications
├── iam.tf               # IAM roles and policies
├── lambda.tf            # Lambda functions
├── api_gateway.tf       # API Gateway configuration
└── README.md            # This file
```

## Resources Created

- **S3 Buckets**: Input and output buckets with encryption and lifecycle policies
- **DynamoDB Table**: Timesheet data with GSIs
- **Lambda Functions**: OCR and Report functions
- **IAM Roles**: Least-privilege roles for Lambda functions
- **API Gateway**: REST API with CORS enabled
- **CloudWatch Log Groups**: For Lambda logging
- **S3 Bucket Notifications**: Trigger OCR function on upload

## Security Best Practices

✅ Encryption at rest (S3, DynamoDB)
✅ Public access blocked on S3 buckets
✅ Least-privilege IAM policies
✅ CloudWatch logging enabled
✅ Versioning enabled on S3 buckets
✅ HTTPS-only API Gateway

## Cost Optimization

- Pay-per-request DynamoDB billing
- S3 lifecycle policies (IA and Glacier transitions)
- Lambda timeout and memory optimized
- CloudWatch log retention limits

## Next Steps

1. Set up remote state backend for production
2. Create separate workspaces for each environment
3. Add CloudWatch alarms (optional)
4. Set up backup/disaster recovery (optional)
5. Configure CI/CD pipeline with Terraform

## CI/CD Integration

Add to GitHub Actions:

```yaml
- name: Terraform Apply
  run: |
    cd terraform
    terraform init
    terraform apply -auto-approve
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Support

For issues, refer to:
- Terraform AWS Provider docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- Project documentation in parent directory
- Terraform plan output for detailed error messages
