# Timesheet Reporting System Guide

## Overview

The Timesheet OCR system includes comprehensive reporting and export capabilities:
- **Desktop UI Exports** - Export data directly from the Mac application
- **API-Based Reports** - Access reports via REST API endpoints
- **Zero-Hour Detection** - Track annual leave and absences
- **Period-Based Exports** - Export data for specific date ranges
- **OCR Error Correction** - Fix and re-import corrected data

## Desktop UI Export Features

### 1. Full Database Export & Import

**Purpose:** Export complete database for offline review and error correction

**Steps:**
1. Click **"📥 Export Full Data"** in the UI
2. Save CSV with all 14 fields (ResourceName, Date, Hours, ProjectCode, etc.)
3. Open in Excel/Numbers and fix any OCR errors
4. Save the corrected CSV
5. Click **"📤 Import Corrections"** to upload
6. Only changed rows are updated in DynamoDB

**Fields Included:**
- ResourceName, DateProjectCode, ResourceNameDisplay
- Date, WeekStartDate, WeekEndDate
- ProjectCode, ProjectName, Hours
- IsZeroHourTimesheet, ZeroHourReason
- SourceImage, ProcessingTimestamp, YearMonth

### 2. Period Summary Export

**Purpose:** Get total hours by resource for a date range

**Steps:**
1. Select **Start Date** using calendar picker
2. Select **End Date** using calendar picker
3. Click **"📊 Export Summary"**
4. Save CSV file

**Output Format:**
```csv
Resource Name,Total Hours,Total Days (Hours ÷ 7.5)
Barry Breden,150.00,20.00
Nik Coultas,120.00,16.00

TOTAL,270.00,36.00
```

**Features:**
- Aggregates hours by resource
- Calculates days (Hours ÷ 7.5)
- Includes grand total row
- Date range is inclusive (includes both start and end dates)
- Sorted alphabetically by resource name

### 3. Period Detailed Export

**Purpose:** Export all timesheet entries for a date range

**Steps:**
1. Select **Start Date** using calendar picker
2. Select **End Date** using calendar picker
3. Click **"📋 Export Detailed"**
4. Save CSV file

**Output:**
- All 14 fields for each timesheet entry
- Sorted by Date, then ResourceName
- One row per timesheet entry
- Date range is inclusive

**Use Cases:**
- Detailed audit trail
- Analysis by project or date
- Verification of specific entries
- Bulk review of timesheets

### 4. Clarity Month Export (VMO2)

**Purpose:** Export timesheet data for Virgin Media O2's custom billing periods (Clarity Months)

**What are Clarity Months?**
VMO2 uses non-calendar months for billing and reporting. Each Clarity Month has specific start and end dates that don't align with standard calendar months.

**Example:**
- **Jan-25**: December 16, 2024 to January 19, 2025
- **Nov-25**: October 20, 2025 to November 16, 2025

**Steps:**
1. Select a **Clarity Month** from the dropdown (e.g., "Nov-25 (20-Oct-25 to 16-Nov-25)")
2. Choose export type:
   - Click **"📊 Export Summary"** for hours by resource
   - Click **"📋 Export Detailed"** for all timesheet entries
3. Save the CSV file

**Default Selection:**
The dropdown automatically selects the current Clarity Month based on today's date.

**Available Months:**
- Jan-25 through Dec-25 (12 months)
- All 2025 Clarity billing periods
- Pre-configured with VMO2-specific date ranges

**Export Formats:**
- **Summary:** Same format as Period Summary (Resource, Hours, Days)
- **Detailed:** Same format as Period Detailed (all 14 fields)
- Filenames include date ranges (e.g., `timesheet_summary_2025-10-20_to_2025-11-16_20251022.csv`)

**Configuration:**
Clarity months are defined in `clarity_months.json` and can be updated for future years.

### Calendar Date Pickers

**Features:**
- Visual calendar interface
- Click to select dates
- Navigate between months
- Week starts on Monday
- Format: YYYY-MM-DD
- Defaults: Start = 1st of current month, End = today

**Important:** Date ranges are **inclusive** - both start and end dates are included in the export.

## API-Based Features

### 1. Per-Person Calendar Reports

Generate visual calendar reports showing:
- **Green checkmark**: Week has timesheet data
- **Orange warning**: Week has zero-hour timesheet (leave/absence)
- **Red cross**: Week is missing timesheet submission

### 2. Gap Detection

The system identifies missing weeks by:
1. Finding the earliest timesheet submission date
2. Generating all calendar weeks from that date to present
3. Marking weeks without submissions as "missing"
4. Calculating completion percentage

### 3. Zero-Hour Timesheet Detection

The system automatically detects when a timesheet has 0% project time logged (indicating annual leave or absence) and tracks these submissions separately.

