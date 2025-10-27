# Automated Bulk Rescan Workflow

## Quick Start - Fully Automated (Recommended)

Run the entire workflow with a single command:

```bash
./full_rescan_workflow.sh
```

This automatically:
1. ✅ Backs up your database
2. ✅ Flushes the database
3. ✅ Deploys Lambda with failure logging
4. ✅ Runs safe bulk rescan with circuit breaker
5. ✅ Waits for processing to complete
6. ✅ Auto-imports all projects
7. ✅ Generates failure report
8. ✅ Displays final statistics

**Total time**: ~40-50 minutes for ~1400 images

---

## Manual Step-by-Step (If you prefer control)

### Step 1: Backup & Deploy

```bash
# Backup database
python3 << 'EOF'
import boto3, json
from datetime import datetime
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('TimesheetOCR-dev')
response = table.scan()
items = response['Items']
while 'LastEvaluatedKey' in response:
    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    items.extend(response['Items'])
with open(f"db_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
    json.dump(items, f, indent=2, default=str)
print(f"✅ Backed up {len(items)} items")
EOF

# Flush database
python3 flush_database.py

# Deploy Lambda
cd src && zip -q -r ../lambda_deploy.zip *.py ../OCR_VERSION.txt && cd ..
aws lambda update-function-code \
    --function-name TimesheetOCR-ocr-dev \
    --zip-file fileb://lambda_deploy.zip \
    --region us-east-1
aws lambda wait function-updated --function-name TimesheetOCR-ocr-dev --region us-east-1
```

### Step 2: Run Bulk Rescan

**Terminal 1** - Run rescan:
```bash
python3 safe_bulk_rescan.py
```

**Terminal 2** (optional) - Monitor progress:
```bash
python3 monitor_bulk_scan.py
```

### Step 3: Post-Processing

After rescan completes:
```bash
python3 post_rescan_automation.py
```

This automatically:
- Waits for Lambda processing
- Imports all projects
- Generates failure reports

---

## Safety Features

### Circuit Breaker
- Stops after **10 consecutive failures**
- Stops if **>50% failure rate** (last 20 images)

### Progress Monitoring
- Checks database growth every 50 images
- Stops if no growth for 10 minutes

### Emergency Stop
```bash
# Create this file to stop immediately:
touch /tmp/STOP_RESCAN
```

### Resume Capability
Progress saved to `/tmp/rescan_progress.json` - rescan can resume if interrupted

---

## Monitoring Commands

### Check Database Count
```bash
aws dynamodb scan --table-name TimesheetOCR-dev --select COUNT --region us-east-1
```

### View Recent Failures
```bash
aws dynamodb scan \
    --table-name TimesheetOCR-dev \
    --filter-expression "RecordType = :type" \
    --expression-attribute-values '{":type":{"S":"FAILED_IMAGE"}}' \
    --region us-east-1 | jq '.Items[] | {ImageKey, FailureType, ErrorMessage}'
```

### Watch CloudWatch Logs
```bash
aws logs tail /aws/lambda/TimesheetOCR-ocr-dev --follow --region us-east-1
```

---

## Expected Performance

### Normal Operation
- Processing rate: 20-40 images/minute
- Database growth: 60-120 entries/minute (~3 entries per image)
- Failure rate: <5%

### Warning Signs
- ⚠️ Processing rate <10 images/minute
- ⚠️ Failure rate >10%
- ⚠️ No database growth for >5 minutes

### Auto-Stop Triggers
- 🛑 10 consecutive failures
- 🛑 >50% failure rate
- 🛑 No database growth for 10 minutes

---

## Files Created

After workflow completes:
- `db_backup_TIMESTAMP.json` - Database backup
- `failed_images_TIMESTAMP.csv` - Failure analysis report
- `project_master.json` - Auto-updated with all detected projects
- `/tmp/rescan_progress.json` - Resume checkpoint

---

## Troubleshooting

### High Failure Rate
1. Check `failed_images_TIMESTAMP.csv` for error patterns
2. Look for common failure types
3. Check CloudWatch logs for specific errors

### Stalled Progress
1. Check Lambda concurrency: `aws lambda get-account-settings --region us-east-1`
2. Check Bedrock quota not exceeded
3. Review CloudWatch metrics

### Resume After Interruption
Just run `python3 safe_bulk_rescan.py` again - it will offer to resume from checkpoint

---

## Post-Workflow

### View Results in UI
```bash
python3 timesheet_ui.py
```

### Check Imported Projects
```bash
cat project_master.json | jq '.projects[] | {code, name}'
```

### Analyze Failures (if any)
Open `failed_images_TIMESTAMP.csv` in Excel/Numbers to analyze failure patterns

---

## Quick Reference

| Task | Command |
|------|---------|
| **Full automated workflow** | `./full_rescan_workflow.sh` |
| **Manual rescan only** | `python3 safe_bulk_rescan.py` |
| **Monitor progress** | `python3 monitor_bulk_scan.py` |
| **Post-processing only** | `python3 post_rescan_automation.py` |
| **Emergency stop** | `touch /tmp/STOP_RESCAN` |
| **View UI** | `python3 timesheet_ui.py` |

---

## Architecture

```
full_rescan_workflow.sh
├── 1. Backup database
├── 2. Flush database
├── 3. Deploy Lambda (with failure logging)
├── 4. safe_bulk_rescan.py
│   ├── Pre-flight checks
│   ├── Circuit breaker monitoring
│   ├── Progress monitoring
│   └── Async Lambda triggers
└── 5. post_rescan_automation.py
    ├── Wait for processing complete
    ├── Auto-import projects
    ├── Generate failure report
    └── Display statistics
```

---

## Need Help?

- Check CloudWatch logs for errors
- Review failed_images CSV for patterns
- Ensure AWS credentials are active (`aws sts get-caller-identity`)
- Verify quotas not exceeded
