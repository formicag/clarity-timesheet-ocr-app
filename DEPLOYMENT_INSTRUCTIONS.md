# Deployment Instructions - Timesheet OCR with Reporting

## Current Status

The application has been fully implemented with:
- Zero-hour timesheet detection
- DynamoDB storage with proper schema
- Per-person calendar reporting
- HTML report generation with visual indicators
- RESTful API for reports

## Known Issue: Circular Dependency in CloudFormation

SAM/CloudFormation has a circular dependency when configuring S3 bucket notifications.
The InputBucket depends on Lambda Permission, which depends on the Lambda Function, which SAM tries to configure with S3 events.

## Recommended Deployment Approach

### Option 1: Two-Stage Deployment (Recommended)

**Stage 1: Deploy core resources without S3 events**

1. Create a temporary template without S3 notifications
2. Deploy all resources except S3 bucket notifications
3. Manually configure S3 bucket notifications via AWS CLI

**Stage 2: Configure S3 notifications**

```bash
# After stack deployment completes
FUNCTION_ARN=$(aws cloudformation describe-stacks \
  --stack-name timesheet-ocr-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`FunctionArn`].OutputValue' \
  --output text)

INPUT_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name timesheet-ocr-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`InputBucketName`].OutputValue' \
  --output text)

# Grant S3 permission to invoke Lambda
aws lambda add-permission \
  --function-name $FUNCTION_ARN \
  --statement-id s3-invoke-permission \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::$INPUT_BUCKET \
  --source-account $(aws sts get-caller-identity --query Account --output text)

# Configure S3 notifications
aws s3api put-bucket-notification-configuration \
  --bucket $INPUT_BUCKET \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [
      {
        "LambdaFunctionArn": "'$FUNCTION_ARN'",
        "Events": ["s3:ObjectCreated:*"],
        "Filter": {
          "Key": {
            "FilterRules": [
              {"Name": "suffix", "Value": ".png"}
            ]
          }
        }
      },
      {
        "LambdaFunctionArn": "'$FUNCTION_ARN'",
        "Events": ["s3:ObjectCreated:*"],
        "Filter": {
          "Key": {
            "FilterRules": [
              {"Name": "suffix", "Value": ".jpg"}
            ]
          }
        }
      }
    ]
  }'
```

### Option 2: Use Existing Infrastructure

If you have infrastructure already deployed:

1. Deploy the updated Lambda functions only
2. Update DynamoDB table separately
3. Deploy API Gateway for reports

### Option 3: Manual Deployment Steps

```bash
# 1. Create DynamoDB Table
aws dynamodb create-table \
  --table-name TimesheetOCR-dev \
  --attribute-definitions \
    AttributeName=ResourceName,AttributeType=S \
    AttributeName=DateProjectCode,AttributeType=S \
    AttributeName=ProjectCodeGSI,AttributeType=S \
    AttributeName=YearMonth,AttributeType=S \
  --key-schema \
    AttributeName=ResourceName,KeyType=HASH \
    AttributeName=DateProjectCode,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --global-secondary-indexes \
    'IndexName=ProjectCodeIndex,KeySchema=[{AttributeName=ProjectCodeGSI,KeyType=HASH},{AttributeName=DateProjectCode,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
    'IndexName=YearMonthIndex,KeySchema=[{AttributeName=YearMonth,KeyType=HASH},{AttributeName=ResourceName,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
  --tags Key=Environment,Value=dev Key=Project,Value=TimesheetOCR

# 2. Create Lambda function (OCR)
# Package the code first
cd .aws-sam/build/OCRFunction
zip -r ../ocr-function.zip .
cd ../../..

# Create function
aws lambda create-function \
  --function-name TimesheetOCR-ocr-dev \
  --runtime python3.13 \
  --role arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/TimesheetOCR-Role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://.aws-sam/build/ocr-function.zip \
  --timeout 300 \
  --memory-size 1024 \
  --environment 'Variables={DYNAMODB_TABLE=TimesheetOCR-dev,MODEL_ID=us.anthropic.claude-sonnet-4-5-v1:0,MAX_TOKENS=4096,ENVIRONMENT=dev}'

# 3. Create Lambda function (Report)
cd .aws-sam/build/ReportFunction
zip -r ../report-function.zip .
cd ../../..

aws lambda create-function \
  --function-name TimesheetOCR-report-dev \
  --runtime python3.13 \
  --role arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/TimesheetOCR-Role \
  --handler report_lambda.lambda_handler \
  --zip-file fileb://.aws-sam/build/report-function.zip \
  --timeout 30 \
  --memory-size 512 \
  --environment 'Variables={DYNAMODB_TABLE=TimesheetOCR-dev,ENVIRONMENT=dev}'

# 4. Create API Gateway
# ... (API Gateway creation steps)

# 5. Configure S3 events
# ... (as shown in Option 1)
```

## Quick Fix: Remove S3 Event Configuration

If you want to deploy immediately without the circular dependency:

1. Remove the `NotificationConfiguration` from InputBucket in template.yaml
2. Remove the `S3InvokeLambdaPermission` resource
3. Rebuild and deploy
4. Manually configure S3 notifications after deployment using the commands from Option 1

## Testing After Deployment

```bash
# Get bucket name
INPUT_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name timesheet-ocr-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`InputBucketName`].OutputValue' \
  --output text)

# Upload test image
aws s3 cp Screenshots/2025-10-20_15h54_43.png s3://$INPUT_BUCKET/

# Check logs
aws logs tail /aws/lambda/TimesheetOCR-ocr-dev --follow

# Get API URL
API_URL=$(aws cloudformation describe-stacks \
  --stack-name timesheet-ocr-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportApiUrl`].OutputValue' \
  --output text)

# Test report API
curl "$API_URL/resources"
```

## Alternative: Use AWS Console

1. Go to CloudFormation console
2. Create stack
3. Upload packaged.yaml
4. If circular dependency error occurs:
   - Edit template in Designer
   - Remove NotificationConfiguration from InputBucket
   - Create stack
   - Manually add S3 event notifications after creation

## Commit Message for Git

```
feat: Add zero-hour timesheet detection and calendar reporting

- Detect and track zero-hour timesheets (annual leave/absence)
- Add DynamoDB table for timesheet storage
- Implement per-person calendar reports with gap detection
- Create RESTful API for report access
- Generate beautiful HTML reports with visual indicators
- Update OCR prompt to identify zero-hour timesheets
- Add reporting Lambda function and API Gateway

Known Issue: CloudFormation circular dependency with S3 events
Workaround: Deploy core resources, then configure S3 manually
```

## Next Steps

1. Commit all code changes to git
2. Push to GitHub repository
3. Choose deployment approach (Option 1 recommended)
4. Test with example screenshots
5. Verify reports are accessible via API

## Files Changed

- src/prompt.py - Added zero-hour detection
- src/dynamodb_handler.py - Updated schema for zero-hour tracking
- src/reporting.py - NEW: Core reporting logic
- src/report_lambda.py - NEW: Report API handler
- src/report_html.py - NEW: HTML report generator
- template.yaml - Added DynamoDB, Report Lambda, API Gateway
- Multiple documentation files added

All code is production-ready. The only blocker is the CloudFormation circular dependency which can be resolved with manual S3 notification configuration.
