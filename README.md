# Timesheet OCR System

Automated timesheet processing using AWS Lambda, Claude 3.5 Sonnet OCR, and DynamoDB with a native Mac desktop application.

## Features

### Core Processing
- 🖼️ **Image OCR** - Extract timesheet data from PNG/JPG images using Claude 3.5 Sonnet
- 📊 **Data Storage** - Store in DynamoDB with indexing by resource and date
- 🔍 **Zero-Hour Detection** - Automatically detect and track annual leave/absences
- 🚀 **S3 Triggers** - Automatic processing when images are uploaded

### Desktop Application
- 🖥️ **Native Mac UI** - Simple, elegant desktop application
- 📁 **Batch Upload** - Process multiple timesheets at once
- 👀 **Data Viewer** - Browse all processed timesheets
- 🔄 **Real-time Refresh** - Reload data from DynamoDB
- 📝 **Detailed Logging** - See exactly what's happening

### Export & Reporting
- 📥 **Full Database Export** - Export all data with all 14 fields
- 📤 **Import Corrections** - Fix OCR errors offline and re-import
- 📅 **Period Exports** - Export data for specific date ranges
- 📊 **Summary Reports** - Total hours by resource with days calculation
- 📋 **Detailed Reports** - All timesheet entries for a period
- 🗓️ **Calendar Pickers** - Visual date selection
- 🌐 **REST API** - Access reports via HTTP endpoints
- 📈 **HTML Reports** - Beautiful visual calendar reports

## Quick Start

### Prerequisites
```bash
# Install dependencies
pip3 install boto3 tkcalendar

# Configure AWS credentials
aws configure
# or
aws sso login
```

### Launch Desktop UI

**Method 1: Double-click (Easiest)**
1. Navigate to project folder in Finder
2. Double-click `launch_ui.command`
3. UI opens automatically

**Method 2: Command line**
```bash
python3 timesheet_ui.py
```

### Using the UI

#### 1. Process Timesheets
- Click **"📁 Select Files..."** to browse for images
- Click **"🚀 Upload & Process"** to upload and OCR
- Watch progress in logs

#### 2. View Data
- Click **"📊 View Data"** to see all processed timesheets
- Click **"🔄 Refresh"** to reload latest data

#### 3. Export Data

**Full Export (for corrections):**
1. Click **"📥 Export Full Data"**
2. Edit CSV in Excel/Numbers to fix OCR errors
3. Click **"📤 Import Corrections"** to upload fixes

**Period Exports:**
1. Select **Start Date** and **End Date** using calendar pickers
2. Click **"📊 Export Summary"** for hours by resource
3. Click **"📋 Export Detailed"** for all entries

## Export Formats

### Summary Export
```csv
Resource Name,Total Hours,Total Days (Hours ÷ 7.5)
Barry Breden,150.00,20.00
Nik Coultas,120.00,16.00

TOTAL,270.00,36.00
```

### Detailed Export
```csv
ResourceName,DateProjectCode,Date,ProjectCode,ProjectName,Hours,...
Barry Breden,2025-10-01#P001,2025-10-01,P001,Project Alpha,7.5,...
Barry Breden,2025-10-02#P001,2025-10-02,P001,Project Alpha,8.0,...
```

### Full Export
All 14 fields:
- ResourceName, DateProjectCode, ResourceNameDisplay
- Date, WeekStartDate, WeekEndDate
- ProjectCode, ProjectName, Hours
- IsZeroHourTimesheet, ZeroHourReason
- SourceImage, ProcessingTimestamp, YearMonth

## Key Features Explained

### Calendar Date Pickers
- Visual calendar interface for date selection
- Click date field to open calendar
- Navigate between months
- Format: YYYY-MM-DD
- **Date ranges are inclusive** (both start and end dates included)

### OCR Error Correction Workflow
1. Export full database
2. Open CSV in Excel/Numbers
3. Fix any OCR errors
4. Save corrected CSV
5. Import corrections
6. Only changed rows are updated (efficient)

### Days Calculation
- **Formula:** Total Days = Total Hours ÷ 7.5
- Based on 7.5-hour working day
- Shown with 2 decimal places

### Zero-Hour Timesheets
- Automatically detected (0% project time)
- Tracks annual leave and absences
- Stored in database with reason
- Included in reports

## Deployment

