# Timesheet OCR - Deployment Checklist

## Pre-Deployment Checklist

### Prerequisites
- [ ] AWS Account with admin or sufficient permissions
- [ ] AWS CLI installed and configured (`aws --version`)
- [ ] AWS credentials configured (`aws sts get-caller-identity`)
- [ ] AWS SAM CLI installed (`sam --version`)
- [ ] Python 3.11+ installed (`python3 --version`)
- [ ] Git installed (optional, for version control)

### Bedrock Access (CRITICAL!)
- [ ] Go to AWS Console → Amazon Bedrock
- [ ] Click "Model access" in sidebar
- [ ] Click "Manage model access"
- [ ] Enable "Anthropic Claude Sonnet 4.5"
- [ ] Verify access: `aws bedrock list-foundation-models --region us-east-1`

## Deployment Options

### Option A: Automated Setup (Recommended)
- [ ] Run `./setup.sh`
- [ ] Follow prompts
- [ ] Choose deployment type (Simple or Production)
- [ ] Note bucket names from output
- [ ] Save `deployment-config.txt` for reference

### Option B: Manual Deployment (Simple)
- [ ] Run `sam build`
- [ ] Run deployment command:
  ```bash
  sam deploy --template-file template-simple.yaml \
    --stack-name timesheetocr-dev \
    --capabilities CAPABILITY_IAM \
    --resolve-s3 \
    --parameter-overrides Environment=dev
  ```
- [ ] Note bucket names from CloudFormation outputs
- [ ] Save bucket names for later use

### Option C: Manual Deployment (Production)
- [ ] Update `samconfig.toml` with your email for AlarmEmail
- [ ] Run `sam build`
- [ ] Run deployment command:
  ```bash
  sam deploy --config-env prod \
    --parameter-overrides AlarmEmail=your-email@example.com
  ```
- [ ] Note bucket names from CloudFormation outputs
- [ ] Verify SNS subscription email (check inbox)
- [ ] Confirm SNS subscription

## Post-Deployment Verification

### Step 1: Verify Resources Created
- [ ] Check S3 input bucket exists
- [ ] Check S3 output bucket exists
- [ ] Check Lambda function exists
- [ ] Check CloudWatch log group exists
- [ ] (Production) Check DLQ exists
- [ ] (Production) Check CloudWatch alarms exist
- [ ] (Production) Check CloudWatch dashboard exists

### Step 2: Test with Sample Image
- [ ] Upload test image:
  ```bash
  aws s3 cp 2025-10-15_20h43_56.png s3://INPUT_BUCKET/
  ```
- [ ] Wait 30-60 seconds
- [ ] Check Lambda logs:
  ```bash
  aws logs tail /aws/lambda/TimesheetOCR-ocr-dev --follow
  ```
- [ ] Verify "Processing completed successfully" in logs
- [ ] List output files:
  ```bash
  aws s3 ls s3://OUTPUT_BUCKET/timesheets/
  aws s3 ls s3://OUTPUT_BUCKET/audit/
  ```
- [ ] Download CSV:
  ```bash
  aws s3 cp s3://OUTPUT_BUCKET/timesheets/*.csv ./
  ```
- [ ] Verify CSV format and content

### Step 3: Validate Output
- [ ] Open CSV in spreadsheet or text editor
- [ ] Verify header: `Resource Name,Date,Project Name,Project Code,Hours`
- [ ] Verify resource name matches image (Nik Coultas)
- [ ] Verify dates are correct (2025-09-29 to 2025-10-05)
- [ ] Verify project codes are normalized (PJ021931, etc.)
- [ ] Verify hours are accurate
- [ ] Check for 7 rows per project (Mon-Sun)

### Step 4: Check Audit Trail
- [ ] Download audit JSON:
  ```bash
  aws s3 cp s3://OUTPUT_BUCKET/audit/*.json ./
  ```
- [ ] Open audit JSON
- [ ] Verify contains:
  - [ ] Source image path
  - [ ] Processing timestamp
  - [ ] Model ID
  - [ ] Token usage
  - [ ] Cost estimate
  - [ ] Extracted data
  - [ ] Validation warnings (if any)

## Production-Specific Verification

### CloudWatch Alarms (Production Only)
- [ ] Go to CloudWatch → Alarms
- [ ] Verify error alarm exists
- [ ] Verify throttle alarm exists
- [ ] Verify DLQ alarm exists
- [ ] All alarms should be in "OK" state initially

### CloudWatch Dashboard (Production Only)
- [ ] Go to CloudWatch → Dashboards
- [ ] Open TimesheetOCR-{env} dashboard
- [ ] Verify widgets display:
  - [ ] Lambda invocations
  - [ ] Lambda errors
  - [ ] Lambda duration
  - [ ] DLQ messages

### SNS Notifications (Production Only)
- [ ] Check email inbox
- [ ] Confirm SNS subscription
- [ ] Trigger test alarm (optional):
  ```bash
  aws sns publish --topic-arn TOPIC_ARN --message "Test message"
  ```

