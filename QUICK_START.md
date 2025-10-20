# Quick Start Guide

## Deploy the System

```bash
# 1. Build
sam build

# 2. Deploy
sam deploy --stack-name timesheet-ocr-dev

# 3. Get API URL
aws cloudformation describe-stacks \
  --stack-name timesheet-ocr-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportApiUrl`].OutputValue' \
  --output text
```

## Upload Timesheets

```bash
# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Upload screenshots
aws s3 cp "Screenshots/2025-10-20_15h54_43.png" \
  s3://timesheetocr-input-dev-${ACCOUNT_ID}/

aws s3 cp "Screenshots/2025-10-20_15h54_17.png" \
  s3://timesheetocr-input-dev-${ACCOUNT_ID}/
```

## View Reports

```bash
# Get API URL
API_URL=$(aws cloudformation describe-stacks \
  --stack-name timesheet-ocr-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportApiUrl`].OutputValue' \
  --output text)

# List all people
curl "$API_URL/resources" | jq .

# View JSON report
curl "$API_URL/report/Barry%20Breden" | jq .

# Open HTML report in browser
open "$API_URL/report/Barry%20Breden/html"
```

## Check Results

```bash
# View DynamoDB data
aws dynamodb scan --table-name TimesheetOCR-dev | jq '.Items[] | {name: .ResourceNameDisplay.S, week: .WeekStartDate.S, zero_hour: .IsZeroHourTimesheet.BOOL, hours: .Hours.N}'

# Check Lambda logs
aws logs tail /aws/lambda/TimesheetOCR-ocr-dev --follow
```

## Color Code Reference

- 🟢 **Green** = Timesheet submitted with hours
- 🟠 **Orange** = Zero-hour timesheet (leave/absence)
- 🔴 **Red** = Missing submission

## API Endpoints

1. **List Resources**: `GET /resources`
2. **JSON Report**: `GET /report/{name}`
3. **HTML Report**: `GET /report/{name}/html`

Query params: `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

## Example Report URL

```
https://{api-id}.execute-api.us-east-1.amazonaws.com/dev/report/Barry%20Breden/html
```

Replace spaces with `%20` in URLs!

## Troubleshooting

**Issue**: API returns 404
**Fix**: Check API Gateway deployed correctly
```bash
aws apigateway get-rest-apis --query 'items[?name==`TimesheetOCR-API-dev`]'
```

**Issue**: Zero-hour not detected
**Fix**: Verify timesheet shows 0% in top-right corner

**Issue**: Missing weeks incorrect
**Fix**: Use `?start_date=` parameter to filter date range

## What's New

1. ✅ Zero-hour timesheet detection (annual leave)
2. ✅ Per-person calendar reports
3. ✅ Gap detection with visual indicators
4. ✅ Beautiful HTML reports
5. ✅ RESTful API for reporting

See `REPORTING_GUIDE.md` for complete documentation.