**Key Characteristics:**
- Detects timesheets with 0% project time
- Identifies reason (ANNUAL_LEAVE or ABSENCE)
- Stores a single record to track the week was submitted
- Shows as "Zero Hour" in reports with an orange indicator

**Example Zero-Hour Timesheets:**
- Employee on annual leave for the week
- Employee absent for the week
- Any timesheet showing 0% in the top-right corner

## API Endpoints

### Base URL
```
https://{API_ID}.execute-api.us-east-1.amazonaws.com/dev
```

You can find your API URL in the CloudFormation outputs after deployment:
```bash
aws cloudformation describe-stacks --stack-name timesheet-ocr-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportApiUrl`].OutputValue' \
  --output text
```

### 1. List All Resources

**Endpoint:** `GET /resources`

**Description:** Get a list of all resources (people) who have submitted timesheets.

**Example:**
```bash
curl https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/resources
```

**Response:**
```json
{
  "resources": [
    {
      "resource_key": "Barry_Breden",
      "resource_name": "Barry Breden"
    },
    {
      "resource_key": "Nik_Coultas",
      "resource_name": "Nik Coultas"
    }
  ],
  "count": 2
}
```

### 2. Get Calendar Report (JSON)

**Endpoint:** `GET /report/{resource_name}`

**Description:** Get detailed calendar report for a specific resource in JSON format.

**Query Parameters:**
- `start_date` (optional): Start date in YYYY-MM-DD format
- `end_date` (optional): End date in YYYY-MM-DD format (defaults to today)

**Example:**
```bash
# Get report for Barry Breden
curl "https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/report/Barry%20Breden"

# Get report for specific date range
curl "https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/report/Barry%20Breden?start_date=2025-09-01&end_date=2025-12-31"
```

**Response:**
```json
{
  "resource_name": "Barry Breden",
  "has_data": true,
  "date_range": {
    "start": "2025-09-15",
    "end": "2025-10-20"
  },
  "statistics": {
    "total_weeks": 6,
    "weeks_present": 2,
    "weeks_missing": 4,
    "zero_hour_weeks": 1,
    "completion_percentage": 33.3
  },
  "calendar": [
    {
      "week_start": "2025-09-15",
      "week_end": "2025-09-21",
      "iso_week": 38,
      "year": 2025,
      "status": "present",
      "is_zero_hour": true,
      "zero_hour_reason": "ANNUAL_LEAVE",
      "total_hours": 0,
      "projects_count": 0,
      "project_codes": []
    },
    {
      "week_start": "2025-09-22",
      "week_end": "2025-09-28",
      "iso_week": 39,
      "year": 2025,
      "status": "present",
      "is_zero_hour": false,
      "total_hours": 52.5,
      "projects_count": 1,
      "project_codes": ["PJ023275"]
    },
    {
      "week_start": "2025-09-29",
      "week_end": "2025-10-05",
      "iso_week": 40,
      "year": 2025,
      "status": "missing",
      "is_zero_hour": false,
      "total_hours": 0,
      "projects_count": 0,
      "project_codes": []
    }
  ]
}
```

### 3. Get Calendar Report (HTML)

**Endpoint:** `GET /report/{resource_name}/html`

**Description:** Get beautiful visual HTML calendar report.

**Query Parameters:**
- `start_date` (optional): Start date in YYYY-MM-DD format
- `end_date` (optional): End date in YYYY-MM-DD format

**Example:**
```bash
# View in browser
open "https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/report/Barry%20Breden/html"
```

**Features of HTML Report:**
- Responsive design that works on desktop and mobile
- Color-coded week cards:
  - 🟢 Green border = Timesheet submitted
  - 🟠 Orange border = Zero-hour timesheet (leave/absence)
  - 🔴 Red border = Missing submission
- Statistics dashboard showing:
  - Total weeks
  - Weeks submitted
  - Weeks missing
  - Zero-hour weeks
  - Completion percentage
- Grouped by month for easy navigation
- Hover effects for better interactivity

## Database Schema

### DynamoDB Table: TimesheetOCR-{Environment}

**Primary Key:**
- Partition Key: `ResourceName` (e.g., "Barry_Breden")
- Sort Key: `DateProjectCode` (e.g., "2025-09-29#PJ023275")

**For zero-hour timesheets:**
- Sort Key: `WEEK#{start_date}` (e.g., "WEEK#2025-09-15")