## Testing Additional Timesheet Images

### Upload Your Own Timesheets
- [ ] Prepare timesheet images (PNG or JPG)
- [ ] Upload to input bucket:
  ```bash
  for file in timesheets/*.png; do
    aws s3 cp "$file" s3://INPUT_BUCKET/
  done
  ```
- [ ] Monitor processing in CloudWatch logs
- [ ] Verify CSV files generated
- [ ] Validate accuracy by comparing with source images

### Batch Processing Test
- [ ] Upload 10+ timesheets at once
- [ ] Monitor Lambda concurrency in CloudWatch
- [ ] Verify all processed successfully
- [ ] Check for any throttling errors
- [ ] Verify CSV files for all timesheets

## Local Testing (Optional)

### Setup Virtual Environment
- [ ] Create venv: `python3 -m venv venv`
- [ ] Activate: `source venv/bin/activate`
- [ ] Install deps: `pip install boto3 pandas`

### Run Local Test
- [ ] Run: `python test_local.py 2025-10-15_20h43_56.png`
- [ ] Verify output in `test-output/` directory
- [ ] Check CSV accuracy
- [ ] Review audit JSON

### Run Unit Tests
- [ ] Navigate to tests: `cd tests`
- [ ] Install test deps: `pip install -r requirements.txt`
- [ ] Run tests: `pytest -v --cov=../src`
- [ ] Verify all tests pass
- [ ] Check coverage report

## CI/CD Setup (Optional)

### GitHub Actions
- [ ] Create GitHub repository
- [ ] Add GitHub Secrets:
  - [ ] AWS_ACCESS_KEY_ID
  - [ ] AWS_SECRET_ACCESS_KEY
  - [ ] AWS_ACCESS_KEY_ID_PROD (for production)
  - [ ] AWS_SECRET_ACCESS_KEY_PROD (for production)
- [ ] Push code to repository
- [ ] Verify workflow runs successfully
- [ ] Test auto-deployment by pushing to `develop` branch

## Cost Monitoring

### Set Up Cost Alerts
- [ ] Go to AWS Billing → Budgets
- [ ] Create budget for Bedrock API calls
- [ ] Create budget for Lambda invocations
- [ ] Set alert thresholds

### Review Cost Allocation Tags
- [ ] Go to AWS Cost Explorer
- [ ] Filter by tag: `Project=TimesheetOCR`
- [ ] Verify resources are tagged correctly
- [ ] Set up monthly cost reports

## Documentation

### Save Important Information
- [ ] Note input bucket name
- [ ] Note output bucket name
- [ ] Note Lambda function name
- [ ] Note CloudWatch log group name
- [ ] Note stack name
- [ ] Save deployment-config.txt
- [ ] Document any custom configurations

### Share with Team
- [ ] Share deployment details with team
- [ ] Provide access to S3 buckets
- [ ] Share CloudWatch dashboard URL
- [ ] Document any custom processes

## Troubleshooting

### Common Issues Checklist
- [ ] If "Access Denied" error: Verify Bedrock model access enabled
- [ ] If Lambda timeout: Check image size and increase timeout
- [ ] If CSV not generated: Check Lambda logs for errors
- [ ] If invalid project codes: Check audit JSON for warnings
- [ ] If high costs: Review CloudWatch metrics and adjust concurrency

### Support Resources
- [ ] Review QUICKSTART.md for quick issues
- [ ] Review DEPLOYMENT_SUMMARY.md for detailed docs
- [ ] Review PROJECT_SUMMARY.md for overview
- [ ] Check CloudWatch logs for errors
- [ ] Review audit JSON for validation issues

## Final Verification

### End-to-End Test
- [ ] Upload a timesheet image
- [ ] Wait for processing (30-60 seconds)
- [ ] Download CSV output
- [ ] Compare CSV with source image
- [ ] Verify 100% accuracy for:
  - [ ] Resource name
  - [ ] Date range and all weekdays
  - [ ] All projects and codes
  - [ ] All hours for each day
  - [ ] Empty cells = 0 hours

### Success Criteria
- [ ] All resources deployed successfully
- [ ] Sample timesheet processed correctly
- [ ] CSV format matches specification
- [ ] Data accuracy is 100%
- [ ] Audit trail generated
- [ ] No errors in CloudWatch logs
- [ ] (Production) Alarms configured and in OK state
- [ ] (Production) Dashboard shows metrics
- [ ] Cost per timesheet ~$0.01

## Deployment Complete! 🎉

If all checkboxes are checked, your timesheet OCR system is ready for production use!

### Next Steps
1. **Process your timesheets** - Upload real timesheet images
2. **Monitor performance** - Use CloudWatch dashboard
3. **Optimize costs** - Review usage and adjust if needed
4. **Integrate with systems** - Connect CSV output to your tools
5. **Scale as needed** - Adjust concurrency limits if processing more

### Support
- Questions? See documentation files
- Issues? Check CloudWatch logs
- Need help? Open GitHub issue

---

**Congratulations! Your timesheet OCR system is deployed and operational.**
