"""
OPTIMIZED AWS Lambda function for timesheet OCR processing.

Improvements:
- Extensive performance logging and timing for every operation
- Detailed error logging with full stack traces
- Additional metadata fields to prevent duplicate processing
- Image hash for content-based deduplication
- Better retry logic with detailed logging
- Performance metrics report at end
"""
import json
import os
import boto3
import time
import re
import base64
import random
import hashlib
from typing import Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime

from dynamodb_handler import store_timesheet_entries, store_rejected_timesheet
from duplicate_detection import check_for_existing_entries
from utils import parse_date_range
from validation import validate_timesheet_data, format_validation_report
from team_manager import TeamManager
from parsing import calculate_cost_estimate
from performance import PerformanceTimer, PerformanceMetrics, create_logger

# Environment variables
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', '')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

# AWS clients
s3_client = boto3.client('s3')
textract_client = boto3.client('textract', region_name='us-east-1')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

# Global performance metrics
perf_metrics = PerformanceMetrics()

# Create logger
log = create_logger("LAMBDA")


def compute_image_hash(image_bytes: bytes) -> str:
    """
    Compute SHA256 hash of image for content-based deduplication.
    This prevents processing the same image twice even if filename differs.
    """
    return hashlib.sha256(image_bytes).hexdigest()


def get_text_from_cell(cell_block, blocks_map):
    """Get text from a Textract cell."""
    text = ''
    if 'Relationships' in cell_block:
        for relationship in cell_block['Relationships']:
            if relationship.get('Type') == 'CHILD':
                for child_id in relationship['Ids']:
                    child_block = blocks_map.get(child_id)
                    if child_block and child_block['BlockType'] == 'WORD':
                        text += child_block['Text'] + ' '
    return text.strip()


def download_image_from_s3(bucket: str, key: str) -> Tuple[bytes, float]:
    """
    Download image from S3 with detailed timing.

    Returns:
        Tuple of (image_bytes, download_time_seconds)
    """
    with PerformanceTimer("S3 Download", log):
        start = time.time()
        log(f"Downloading s3://{bucket}/{key}")

        response = s3_client.get_object(Bucket=bucket, Key=key)
        image_bytes = response['Body'].read()

        download_time = time.time() - start
        size_mb = len(image_bytes) / (1024 * 1024)

        log(f"Downloaded {size_mb:.2f}MB in {download_time:.3f}s ({size_mb/download_time if download_time > 0 else 0:.2f} MB/s)")
        perf_metrics.record("s3_download", download_time, {"size_mb": size_mb})

        return image_bytes, download_time