**Key Attributes:**
- `ResourceName`: Resource identifier (underscored)
- `ResourceNameDisplay`: Display name (with spaces)
- `Date`: Date of entry (YYYY-MM-DD)
- `WeekStartDate`: Monday of the week (YYYY-MM-DD)
- `WeekEndDate`: Sunday of the week (YYYY-MM-DD)
- `IsZeroHourTimesheet`: Boolean flag
- `ZeroHourReason`: "ANNUAL_LEAVE" or "ABSENCE"
- `ProjectCode`: Project code (empty for zero-hour)
- `ProjectName`: Project name (empty for zero-hour)
- `Hours`: Hours logged (0 for zero-hour)
- `SourceImage`: S3 key of uploaded screenshot

**Global Secondary Indexes:**
1. `ProjectCodeIndex`: Query by project
2. `YearMonthIndex`: Query by month

## Deployment

### Prerequisites
1. AWS CLI configured
2. SAM CLI installed
3. Python 3.13+ environment

### Deploy the Updated Stack

```bash
# Build
sam build

# Deploy to dev environment
sam deploy \
  --stack-name timesheet-ocr-dev \
  --parameter-overrides Environment=dev \
  --capabilities CAPABILITY_IAM \
  --resolve-s3

# Get outputs including API URL
aws cloudformation describe-stacks \
  --stack-name timesheet-ocr-dev \
  --query 'Stacks[0].Outputs'
```

### Environment Variables

The system automatically sets:
- `DYNAMODB_TABLE`: Table name for timesheet data
- `MODEL_ID`: Claude model ID for OCR
- `ENVIRONMENT`: Deployment environment

## Usage Examples

### 1. Upload a Zero-Hour Timesheet

Simply upload the screenshot as normal:

```bash
# Copy screenshot to S3
aws s3 cp "Screenshots/2025-10-20_15h54_43.png" \
  s3://timesheetocr-input-dev-{ACCOUNT_ID}/2025-10-20_15h54_43.png
```

The system will automatically:
1. Detect it's a zero-hour timesheet (0% shown)
2. Extract the resource name and date range
3. Store a single record with `IsZeroHourTimesheet: true`
4. Include it in reports with orange indicator

### 2. View All Resources

```bash
# Get list of all people who have submitted timesheets
curl https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/resources | jq .
```

### 3. Check Completion Status

```bash
# Get JSON report
curl "https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/report/Barry%20Breden" | jq .statistics

# Output:
# {
#   "total_weeks": 10,
#   "weeks_present": 7,
#   "weeks_missing": 3,
#   "zero_hour_weeks": 1,
#   "completion_percentage": 70.0
# }
```

### 4. View Visual Report

Open in your browser:
```bash
# macOS
open "https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/report/Barry%20Breden/html"

# Linux
xdg-open "https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/report/Barry%20Breden/html"

# Windows
start "https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/report/Barry%20Breden/html"
```

### 5. Export Report Data

```bash
# Save JSON report to file
curl "https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/report/Barry%20Breden" > report.json

# Save HTML report
curl "https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/report/Barry%20Breden/html" > report.html
```

## Local Testing

### Test Zero-Hour Detection

```bash
python3 test_zero_hour_detection.py
```

### Test Report Generation Locally

```python
# Set environment variable
export DYNAMODB_TABLE=TimesheetOCR-dev

# Run report function locally
python3 -c "
import sys
sys.path.insert(0, 'src')
from report_lambda import lambda_handler

event = {
    'path': '/resources',
    'httpMethod': 'GET',
    'queryStringParameters': None
}

result = lambda_handler(event, None)
print(result)
"
```

## Troubleshooting

### Issue: Zero-hour timesheet not detected

**Check:**
1. Timesheet shows 0% in top-right corner
2. No project hours are logged
3. Review Lambda logs for OCR output

**Solution:**
The prompt explicitly looks for 0% project time. If the timesheet has any hours logged, it won't be classified as zero-hour.

### Issue: Missing weeks showing incorrectly

**Check:**
1. Verify the date range in query parameters
2. Check if there are any entries for that resource
3. Ensure WeekStartDate is set correctly (Mondays)

**Solution:**
The system generates all weeks from the earliest submission to today. If a resource has very old data, consider using `start_date` parameter.

### Issue: Report API returns 404

**Check:**
1. API Gateway deployed correctly
2. Lambda function has correct permissions
3. Resource name is URL-encoded (spaces as %20)

**Solution:**
```bash
# Check API exists
aws apigateway get-rest-apis --query 'items[?name==`TimesheetOCR-API-dev`]'

# Check Lambda function
aws lambda get-function --function-name TimesheetOCR-report-dev
```

## Future Enhancements

Potential improvements:
1. Email notifications for missing weeks
2. Bulk report generation for all resources
3. Export to Excel/PDF
4. Team-level dashboards
5. Trend analysis (hours over time)
6. Project allocation reports

## Support

For issues or questions:
1. Check CloudWatch logs for Lambda functions
2. Review DynamoDB table contents
3. Verify IAM permissions
4. Check API Gateway configuration
