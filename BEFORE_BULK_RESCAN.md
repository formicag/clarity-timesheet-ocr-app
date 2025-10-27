# Pre-Bulk Rescan Checklist

## CRITICAL: Complete These Steps Before Flushing Database

### 1. Backup Current Data ✓
```bash
# Export current database to backup
python3 << 'EOF'
import boto3
import json
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('TimesheetOCR-dev')

# Scan all items
items = []
response = table.scan()
items.extend(response['Items'])

while 'LastEvaluatedKey' in response:
    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    items.extend(response['Items'])

# Save to file
backup_file = f"db_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(backup_file, 'w') as f:
    json.dump(items, f, indent=2, default=str)

print(f"✅ Backed up {len(items)} items to {backup_file}")
EOF
```

### 2. Verify AWS Quotas
- ✓ Amazon Nova Lite: 200 requests/minute
- ✓ Lambda concurrent executions: Check current limit
- ✓ DynamoDB write capacity: Check provisioned or on-demand

```bash
# Check Bedrock quotas
aws service-quotas list-service-quotas \
    --service-code bedrock \
    --region us-east-1 | grep -A 5 "Nova"

# Check Lambda concurrency
aws lambda get-account-settings --region us-east-1 | jq '.AccountLimit.ConcurrentExecutions'
```

### 3. Update Lambda with Failure Logging (CRITICAL!)

**Add this to lambda_function.py exception handler (lines 697-722):**

```python
except Exception as e:
    error_time = time.time() - overall_start

    log("="*80, "ERROR")
    log(f"❌ INVOCATION FAILED AFTER {error_time:.3f}s", "ERROR")
    log("="*80, "ERROR")
    log(f"Error type: {type(e).__name__}", "ERROR")
    log(f"Error message: {str(e)}", "ERROR")

    import traceback
    stack_trace = traceback.format_exc()
    log(f"Full stack trace:\n{stack_trace}", "ERROR")

    # === NEW: LOG FAILURE TO DATABASE ===
    try:
        # Determine failure type
        failure_type = "OCR_ERROR"
        if "parsing" in str(e).lower() or "json" in str(e).lower():
            failure_type = "PARSING_ERROR"
        elif "validation" in str(e).lower():
            failure_type = "VALIDATION_ERROR"
        elif "throttl" in str(e).lower():
            failure_type = "THROTTLING_ERROR"
        elif "textract" in str(e).lower():
            failure_type = "TEXTRACT_ERROR"

        # Get attempt count
        attempt_number = get_attempt_count(DYNAMODB_TABLE, key) + 1

        # Collect error details
        error_details = {
            'error_code': type(e).__name__,
            'processing_time': error_time,
            'stack_trace': stack_trace,
            's3_bucket': bucket,
            's3_region': 'us-east-1',
            'attempt_number': attempt_number,
            'cloudwatch_log_stream': context.log_stream_name if context else 'unknown'
        }

        # Add any available OCR data for debugging
        if 'metadata' in locals():
            error_details['raw_ocr_output'] = str(metadata)[:10000]

        if 'nova_usage' in locals():
            error_details['input_tokens'] = nova_usage.get('inputTokens', 0)
            error_details['output_tokens'] = nova_usage.get('outputTokens', 0)

        # Log the failure
        log_failed_image(
            table_name=DYNAMODB_TABLE,
            image_key=key,
            failure_type=failure_type,
            error_message=str(e),
            ocr_version=OCR_VERSION,
            error_details=error_details
        )
        log(f"📝 Logged failure to database", "INFO")

    except Exception as log_error:
        log(f"⚠️  Could not log failure: {log_error}", "WARN")
    # === END NEW CODE ===

    # Print partial performance report even on failure
    perf_metrics.print_report()

    return {
        'statusCode': 500,
        'body': json.dumps({
            'message': 'Error processing timesheet',
            'error': str(e),
            'error_type': type(e).__name__,
            'processing_time_seconds': round(error_time, 2),
            'stack_trace': stack_trace
        })
    }
```

### 4. Deploy Updated Lambda
```bash
cd /Users/gianlucaformica/Projects/clarity-timesheet-ocr-app

# Package Lambda
rm -f lambda_with_failure_logging.zip
cd src && zip -r ../lambda_with_failure_logging.zip *.py ../OCR_VERSION.txt && cd ..

# Deploy
aws lambda update-function-code \
    --function-name TimesheetOCR-ocr-dev \
    --zip-file fileb://lambda_with_failure_logging.zip \
    --region us-east-1

# Wait for update
aws lambda wait function-updated \
    --function-name TimesheetOCR-ocr-dev \
    --region us-east-1

echo "✅ Lambda updated with failure logging"
```

