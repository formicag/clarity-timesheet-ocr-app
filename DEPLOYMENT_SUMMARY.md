# Timesheet OCR - Deployment Summary

## Project Overview

A production-ready, serverless timesheet OCR system built with:
- **AWS Lambda** - Serverless compute
- **Amazon S3** - Image storage and CSV output
- **Amazon Bedrock** - Claude Sonnet 4.5 for OCR
- **AWS SAM** - Infrastructure as Code
- **GitHub Actions** - CI/CD pipeline

## System Architecture

```
Timesheet Image (PNG/JPG)
    ↓
S3 Input Bucket
    ↓ (S3 Event)
Lambda Function
    ├→ Claude Sonnet 4.5 (Bedrock)
    ├→ Parse & Validate Data
    ├→ Generate CSV
    └→ Save Audit JSON
    ↓
S3 Output Bucket
    ├→ timesheets/*.csv
    └→ audit/*.json
```

## Key Features

### Data Extraction
- **Resource Name**: Person whose timesheet this is
- **Date Range**: Week period (Mon-Sun)
- **Projects**: Project name + code (PJ######)
- **Hours**: Daily hours for each project (Mon-Sun)

### Data Quality
- **Date calculation**: Generates all 7 days from date range
- **Project code normalization**: Fixes OCR errors (O→0, I→1, L→1)
- **Validation**: Warns about missing/invalid data
- **Audit trail**: Full JSON audit log per timesheet

### CSV Output Format
```csv
Resource Name,Date,Project Name,Project Code,Hours
Nik Coultas,2025-09-29,(NDA) Fixed Transformation (Parent),PJ021931,0
Nik Coultas,2025-09-30,(NDA) Fixed Transformation (Parent),PJ021931,0
...
```

## Two Deployment Options

### Option 1: Simple (Quick Start)
**File**: `template-simple.yaml`
**Time**: 5 minutes
**Use Case**: Learning, POC, development

Features:
- S3 input/output buckets
- Lambda function with Bedrock
- Basic encryption and access control

**Deploy**:
```bash
sam build
sam deploy --template-file template-simple.yaml \
  --stack-name timesheetocr-dev \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides Environment=dev
```

### Option 2: Production (Full Featured)
**File**: `template.yaml`
**Time**: 30 minutes
**Use Case**: Production workloads

Additional features:
- Dead Letter Queue (DLQ) for failed processing
- CloudWatch Alarms (errors, throttles, DLQ messages)
- SNS notifications for alarms
- CloudWatch Dashboard
- S3 lifecycle policies (cost optimization)
- Multi-environment support (dev/staging/prod)
- Reserved concurrency limits
- Comprehensive cost allocation tags

**Deploy**:
```bash
sam build
sam deploy --config-env prod \
  --parameter-overrides AlarmEmail=your-email@example.com
```

## File Structure

```
clarity-timesheet-ocr-app/
├── src/
│   ├── lambda_function.py      # Main Lambda handler
│   ├── parsing.py              # JSON → CSV conversion
│   ├── prompt.py               # Claude prompts
│   ├── utils.py                # Helper functions
│   └── requirements.txt        # Python dependencies
├── tests/
│   ├── test_utils.py           # Unit tests for utils
│   ├── test_parsing.py         # Unit tests for parsing
│   └── requirements.txt        # Test dependencies
├── .github/workflows/
│   └── deploy.yml              # CI/CD pipeline
├── template.yaml               # Production SAM template
├── template-simple.yaml        # Simple SAM template
├── samconfig.toml              # SAM configuration
├── test_local.py               # Local testing script
├── QUICKSTART.md               # 5-minute guide
├── DEPLOYMENT_SUMMARY.md       # This file
└── README.md                   # Complete documentation
```

## Code Modules

### 1. utils.py
- `parse_date_range()` - Parse "Sep 29 2025 - Oct 5 2025"
- `generate_week_dates()` - Generate Mon-Sun dates
- `normalize_project_code()` - Fix OCR errors in codes
- `parse_hours()` - Convert hours string to float
- `validate_timesheet_data()` - Data quality checks

### 2. prompt.py
- `get_ocr_prompt()` - Detailed prompt for Claude
- Instructs Claude to return structured JSON
- Specifies exact format and requirements

### 3. parsing.py
- `parse_timesheet_json()` - Parse Claude response
- `convert_to_csv()` - Generate CSV using pandas
- `create_audit_json()` - Generate audit trail
- `calculate_cost_estimate()` - Estimate API costs

### 4. lambda_function.py
- Main Lambda handler
- Downloads image from S3
- Calls Claude on Bedrock
- Saves CSV and audit JSON
- Error handling and logging

## Testing

### Unit Tests (pytest)
```bash
cd tests
pip install -r requirements.txt
pytest -v --cov=../src
```

Tests cover:
- Date parsing and generation
- Project code normalization
- CSV conversion
- Data validation
- Cost calculation

### Local Testing
```bash
python3 -m venv venv
source venv/bin/activate
pip install boto3 pandas
python test_local.py 2025-10-15_20h43_56.png
```

Outputs:
- `test-output/2025-10-15_20h43_56_output.csv`
- `test-output/2025-10-15_20h43_56_audit.json`
- `test-output/2025-10-15_20h43_56_raw.json`

## CI/CD Pipeline

**GitHub Actions** workflow (`deploy.yml`):

1. **Test** - Runs pytest on every push/PR
2. **Deploy to Dev** - Auto-deploys from `develop` branch
3. **Deploy to Staging** - Auto-deploys from `main` branch
4. **Deploy to Prod** - Manual trigger via workflow_dispatch

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_ACCESS_KEY_ID_PROD` (for production)
- `AWS_SECRET_ACCESS_KEY_PROD` (for production)

## Cost Analysis

### Per Timesheet (Average)
- **Claude Sonnet 4.5**: ~$0.01 (1K input + 500 output tokens)
- **Lambda**: ~$0.0005 (30s execution, 1024MB)
- **S3**: ~$0.0002 (storage + requests)
- **Total**: **~$0.0107 per timesheet**

### Monthly (100 timesheets)
- Claude: $1.05
- Lambda: $0.05
- S3: $0.24
- CloudWatch: $0.50
- **Total: $1.84/month**

### Cost Optimization Features
1. S3 Lifecycle (transition to cheaper storage)
2. Lambda reserved concurrency (prevent runaway costs)
3. Log retention policies (30-90 days)
4. Model selection (Sonnet vs Opus trade-off)

## Monitoring & Observability

### CloudWatch Alarms (Production)
1. **Error Alarm** - Triggers on >5 errors in 5 minutes
2. **Throttle Alarm** - Triggers on any throttling
3. **DLQ Alarm** - Triggers when messages in DLQ

### CloudWatch Dashboard
View at: AWS Console → CloudWatch → Dashboards → TimesheetOCR-{env}

Metrics:
- Lambda invocations, errors, duration
- DLQ message count
- Bedrock API calls

### Logs
```bash
# Tail Lambda logs
aws logs tail /aws/lambda/TimesheetOCR-ocr-{env} --follow

# Search for errors
aws logs filter-pattern /aws/lambda/TimesheetOCR-ocr-{env} \
  --filter-pattern "ERROR"
```

## Usage Examples

### Upload Single Timesheet
```bash
aws s3 cp timesheet.png s3://INPUT_BUCKET/
```

### Batch Upload
```bash
for file in timesheets/*.png; do
  aws s3 cp "$file" s3://INPUT_BUCKET/
done
```

### Download Results
```bash
# List CSVs
aws s3 ls s3://OUTPUT_BUCKET/timesheets/

# Download specific CSV
aws s3 cp s3://OUTPUT_BUCKET/timesheets/2025-09-29_Nik_Coultas_timesheet.csv ./

# Download all CSVs
aws s3 sync s3://OUTPUT_BUCKET/timesheets/ ./timesheets/
```

### Check Audit Trail
```bash
aws s3 cp s3://OUTPUT_BUCKET/audit/2025-09-29_Nik_Coultas_timesheet.json ./
cat 2025-09-29_Nik_Coultas_timesheet.json | jq '.'
```

Audit JSON contains:
- Processing timestamp
- Token usage and cost
- Validation warnings
- Full extracted data

## Troubleshooting

### Common Issues

1. **Access Denied - Bedrock**
   - Enable model access in Bedrock console
   - Check IAM permissions for `bedrock:InvokeModel`

2. **Lambda Timeout**
   - Increase `Timeout` in template (default 300s)
   - Check image size (large images take longer)

3. **Invalid Project Codes**
   - Check audit JSON for validation warnings
   - Normalization handles most OCR errors automatically

4. **Missing Hours Data**
   - Check source image quality
   - Review Claude response in audit JSON
   - Adjust prompt if needed

5. **High Costs**
   - Check invocation count in CloudWatch
   - Review reserved concurrency settings
   - Consider using smaller Claude model for testing

## Security Best Practices

1. **S3 Buckets**
   - Public access blocked
   - Encryption at rest (AES256)
   - Versioning enabled

2. **Lambda**
   - Least privilege IAM roles
   - No hardcoded credentials
   - Environment variables for config

3. **Secrets Management**
   - Use AWS Secrets Manager for API keys
   - GitHub Secrets for deployment credentials

4. **Network**
   - Lambda in VPC (optional, for private resources)
   - S3 VPC endpoints (optional, for private access)

## Next Steps After Deployment

1. **Test with your timesheets** - Upload actual timesheet images
2. **Validate CSV accuracy** - Compare output with source images
3. **Set up monitoring** - Configure CloudWatch alarms
4. **Integrate with downstream** - Connect CSV output to your systems
5. **Optimize costs** - Review usage and adjust resources

## Support & Resources

- **Full Documentation**: [README.md](README.md)
- **Quick Start**: [QUICKSTART.md](QUICKSTART.md)
- **GitHub Issues**: Report bugs and feature requests
- **AWS Documentation**:
  - [Amazon Bedrock](https://docs.aws.amazon.com/bedrock/)
  - [AWS Lambda](https://docs.aws.amazon.com/lambda/)
  - [AWS SAM](https://docs.aws.amazon.com/serverless-application-model/)

---

**Built with AWS SAM, Lambda, S3, and Claude Sonnet 4.5 on Bedrock**
