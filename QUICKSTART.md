# Timesheet OCR - Quick Start Guide

Get your timesheet OCR system running in **5 minutes**!

## What You'll Deploy

A serverless OCR system that:
- Automatically processes timesheet images uploaded to S3
- Extracts resource name, dates, projects, and hours using Claude Sonnet 4.5
- Outputs structured CSV files with time tracking data
- Costs ~$0.01 per timesheet

## Prerequisites

Before you begin:

1. **AWS Account** with Bedrock access
2. **AWS CLI** configured (`aws configure`)
3. **AWS SAM CLI** installed
4. **Python 3.11+**

### Enable Amazon Bedrock

This is **required** before deployment:

```bash
# Check if Bedrock model access is enabled
aws bedrock list-foundation-models --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `claude-sonnet-4-5`)]'
```

If no models are returned, enable access:
1. Go to AWS Console → Amazon Bedrock
2. Click "Model access" in sidebar
3. Click "Manage model access"
4. Select "Anthropic Claude Sonnet 4.5"
5. Click "Save changes"

## Quick Deploy (5 Minutes)

### Step 1: Clone and Setup

```bash
# Clone the repository (or create from scratch)
git clone https://github.com/your-org/timesheet-ocr.git
cd timesheet-ocr

# Verify structure
ls src/
# Should see: lambda_function.py, parsing.py, prompt.py, utils.py, requirements.txt
```

### Step 2: Build

```bash
sam build
```

Expected output:
```
Build Succeeded

Built Artifacts  : .aws-sam/build
Built Template   : .aws-sam/build/template.yaml
```

### Step 3: Deploy

```bash
# Simple deployment (no alarms)
sam deploy \
  --template-file template-simple.yaml \
  --stack-name timesheetocr-quickstart \
  --capabilities CAPABILITY_IAM \
  --region us-east-1 \
  --resolve-s3 \
  --parameter-overrides Environment=dev
```

Deployment takes ~2 minutes. You'll see:
```
Stack timesheetocr-quickstart outputs:
InputBucketName: timesheetocr-input-dev-123456789012
OutputBucketName: timesheetocr-output-dev-123456789012
FunctionArn: arn:aws:lambda:us-east-1:...
```

**Save these bucket names!**

## Test It Out

### Upload a Timesheet

```bash
# Replace with your actual input bucket name from outputs
INPUT_BUCKET="timesheetocr-input-dev-YOUR-ACCOUNT-ID"

# Upload your timesheet image
aws s3 cp 2025-10-15_20h43_56.png s3://$INPUT_BUCKET/
```

### Watch the Processing

```bash
# View Lambda logs (replace with your actual function name)
aws logs tail /aws/lambda/TimesheetOCR-ocr-dev --follow
```

You should see:
```
Processing image: s3://timesheetocr-input-dev.../2025-10-15_20h43_56.png
Image size: 87,205 bytes
Calling Claude Bedrock for OCR...
Extracted data for: Nik Coultas
Date range: Sep 29 2025 - Oct 5 2025
Projects found: 5
Converting to CSV...
Uploaded CSV: s3://timesheetocr-output-dev.../timesheets/2025-09-29_Nik_Coultas_timesheet.csv
```

### Download the CSV

```bash
# Replace with your actual output bucket name
OUTPUT_BUCKET="timesheetocr-output-dev-YOUR-ACCOUNT-ID"

# List generated files
aws s3 ls s3://$OUTPUT_BUCKET/timesheets/

# Download the CSV
aws s3 cp s3://$OUTPUT_BUCKET/timesheets/2025-09-29_Nik_Coultas_timesheet.csv ./output.csv

# View it
cat output.csv
```

Expected output:
```csv
Resource Name,Date,Project Name,Project Code,Hours
Nik Coultas,2025-09-29,(NDA) Fixed Transformation (Parent),PJ021931,0
Nik Coultas,2025-09-30,(NDA) Fixed Transformation (Parent),PJ021931,0
Nik Coultas,2025-10-01,(NDA) Fixed Transformation (Parent),PJ021931,0
Nik Coultas,2025-10-02,(NDA) Fixed Transformation (Parent),PJ021931,0
Nik Coultas,2025-10-03,(NDA) Fixed Transformation (Parent),PJ021931,7.5
...
```

## What Just Happened?

1. Image uploaded to S3 input bucket
2. S3 event triggered Lambda function
3. Lambda downloaded image and called Claude Bedrock
4. Claude extracted timesheet data (resource, dates, projects, hours)
5. Lambda generated CSV and uploaded to output bucket
6. Audit JSON also saved for traceability

## Cost Estimate

For **100 timesheets/month**:
- Claude API: ~$1.05
- Lambda: ~$0.05
- S3: ~$0.24
- **Total: ~$1.34/month**

Single timesheet: **~$0.01**

## Next Steps

### Process More Timesheets

```bash
# Batch upload
for file in timesheets/*.png; do
  aws s3 cp "$file" s3://$INPUT_BUCKET/
done
```

### View Audit Data

```bash
# Each CSV has a corresponding audit JSON
aws s3 ls s3://$OUTPUT_BUCKET/audit/
aws s3 cp s3://$OUTPUT_BUCKET/audit/2025-09-29_Nik_Coultas_timesheet.json ./audit.json
cat audit.json
```

The audit JSON contains:
- Source image path
- Processing timestamp
- Model used and token counts
- Cost estimate
- Validation warnings (if any)

### Local Testing (Optional)

Want to test without deploying?

```bash
# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install boto3 pandas

# Test locally (requires AWS credentials)
python test_local.py 2025-10-15_20h43_56.png

# View output
ls test-output/
```

## Troubleshooting

### Issue: "Access Denied" when calling Bedrock

**Solution**: Enable Bedrock model access (see Prerequisites section above)

### Issue: Lambda timeout

**Solution**: Increase timeout in template:
```yaml
Timeout: 600  # 10 minutes
```

### Issue: CSV not generated

**Solution**: Check Lambda logs for errors:
```bash
aws logs tail /aws/lambda/TimesheetOCR-ocr-dev --since 10m
```

### Issue: Invalid project codes

**Solution**: The system auto-normalizes OCR errors (O→0, I→1, L→1). Check audit JSON for validation warnings.

## Clean Up

To delete all resources:

```bash
# Delete stack
aws cloudformation delete-stack --stack-name timesheetocr-quickstart

# Empty buckets first (otherwise delete will fail)
aws s3 rm s3://$INPUT_BUCKET --recursive
aws s3 rm s3://$OUTPUT_BUCKET --recursive
```

## Want More Features?

This quick start uses `template-simple.yaml` for fast deployment.

For **production use** with monitoring, alarms, and cost optimization, see:
- [DEPLOYMENT.md](DEPLOYMENT.md) - Full production deployment guide
- [COMPARISON.md](COMPARISON.md) - Simple vs Production features

## Need Help?

- Check [README.md](README.md) for complete documentation
- View Lambda logs for detailed error messages
- Open an issue on GitHub

---

**Congratulations!** You now have a working timesheet OCR system. 🎉