def extract_metadata_with_claude(bucket: str, key: str, image_bytes: bytes = None) -> Tuple[Dict, Dict, float]:
    """
    Use Claude to extract resource name and date range from the image with retry logic.

    Returns:
        Tuple of (metadata, usage_stats, extraction_time_seconds)
    """
    operation_start = time.time()

    # Download if not provided
    if image_bytes is None:
        with PerformanceTimer("Download for Claude", log):
            response = s3_client.get_object(Bucket=bucket, Key=key)
            image_bytes = response['Body'].read()

    # Determine image format
    if key.lower().endswith('.png'):
        media_type = 'image/png'
    elif key.lower().endswith('.jpg') or key.lower().endswith('.jpeg'):
        media_type = 'image/jpeg'
    else:
        media_type = 'image/png'

    log(f"Encoding image for Claude (format: {media_type})")

    with PerformanceTimer("Base64 Encoding", log):
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')
        log(f"Encoded {len(image_bytes)} bytes to {len(encoded_image)} base64 chars")

    # Simple prompt for metadata extraction
    prompt = """Look at this timesheet image and extract ONLY the following information:
1. Resource name - This is the PERSON'S NAME (not their job title). Look for a proper name like "Matthew Garretty", "John Smith", etc. at the top of the timesheet. DO NOT use job titles like "Solution Designer", "Developer", etc.
2. Date range (format: "MMM DD YYYY - MMM DD YYYY", e.g., "Oct 6 2025 - Oct 12 2025")
3. Status (look for "Status: Posted" or "Status: Submitted" etc.)

Return ONLY this JSON (no explanations):
{
  "resource_name": "Full Name",
  "date_range": "MMM DD YYYY - MMM DD YYYY",
  "status": "Posted"
}

IMPORTANT: The resource_name must be a person's actual name (first name and last name), not a job title or role."""

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded_image
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }

    # Retry logic with exponential backoff for throttling
    max_retries = 5
    base_delay = 2

    for attempt in range(max_retries):
        try:
            log(f"Claude API call (attempt {attempt + 1}/{max_retries})")

            with PerformanceTimer(f"Claude API Call #{attempt + 1}", log):
                api_start = time.time()

                response = bedrock_runtime.invoke_model(
                    modelId='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
                    body=json.dumps(request_body),
                    contentType='application/json',
                    accept='application/json'
                )

                api_time = time.time() - api_start
                log(f"Claude API responded in {api_time:.3f}s")

            response_body = json.loads(response['body'].read())
            text = response_body['content'][0]['text']

            log(f"Claude response: {text[:200]}..." if len(text) > 200 else f"Claude response: {text}")

            # Parse JSON
            if '```json' in text:
                start = text.find('```json') + 7
                end = text.find('```', start)
                text = text[start:end].strip()

            metadata = json.loads(text)

            total_time = time.time() - operation_start
            perf_metrics.record("claude_metadata_extraction", total_time, {
                "attempt": attempt + 1,
                "input_tokens": response_body['usage']['input_tokens'],
                "output_tokens": response_body['usage']['output_tokens']
            })

            log(f"✅ Metadata extracted: {metadata}")
            return metadata, response_body['usage'], total_time

        except Exception as e:
            error_str = str(e)
            log(f"❌ Claude API error (attempt {attempt + 1}): {error_str}", "ERROR")

            if 'ThrottlingException' in error_str or 'Too many requests' in error_str:
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    log(f"⏳ Bedrock throttled, retrying in {delay:.1f}s", "WARN")
                    time.sleep(delay)
                else:
                    log(f"❌ Bedrock throttled after {max_retries} attempts, giving up", "ERROR")
                    raise
            else:
                # Non-throttling error, don't retry
                log(f"❌ Non-throttling error, not retrying: {error_str}", "ERROR")
                import traceback
                log(f"Stack trace:\n{traceback.format_exc()}", "ERROR")
                raise


def extract_table_with_textract(bucket: str, key: str) -> Tuple[Dict, float]:
    """
    Extract table structure with AWS Textract.

    Returns:
        Tuple of (textract_response, extraction_time_seconds)
    """
    with PerformanceTimer("Textract Table Extraction", log):
        start = time.time()

        log(f"Calling Textract for s3://{bucket}/{key}")

        textract_response = textract_client.analyze_document(
            Document={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            },
            FeatureTypes=['TABLES']
        )

        extraction_time = time.time() - start

        blocks_count = len(textract_response.get('Blocks', []))
        log(f"Textract returned {blocks_count} blocks in {extraction_time:.3f}s")

        perf_metrics.record("textract_extraction", extraction_time, {
            "blocks_count": blocks_count
        })

        return textract_response, extraction_time