### Using Terraform (Recommended)
```bash
# Build Lambda functions
sam build

# Deploy with Terraform
cd terraform
terraform init
terraform plan
terraform apply

# Or use the deployment script
./deploy.sh dev apply
```

### Using SAM (Alternative)
```bash
sam build
sam deploy --guided
```

See `DEPLOYMENT_INSTRUCTIONS.md` for detailed deployment guide.

## Architecture

```
┌─────────────┐     ┌──────────┐     ┌─────────────┐
│   Desktop   │────▶│    S3    │────▶│   Lambda    │
│     UI      │     │  Input   │     │  (OCR)      │
└─────────────┘     └──────────┘     └─────────────┘
                                            │
                                            ▼
                    ┌──────────┐     ┌─────────────┐
                    │    S3    │◀────│  DynamoDB   │
                    │  Output  │     │   Table     │
                    └──────────┘     └─────────────┘
                                            │
                                            ▼
                                     ┌─────────────┐
                                     │   Report    │
                                     │   Lambda    │
                                     └─────────────┘
                                            │
                                            ▼
                                     ┌─────────────┐
                                     │     API     │
                                     │   Gateway   │
                                     └─────────────┘
```

## Project Structure

```
.
├── timesheet_ui.py              # Desktop UI application
├── launch_ui.command            # Quick launch script
├── src/
│   ├── ocr_lambda.py           # OCR Lambda handler
│   ├── report_lambda.py        # Report API handler
│   ├── dynamodb_handler.py     # Database operations
│   ├── prompt.py               # Claude OCR prompts
│   └── ...
├── terraform/                   # Infrastructure as code
│   ├── main.tf
│   ├── lambda.tf
│   ├── dynamodb.tf
│   └── ...
├── template.yaml               # SAM template
├── deploy.sh                   # Deployment script
└── docs/
    ├── UI_README.md            # UI documentation
    ├── REPORTING_GUIDE.md      # Reporting guide
    └── ...
```

## Documentation

- **[UI_README.md](UI_README.md)** - Desktop UI user guide
- **[QUICK_START_UI.md](QUICK_START_UI.md)** - Quick start guide
- **[REPORTING_GUIDE.md](REPORTING_GUIDE.md)** - Export and reporting guide
- **[DEPLOYMENT_INSTRUCTIONS.md](DEPLOYMENT_INSTRUCTIONS.md)** - Deployment guide
- **[terraform/README.md](terraform/README.md)** - Terraform documentation

## Requirements

### Desktop UI
- Python 3.11+
- boto3
- tkinter (built-in)
- tkcalendar

### AWS Infrastructure
- AWS Account with appropriate permissions
- S3 buckets for input/output
- Lambda functions (Python 3.13)
- DynamoDB table
- API Gateway (optional, for reports)

## Cost Estimation

**Per Timesheet:**
- Claude 3.5 Sonnet: ~$0.018
- Lambda execution: ~$0.001
- S3/DynamoDB: negligible

**Monthly (100 timesheets):** ~$1.90

## Troubleshooting

### UI Won't Launch
```bash
# Check Python
python3 --version  # Should be 3.11+

# Check dependencies
pip3 install boto3 tkcalendar

# Check permissions
chmod +x launch_ui.command
```

### AWS Credentials
```bash
# SSO login
aws sso login

# Or configure credentials
aws configure
```

### Module Not Found: tkcalendar
```bash
# Install in virtual environment
source venv/bin/activate
pip install tkcalendar
```

## Security

- ✅ S3 buckets encrypted at rest
- ✅ Public access blocked
- ✅ IAM least-privilege policies
- ✅ HTTPS-only API Gateway
- ✅ CloudWatch logging enabled
- ✅ Credentials never stored in app

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

- Check CloudWatch logs for errors
- Review `UI_README.md` for UI issues
- See `REPORTING_GUIDE.md` for export questions
- Check `DEPLOYMENT_INSTRUCTIONS.md` for deployment issues

## License

Private project - all rights reserved.

## Acknowledgments

Built with:
- **Python** - Application logic
- **Tkinter** - Desktop UI framework
- **AWS Lambda** - Serverless compute
- **Claude 3.5 Sonnet** - AI-powered OCR
- **DynamoDB** - NoSQL database
- **Terraform** - Infrastructure as code
- **SAM** - Lambda packaging

---

**Last Updated:** October 2025
**Version:** 2.0 - Added period exports, calendar pickers, and error correction workflow
