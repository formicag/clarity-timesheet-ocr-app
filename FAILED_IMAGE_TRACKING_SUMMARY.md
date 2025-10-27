# Failed Image Tracking System - Implementation Summary

## Completed Work

### 1. OCR Version Tracking (COMPLETED)
**Files Created:**
- `OCR_VERSION.txt` - Version tracking file
- `src/ocr_version.py` - Version management module

**Files Modified:**
- `src/dynamodb_handler.py` - Added OCR version fields to all database entries
- `src/lambda_function.py` - Added OCR_VERSION import

**Database Fields Added:**
- `OCRVersion`: "2.0.0"
- `OCRBuildDate`: "2025-10-25"
- `OCRDescription`: "Amazon Nova Lite + Real-time Coverage Tracking"
- `OCRFullVersion`: "2.0.0-2025-10-25"

**Status:** Deployed and tested successfully

### 2. Failed Image Logger Module (COMPLETED)
**File Created:** `src/failed_image_logger.py`

**Functions:**
- `log_failed_image()` - Log failure with comprehensive details
- `get_attempt_count()` - Count retry attempts
- `get_all_failed_images()` - Retrieve all failures
- `export_failed_images_csv()` - Export to CSV
- `get_failure_statistics()` - Failure analytics

**Database Schema:**
```
Partition Key: ImageKey (S)
Sort Key: FailureTimestamp (S)
RecordType: "FAILED_IMAGE"

Attributes:
- FailureType (OCR_ERROR, PARSING_ERROR, VALIDATION_ERROR)
- ErrorMessage (5000 chars)
- ErrorCode
- OCRVersion, OCRBuildDate, OCRFullVersion
- ModelId
- ProcessingTimeSeconds
- InputTokens, OutputTokens
- RawOCROutput (10000 chars)
- ValidationErrors (2000 chars)
- S3Bucket, S3Region
- ImageSize
- AttemptNumber
- StackTrace (5000 chars)
- CloudWatchLogStream
```

## Remaining Tasks

### 3. Lambda Failure Logging Integration (IN PROGRESS)
**File to Modify:** `src/lambda_function.py`

**Location:** Lines 697-722 (exception handler)

**Changes Needed:**
```python
except Exception as e:
    # Existing error logging...

    # Determine failure type
    failure_type = "OCR_ERROR"
    if "parsing" in str(e).lower() or "json" in str(e).lower():
        failure_type = "PARSING_ERROR"
    elif "validation" in str(e).lower():
        failure_type = "VALIDATION_ERROR"
    elif "throttl" in str(e).lower():
        failure_type = "THROTTLING_ERROR"

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

    # Add any available OCR data
    if 'metadata' in locals():
        error_details['raw_ocr_output'] = str(metadata)

    # Log the failure
    log_failed_image(
        table_name=DYNAMODB_TABLE,
        image_key=key,
        failure_type=failure_type,
        error_message=str(e),
        ocr_version=OCR_VERSION,
        error_details=error_details
    )
```

### 4. UI Export Button (PENDING)
**File to Modify:** `timesheet_ui.py`

**Changes Needed:**
1. Add import: `from src.failed_image_logger import export_failed_images_csv, get_failure_statistics`
2. Add button to sidebar:
   ```python
   if st.sidebar.button("📊 Export Failed Images"):
       with st.spinner("Exporting failed images..."):
           stats = get_failure_statistics(table_name)

           if stats['total_failures'] == 0:
               st.success("No failed images to export!")
           else:
               # Export to temp file
               import tempfile
               temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
               count = export_failed_images_csv(table_name, temp_file.name)

               # Read file for download
               with open(temp_file.name, 'rb') as f:
                   csv_data = f.read()

               # Show stats
               st.success(f"Exported {count} failed images!")
               st.info(f"Unique images: {stats['unique_images']}")
               st.info(f"Recent failures (24h): {stats['recent_failures_24h']}")

               # Show failure breakdown
               st.write("**Failure Types:**")
               for ftype, count in stats['failure_types'].items():
                   st.write(f"- {ftype}: {count}")

               # Download button
               st.download_button(
                   label="📥 Download Failed Images Report",
                   data=csv_data,
                   file_name=f"failed_images_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                   mime="text/csv"
               )
   ```

### 5. Testing (PENDING)
**Test Plan:**
1. Trigger a failure manually (use invalid image)
2. Verify failure logged to DynamoDB
3. Check all fields populated correctly
4. Test UI export button
5. Verify CSV export contains all data
6. Test statistics display

## Benefits

1. **Pattern Analysis:** Export CSV to analyze failure patterns
2. **Version Tracking:** Know which OCR version failed
3. **Debugging:** Full stack traces and CloudWatch log stream references
4. **Retry Management:** Track attempt numbers to avoid infinite loops
5. **OCR Improvement:** Use raw OCR output to improve prompts
6. **Statistics:** Real-time failure analytics

## CSV Export Columns

The exported CSV will contain:
- ImageKey
- FailureTimestamp
- FailureType
- ErrorMessage
- ErrorCode
- OCRVersion, OCRBuildDate, OCRFullVersion
- ModelId
- ProcessingTimeSeconds
- InputTokens, OutputTokens
- ValidationErrors
- S3Bucket
- ImageSize
- AttemptNumber
- CloudWatchLogStream
- RawOCROutput
- StackTrace

## Next Steps

1. Complete Lambda exception handler update
2. Add UI export button
3. Test failure logging with intentional error
4. Deploy updated Lambda
5. Document usage in main README