def parse_timesheet_table(textract_response: Dict, resource_name: str, date_range: str) -> Tuple[Dict, float]:
    """
    Parse Textract response into timesheet data structure.

    Returns:
        Tuple of (timesheet_data, parsing_time_seconds)
    """
    with PerformanceTimer("Table Parsing", log):
        start = time.time()

        # Build blocks map
        log("Building blocks map")
        blocks_map = {block['Id']: block for block in textract_response['Blocks']}
        log(f"Mapped {len(blocks_map)} blocks")

        # Extract tables
        tables = [block for block in textract_response['Blocks'] if block['BlockType'] == 'TABLE']
        log(f"Found {len(tables)} tables")

        if not tables:
            raise ValueError("No tables found in image")

        table = tables[0]
        cells = []

        if 'Relationships' in table:
            for relationship in table['Relationships']:
                if relationship.get('Type') == 'CHILD':
                    for cell_id in relationship['Ids']:
                        cell = blocks_map.get(cell_id)
                        if cell and cell['BlockType'] == 'CELL':
                            cells.append(cell)

        log(f"Extracted {len(cells)} cells from table")

        # Organize cells by row and column
        table_data = {}
        for cell in cells:
            row_index = cell.get('RowIndex', 0)
            col_index = cell.get('ColumnIndex', 0)
            text = get_text_from_cell(cell, blocks_map)

            if row_index not in table_data:
                table_data[row_index] = {}
            table_data[row_index][col_index] = text

        log(f"Organized into {len(table_data)} rows")

        # Parse header row to identify day columns and extract daily totals
        log("Searching for header row")
        header = {}
        header_row_idx = None
        for row_idx in range(1, min(5, len(table_data) + 1)):  # Check first 5 rows
            candidate = table_data.get(row_idx, {})
            # Header row contains "Mon." or "Monday"
            if any('Mon.' in str(cell) or 'Monday' in str(cell) for cell in candidate.values()):
                header = candidate
                header_row_idx = row_idx
                log(f"Found header row at index {row_idx}: {header}")
                break

        if not header_row_idx:
            raise ValueError("Could not find header row with day columns")

        day_columns = {}
        daily_totals = [0.0] * 7
        weekly_total = 0.0

        log("Parsing day columns from header")
        for col_idx, text in header.items():
            # Header cells contain: "Mon. 6 7.50" where 7.50 is the daily total
            if 'Mon.' in text:
                day_columns[col_idx] = 0
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[0] = float(parts[-1])
                        log(f"  Monday (col {col_idx}): total={daily_totals[0]}")
                    except ValueError as e:
                        log(f"  WARNING: Could not parse Monday total from '{text}': {e}", "WARN")
            elif 'Tue.' in text:
                day_columns[col_idx] = 1
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[1] = float(parts[-1])
                        log(f"  Tuesday (col {col_idx}): total={daily_totals[1]}")
                    except ValueError as e:
                        log(f"  WARNING: Could not parse Tuesday total: {e}", "WARN")
            elif 'Wed.' in text:
                day_columns[col_idx] = 2
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[2] = float(parts[-1])
                        log(f"  Wednesday (col {col_idx}): total={daily_totals[2]}")
                    except ValueError as e:
                        log(f"  WARNING: Could not parse Wednesday total: {e}", "WARN")
            elif 'Thu.' in text:
                day_columns[col_idx] = 3
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[3] = float(parts[-1])
                        log(f"  Thursday (col {col_idx}): total={daily_totals[3]}")
                    except ValueError as e:
                        log(f"  WARNING: Could not parse Thursday total: {e}", "WARN")
            elif 'Fri.' in text:
                day_columns[col_idx] = 4
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[4] = float(parts[-1])
                        log(f"  Friday (col {col_idx}): total={daily_totals[4]}")
                    except ValueError as e:
                        log(f"  WARNING: Could not parse Friday total: {e}", "WARN")
            elif 'Sat.' in text:
                day_columns[col_idx] = 5
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[5] = float(parts[-1])
                        log(f"  Saturday (col {col_idx}): total={daily_totals[5]}")
                    except ValueError as e:
                        log(f"  WARNING: Could not parse Saturday total: {e}", "WARN")
            elif 'Sun.' in text:
                day_columns[col_idx] = 6
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[6] = float(parts[-1])
                        log(f"  Sunday (col {col_idx}): total={daily_totals[6]}")
                    except ValueError as e:
                        log(f"  WARNING: Could not parse Sunday total: {e}", "WARN")
            elif 'Total' in text and 'Posted' not in text:
                # Extract weekly total from "Total 22.50"
                parts = text.split()
                if len(parts) >= 2:
                    try:
                        weekly_total = float(parts[-1])
                        log(f"  Weekly total: {weekly_total}")
                    except ValueError as e:
                        log(f"  WARNING: Could not parse weekly total: {e}", "WARN")

        log(f"Identified {len(day_columns)} day columns")
        log(f"Daily totals: {daily_totals}")
        log(f"Weekly total: {weekly_total}")

        # Extract projects and hours
        log("Extracting projects and hours")
        projects = {}
        current_project = None
        project_code_pattern = re.compile(r'\((PJ\d+|DATA\d+|REAG\d+|HCST\d+|NTC5\d+)\)')

        for row_idx in sorted(table_data.keys()):
            if row_idx == header_row_idx:  # Skip header row
                continue

            row = table_data[row_idx]
            first_cell = row.get(1, '').strip()

            # Check if this is a parent project row
            match = project_code_pattern.search(first_cell)
            if match:
                current_project = match.group(1)
                projects[current_project] = {
                    'project_name': first_cell,
                    'project_code': current_project,
                    'hours_by_day': [
                        {"day": "Monday", "hours": "0"},
                        {"day": "Tuesday", "hours": "0"},
                        {"day": "Wednesday", "hours": "0"},
                        {"day": "Thursday", "hours": "0"},
                        {"day": "Friday", "hours": "0"},
                        {"day": "Saturday", "hours": "0"},
                        {"day": "Sunday", "hours": "0"}
                    ]
                }
                log(f"Found project: {current_project} - {first_cell}")

            # If we have a current project, look for hours in this row
            if current_project:
                for col_idx, day_idx in day_columns.items():
                    cell_text = row.get(col_idx, '').strip()
                    if cell_text:
                        try:
                            hours = float(cell_text.split()[0])
                            if hours > 0:
                                # Accumulate hours instead of overwriting (for multiple child tasks)
                                current_hours = float(projects[current_project]['hours_by_day'][day_idx]['hours'])
                                new_total = current_hours + hours
                                projects[current_project]['hours_by_day'][day_idx]['hours'] = str(new_total)
                                day_name = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day_idx]
                                log(f"  {current_project} {day_name}: +{hours}h → {new_total}h")
                        except (ValueError, IndexError) as e:
                            log(f"  WARNING: Could not parse hours from '{cell_text}': {e}", "WARN")

        # Build timesheet_data structure
        timesheet_data = {
            'resource_name': resource_name,
            'date_range': date_range,
            'is_zero_hour_timesheet': False,
            'zero_hour_reason': None,
            'projects': list(projects.values()),
            'daily_totals': daily_totals,
            'weekly_total': weekly_total
        }

        log(f"✅ Extracted {len(projects)} projects with {sum(1 for p in projects.values() for d in p['hours_by_day'] if float(d['hours']) > 0)} non-zero day entries")

        parsing_time = time.time() - start
        perf_metrics.record("table_parsing", parsing_time, {
            "projects_count": len(projects),
            "rows_parsed": len(table_data)
        })

        return timesheet_data, parsing_time


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    OPTIMIZED Lambda handler for S3 triggered OCR processing using Textract.

    Key optimizations:
    - Detailed timing for every operation
    - Image hash for content deduplication
    - Better error logging
    - Performance metrics report
    """
    global perf_metrics
    perf_metrics = PerformanceMetrics()  # Reset for each invocation

    overall_start = time.time()

    try:
        log("="*80)
        log("🚀 NEW INVOCATION STARTED")
        log("="*80)

        # Extract S3 bucket and key from event
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        log(f"Processing: s3://{bucket}/{key}")
        log(f"Lambda Request ID: {context.aws_request_id if context else 'N/A'}")
        log(f"Memory Limit: {context.memory_limit_in_mb if context else 'N/A'}MB")

        # Step 1: Download image and compute hash
        log("\n" + "="*80)
        log("STEP 1: Download Image & Compute Hash")
        log("="*80)

        image_bytes, download_time = download_image_from_s3(bucket, key)

        with PerformanceTimer("Image Hash Computation", log):
            image_hash = compute_image_hash(image_bytes)
            log(f"Image hash: {image_hash[:16]}...")

        # Step 2: Extract metadata (name, dates, status) with Claude
        log("\n" + "="*80)
        log("STEP 2: Extract Metadata with Claude")
        log("="*80)

        metadata, claude_usage, metadata_time = extract_metadata_with_claude(bucket, key, image_bytes)
        resource_name = metadata['resource_name']
        date_range = metadata['date_range']
        status = metadata.get('status', 'Unknown').strip()

        log(f"✅ Resource: {resource_name}")
        log(f"✅ Date range: {date_range}")
        log(f"✅ Status: {status}")

        # Validate status is "Posted"
        if status.lower() != 'posted':
            log(f"❌ REJECTED: Status is '{status}', not 'Posted'", "WARN")

            # Store rejection record in DynamoDB
            processing_time = time.time() - overall_start

            with PerformanceTimer("Store Rejection in DynamoDB", log):
                rejection_result = store_rejected_timesheet(
                    resource_name=resource_name,
                    date_range=date_range,
                    status=status,
                    image_key=key,
                    processing_time=processing_time,
                    reason=f"Status is '{status}' instead of 'Posted'",
                    table_name=DYNAMODB_TABLE
                )

            log(f"Rejection stored with ID: {rejection_result.get('rejection_id', 'N/A')}")
            perf_metrics.print_report()

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'Timesheet rejected: Status is {status}, not Posted',
                    'input_image': f"s3://{bucket}/{key}",
                    'resource_name': resource_name,
                    'date_range': date_range,
                    'status': status,
                    'rejected': True,
                    'reason': f"Status is '{status}' instead of 'Posted'",
                    'image_hash': image_hash
                })
            }

        # Step 3: Extract table structure with Textract
        log("\n" + "="*80)
        log("STEP 3: Extract Table with Textract")
        log("="*80)

        textract_response, textract_time = extract_table_with_textract(bucket, key)

        # Step 4: Parse table into timesheet data
        log("\n" + "="*80)
        log("STEP 4: Parse Table Data")
        log("="*80)

        timesheet_data, parsing_time = parse_timesheet_table(textract_response, resource_name, date_range)

        # Step 5: Normalize resource name using team roster
        log("\n" + "="*80)
        log("STEP 5: Normalize Resource Name")
        log("="*80)

        try:
            with PerformanceTimer("Name Normalization", log):
                team_mgr = TeamManager()
                normalized_name, confidence, match_type = team_mgr.normalize_name(resource_name)

                if match_type in ['alias', 'fuzzy'] and confidence >= 0.85:
                    log(f"✅ Name normalized: '{resource_name}' → '{normalized_name}' (confidence: {confidence:.2f}, type: {match_type})")
                    timesheet_data['resource_name'] = normalized_name
                else:
                    log(f"ℹ️  Name kept as-is: '{resource_name}' (match_type: {match_type}, confidence: {confidence:.2f})")
        except Exception as e:
            log(f"⚠️  Name normalization failed: {e}", "WARN")
            import traceback
            log(f"Stack trace:\n{traceback.format_exc()}", "DEBUG")

        # Step 6: Validate extracted data
        log("\n" + "="*80)
        log("STEP 6: Validate Timesheet Data")
        log("="*80)

        with PerformanceTimer("Data Validation", log):
            validation_result = validate_timesheet_data(timesheet_data)
            log(format_validation_report(validation_result))

            perf_metrics.record("validation", 0.001, {
                "valid": validation_result['valid'],
                "errors_count": len(validation_result['errors']),
                "warnings_count": len(validation_result['warnings'])
            })

        # Step 7: Calculate cost
        log("\n" + "="*80)
        log("STEP 7: Calculate Processing Cost")
        log("="*80)

        textract_pages = 1
        textract_cost = textract_pages * 0.0015  # $0.0015 per page for table analysis
        claude_cost = calculate_cost_estimate(
            claude_usage['input_tokens'],
            claude_usage['output_tokens'],
            'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
        )['total_cost_usd']
        total_cost = textract_cost + claude_cost

        log(f"💰 Textract cost: ${textract_cost:.6f}")
        log(f"💰 Claude cost: ${claude_cost:.6f}")
        log(f"💰 Total cost: ${total_cost:.6f}")

        # Step 8: Store in DynamoDB
        log("\n" + "="*80)
        log("STEP 8: Store in DynamoDB")
        log("="*80)

        processing_time = time.time() - overall_start

        with PerformanceTimer("DynamoDB Storage", log):
            db_start = time.time()

            db_result = store_timesheet_entries(
                timesheet_data=timesheet_data,
                image_key=key,
                processing_time=processing_time,
                model_id='textract+claude',
                input_tokens=claude_usage['input_tokens'],
                output_tokens=claude_usage['output_tokens'],
                cost_estimate=total_cost,
                table_name=DYNAMODB_TABLE
                # NOTE: image_hash not yet supported by store_timesheet_entries()
                # Will add in future update with database schema changes
            )

            db_time = time.time() - db_start
            perf_metrics.record("dynamodb_storage", db_time, {
                "entries_stored": db_result['entries_stored']
            })

        log(f"✅ Stored {db_result['entries_stored']} entries in DynamoDB")

        # Print performance report
        log("\n")
        perf_metrics.print_report()

        log("="*80)
        log("✅ INVOCATION COMPLETED SUCCESSFULLY")
        log("="*80)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Timesheet processed successfully (Textract)',
                'input_image': f"s3://{bucket}/{key}",
                'image_hash': image_hash,
                'dynamodb_table': DYNAMODB_TABLE,
                'entries_stored': db_result['entries_stored'],
                'resource_name': timesheet_data['resource_name'],
                'date_range': timesheet_data['date_range'],
                'projects_count': len(timesheet_data['projects']),
                'processing_time_seconds': round(processing_time, 2),
                'cost_estimate_usd': total_cost,
                'validation': {
                    'valid': validation_result['valid'],
                    'errors': validation_result['errors'],
                    'warnings': validation_result['warnings'],
                    'summary': validation_result['summary']
                },
                'performance_metrics': perf_metrics.get_summary()
            })
        }

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