### 5. Test Failure Logging
```bash
# Trigger with invalid image to test failure logging
aws lambda invoke \
    --function-name TimesheetOCR-ocr-dev \
    --payload '{"Records":[{"s3":{"bucket":{"name":"timesheetocr-input-dev-016164185850"},"object":{"key":"INVALID_IMAGE.png"}}}]}' \
    --region us-east-1 \
    /tmp/test_failure.json

# Check if failure was logged
aws dynamodb scan \
    --table-name TimesheetOCR-dev \
    --filter-expression "RecordType = :type" \
    --expression-attribute-values '{":type":{"S":"FAILED_IMAGE"}}' \
    --region us-east-1 | jq '.Count'
```

### 6. Flush Database
```bash
python3 flush_database.py

# Verify empty
aws dynamodb scan \
    --table-name TimesheetOCR-dev \
    --select COUNT \
    --region us-east-1
```

### 7. Start Safe Bulk Rescan
```bash
# Make executable
chmod +x safe_bulk_rescan.py monitor_bulk_scan.py

# Start monitor in one terminal
python3 monitor_bulk_scan.py

# Start rescan in another terminal
python3 safe_bulk_rescan.py
```

## Safety Features Active

### Circuit Breaker
- ✓ Stops after 10 consecutive failures
- ✓ Stops if >50% failure rate (last 20 images)

### Progress Monitoring
- ✓ Checks database growth every 50 images
- ✓ Stops if no growth for 10 minutes

### Emergency Stop
- ✓ Create file to stop immediately:
  ```bash
  touch /tmp/STOP_RESCAN
  ```

### Resume Capability
- ✓ Progress saved every 10 images to `/tmp/rescan_progress.json`
- ✓ Can resume if interrupted

## Monitoring Commands

### Real-time Monitor
```bash
python3 monitor_bulk_scan.py
```

### Check Failed Images
```bash
# Count failures
aws dynamodb scan \
    --table-name TimesheetOCR-dev \
    --filter-expression "RecordType = :type" \
    --expression-attribute-values '{":type":{"S":"FAILED_IMAGE"}}' \
    --select COUNT \
    --region us-east-1

# View recent failures
aws dynamodb scan \
    --table-name TimesheetOCR-dev \
    --filter-expression "RecordType = :type" \
    --expression-attribute-values '{":type":{"S":"FAILED_IMAGE"}}' \
    --region us-east-1 | jq '.Items[] | {ImageKey, FailureType, ErrorMessage}'
```

### CloudWatch Logs
```bash
# Tail Lambda logs
aws logs tail /aws/lambda/TimesheetOCR-ocr-dev \
    --follow \
    --region us-east-1

# Filter for errors
aws logs tail /aws/lambda/TimesheetOCR-ocr-dev \
    --follow \
    --filter-pattern "ERROR" \
    --region us-east-1
```

## Expected Results

### Normal Operation
- Processing rate: ~20-40 images/minute
- Database growth: ~60-120 entries/minute (3 entries per image average)
- Failure rate: <5%

### Warning Signs
- ⚠️ Processing rate <10 images/minute
- ⚠️ Failure rate >10%
- ⚠️ No database growth for >5 minutes
- ⚠️ Many throttling errors

### Critical Issues (Auto-Stop)
- 🛑 10 consecutive failures
- 🛑 >50% failure rate
- 🛑 No database growth for 10 minutes

## Post-Rescan Validation

### 1. Check Total Entries
```bash
aws dynamodb scan \
    --table-name TimesheetOCR-dev \
    --select COUNT \
    --region us-east-1
```

### 2. Export Failed Images
Run in UI or:
```bash
python3 << 'EOF'
from src.failed_image_logger import export_failed_images_csv
export_failed_images_csv('TimesheetOCR-dev', 'failed_images_report.csv')
EOF
```

### 3. Validate Sample Images
```bash
# Pick random images and verify
aws dynamodb query \
    --table-name TimesheetOCR-dev \
    --key-condition-expression "ResourceName = :name" \
    --expression-attribute-values '{":name":{"S":"Nik_Coultas"}}' \
    --limit 5 \
    --region us-east-1
```

## Troubleshooting

### High Failure Rate
1. Check CloudWatch logs for error patterns
2. Export failed images CSV
3. Look for common failure types
4. Check if specific date ranges failing

### Stalled Progress
1. Check Lambda concurrency limits
2. Verify Bedrock quota not exceeded
3. Check for DynamoDB throttling
4. Review CloudWatch metrics

### Quota Exceeded
1. Reduce BATCH_SIZE in safe_bulk_rescan.py
2. Increase DELAY_BETWEEN_BATCHES
3. Wait for quota to reset (1 minute windows)

## Emergency Recovery

### Stop Everything
```bash
# Create stop file
touch /tmp/STOP_RESCAN

# Kill monitor
pkill -f monitor_bulk_scan

# Kill rescan
pkill -f safe_bulk_rescan
```

### Restore from Backup
```bash
python3 << 'EOF'
import boto3
import json

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('TimesheetOCR-dev')

# Load backup
with open('db_backup_YYYYMMDD_HHMMSS.json', 'r') as f:
    items = json.load(f)

# Restore
with table.batch_writer() as batch:
    for item in items:
        batch.put_item(Item=item)

print(f"✅ Restored {len(items)} items")
EOF
```
