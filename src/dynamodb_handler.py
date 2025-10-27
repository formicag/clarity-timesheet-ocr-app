"""
DynamoDB handler for storing timesheet data.
"""
import boto3
from datetime import datetime
from decimal import Decimal
from typing import Dict, List
from botocore.config import Config
from utils import (
    parse_date_range,
    generate_week_dates,
    is_valid_project_code,
    normalize_project_code,
    parse_hours,
    format_date_for_csv,
    validate_timesheet_data
)
from bank_holidays import is_bank_holiday
from coverage_tracker import update_coverage, get_week_commencing
from ocr_version import OCR_VERSION

# Configure boto3 with retries for transient errors
boto_config = Config(
    retries={
        'max_attempts': 10,
        'mode': 'adaptive'
    },
    region_name='us-east-1'
)
dynamodb = boto3.resource('dynamodb', config=boto_config)


def convert_float_to_decimal(obj):
    """Convert float values to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_float_to_decimal(item) for item in obj]
    return obj


def check_existing_entries(table, resource_key: str, date_str: str) -> Dict[str, Dict]:
    """
    Check for existing entries for a person on a specific date.

    Args:
        table: DynamoDB table resource
        resource_key: ResourceName (e.g., "Neil_Pomfret")
        date_str: Date in YYYY-MM-DD format

    Returns:
        Dict mapping project_code -> existing item data
    """
    try:
        response = table.query(
            KeyConditionExpression='ResourceName = :rn AND begins_with(DateProjectCode, :date)',
            ExpressionAttributeValues={
                ':rn': resource_key,
                ':date': date_str
            }
        )

        existing = {}
        for item in response.get('Items', []):
            # Extract project code from DateProjectCode (format: "YYYY-MM-DD#PJXXXXXX")
            date_project = item.get('DateProjectCode', '')
            if '#' in date_project:
                parts = date_project.split('#')
                if len(parts) == 2:
                    project_code = parts[1]
                    existing[project_code] = item

        return existing

    except Exception as e:
        print(f"Warning: Failed to check existing entries: {e}")
        return {}


def store_timesheet_entries(
    timesheet_data: dict,
    image_key: str,
    processing_time: float,
    model_id: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_estimate: float = 0.0,
    table_name: str = None,
    image_metadata: dict = None
) -> Dict:
    """
    Store timesheet entries in DynamoDB.

    Table Design:
    - Partition Key: ResourceName (e.g., "Nik_Coultas")
    - Sort Key: Date#ProjectCode (e.g., "2025-09-29#PJ021931")
    - For zero-hour timesheets: Sort Key is "WEEK#YYYY-MM-DD" to track submission

    This allows efficient queries:
    - Get all entries for a resource
    - Get all entries for a resource in a date range
    - Get all entries for a specific project
    - Track which weeks have submissions (including zero-hour)

    Args:
        timesheet_data: Dictionary containing parsed timesheet data
        image_key: S3 key of source image
        processing_time: Processing time in seconds
        model_id: Bedrock model ID used
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost_estimate: Estimated cost in USD
        table_name: DynamoDB table name (from environment)
        image_metadata: Optional image metadata (resolution, format, size, etc.)

    Returns:
        Dictionary with summary of stored entries
    """
    print(f"[DEBUG store_timesheet_entries] ENTRY - table_name: {table_name}")

    if not table_name:
        raise ValueError("DynamoDB table name not provided")

    table = dynamodb.Table(table_name)
    print(f"[DEBUG store_timesheet_entries] Created table object: {table.name}")

    # Extract basic info
    resource_name = timesheet_data.get('resource_name', 'Unknown')
    date_range_str = timesheet_data.get('date_range', '')
    is_zero_hour = timesheet_data.get('is_zero_hour_timesheet', False)
    zero_hour_reason = timesheet_data.get('zero_hour_reason', None)

    # Parse date range
    try:
        start_date, end_date = parse_date_range(date_range_str)
        week_dates = generate_week_dates(start_date, end_date)
    except ValueError as e:
        raise ValueError(f"Error processing date range: {str(e)}")

    # Clean resource name for partition key
    resource_key = resource_name.replace(' ', '_')

    # Prepare entries
    entries_stored = 0
    processing_timestamp = datetime.utcnow().isoformat() + 'Z'

    # Handle zero-hour timesheets specially
    if is_zero_hour:
        # Create a single entry to track that this week was submitted (even with 0 hours)
        item = {
            # Primary keys
            'ResourceName': resource_key,
            'DateProjectCode': f"WEEK#{start_date.strftime('%Y-%m-%d')}",

            # Attributes
            'Date': start_date.strftime('%Y-%m-%d'),
            'IsZeroHourTimesheet': True,
            'ZeroHourReason': zero_hour_reason or 'ABSENCE',
            'ResourceNameDisplay': resource_name,

            # Metadata
            'SourceImage': image_key,
            'ProcessingTimestamp': processing_timestamp,
            'ProcessingTimeSeconds': convert_float_to_decimal(processing_time),
            'ModelId': model_id,
            'InputTokens': input_tokens,
            'OutputTokens': output_tokens,
            'CostEstimateUSD': convert_float_to_decimal(cost_estimate),

            # OCR Version Tracking
            'OCRVersion': OCR_VERSION['version'],
            'OCRBuildDate': OCR_VERSION['build_date'],
            'OCRDescription': OCR_VERSION['description'],
            'OCRFullVersion': OCR_VERSION['full_version'],

            # Week context
            'WeekStartDate': start_date.strftime('%Y-%m-%d'),
            'WeekEndDate': end_date.strftime('%Y-%m-%d'),

            # GSI attributes
            'YearMonth': start_date.strftime('%Y-%m'),
        }

        # Add image metadata if available
        if image_metadata:
            item.update(image_metadata)

        table.put_item(Item=item)
        entries_stored = 1

        return {
            'entries_stored': entries_stored,
            'resource_name': resource_name,
            'date_range': date_range_str,
            'projects_count': 0,
            'is_zero_hour': True,
            'zero_hour_reason': zero_hour_reason,
            'table_name': table_name
        }

    # Track unique entries to prevent duplicates WITHIN this scan
    unique_entries = {}  # Key: (date, project_code) -> item

    # Track entries that already exist in database (to prevent cross-scan duplicates)
    # We'll check per-date to avoid excessive queries
    existing_db_entries_by_date = {}  # Key: date_str -> dict of project_code -> item

    # Track statistics
    duplicates_skipped = 0
    duplicates_updated = 0

    for project in timesheet_data.get('projects', []):
        project_name = project.get('project_name', '')
        project_code = project.get('project_code', '')

        # Validate project code - skip if invalid (e.g., subtask labels like "DESIGN", "LABOUR")
        if not is_valid_project_code(project_code):
            print(f"WARNING: Skipping invalid project code '{project_code}' for project '{project_name}'")
            print(f"         This appears to be a subtask label, not a valid project code")
            continue

        project_code = normalize_project_code(project_code)

        hours_by_day = project.get('hours_by_day', [])

        # Create an entry for each day
        for i, day_data in enumerate(hours_by_day):
            if i >= len(week_dates):
                break

            date_obj = week_dates[i]
            date_str = format_date_for_csv(date_obj)
            hours_str = day_data.get('hours', '0')
            hours = parse_hours(hours_str)

            # Log each day being processed
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            print(f"   [DEBUG] Day {i} ({day_names[i]}): {date_str} - Project: {project_code} - Hours: {hours}")

            # CRITICAL FIX: Skip entries with 0 hours to prevent database bloat
            # Only create database entries for days where actual work was logged
            # Exception: Bank holidays should still be recorded as 0 hours
            if hours == 0 and not is_bank_holiday(date_obj):
                print(f"   [DEBUG] SKIPPING: 0 hours on {date_str} (not a bank holiday)")
                continue

            if hours > 0:
                print(f"   [DEBUG] KEEPING: {hours} hours on {date_str} for project {project_code}")

            # Check for duplicate entry (same resource, date, project) WITHIN this scan
            entry_key = (date_str, project_code)

            if entry_key in unique_entries:
                # Duplicate detected within this scan - sum the hours instead of creating new entry
                existing_hours = float(unique_entries[entry_key]['Hours'])
                unique_entries[entry_key]['Hours'] = convert_float_to_decimal(existing_hours + hours)
                continue

            # Check if entry already exists in DATABASE (cross-scan deduplication)
            if date_str not in existing_db_entries_by_date:
                # Load existing entries for this date
                existing_db_entries_by_date[date_str] = check_existing_entries(table, resource_key, date_str)

            existing_for_date = existing_db_entries_by_date[date_str]

            if project_code in existing_for_date:
                # Entry already exists in database for this person/date/project
                existing_item = existing_for_date[project_code]
                existing_source = existing_item.get('SourceImage', 'unknown')
                existing_hours = float(existing_item.get('Hours', 0))
                existing_timestamp = existing_item.get('ProcessingTimestamp', '')

                print(f"⚠️  DUPLICATE DETECTED:")
                print(f"   Person: {resource_name}")
                print(f"   Date: {date_str}")
                print(f"   Project: {project_code}")
                print(f"   Existing: {existing_hours}h from '{existing_source}' @ {existing_timestamp}")
                print(f"   New: {hours}h from '{image_key}' @ {processing_timestamp}")

                # DEDUPLICATION STRATEGY: Keep the most recent entry
                # Compare timestamps - if new entry is newer, update; otherwise skip
                if processing_timestamp > existing_timestamp:
                    print(f"   ✅ UPDATING to newer entry (replacing old data)")
                    # We'll insert the new entry (it will overwrite via put_item with same key)
                    duplicates_updated += 1
                else:
                    print(f"   ⏭️  SKIPPING - existing entry is newer")
                    duplicates_skipped += 1
                    continue

            # Create DynamoDB item
            item = {
                # Primary keys
                'ResourceName': resource_key,
                'DateProjectCode': f"{date_str}#{project_code}",

                # Attributes
                'Date': date_str,
                'ProjectCode': project_code,
                'ProjectName': project_name,
                'Hours': convert_float_to_decimal(hours),
                'ResourceNameDisplay': resource_name,
                'IsZeroHourTimesheet': False,

                # Metadata
                'SourceImage': image_key,
                'ProcessingTimestamp': processing_timestamp,
                'ProcessingTimeSeconds': convert_float_to_decimal(processing_time),
                'ModelId': model_id,
                'InputTokens': input_tokens,
                'OutputTokens': output_tokens,
                'CostEstimateUSD': convert_float_to_decimal(cost_estimate),

                # OCR Version Tracking
                'OCRVersion': OCR_VERSION['version'],
                'OCRBuildDate': OCR_VERSION['build_date'],
                'OCRDescription': OCR_VERSION['description'],
                'OCRFullVersion': OCR_VERSION['full_version'],

                # Week context
                'WeekStartDate': start_date.strftime('%Y-%m-%d'),
                'WeekEndDate': end_date.strftime('%Y-%m-%d'),

                # GSI attributes
                'YearMonth': date_str[:7],  # e.g., "2025-09" for GSI queries
                'ProjectCodeGSI': project_code,  # For project-based queries
            }

            # Add image metadata if available
            if image_metadata:
                item.update(image_metadata)

            unique_entries[entry_key] = item

    # Now batch write the unique entries
    print(f"[DEBUG] About to batch write {len(unique_entries)} entries to table '{table_name}'")
    print(f"[DEBUG] Table object: {table}")
    print(f"[DEBUG] Table name from object: {table.name}")

    if len(unique_entries) == 0:
        print(f"[DEBUG] No entries to write - skipping batch operation")
    else:
        try:
            with table.batch_writer() as batch:
                for idx, item in enumerate(unique_entries.values()):
                    print(f"[DEBUG] Adding item {idx+1}/{len(unique_entries)} to batch")
                    batch.put_item(Item=item)
                    entries_stored += 1
            print(f"[DEBUG] Batch write completed successfully - {entries_stored} entries written")

            # Update coverage tracker - mark this week as submitted for this person/month
            try:
                # Get first date from the timesheet to determine the week
                if week_dates and len(week_dates) > 0:
                    first_date = format_date_for_csv(week_dates[0])
                    week_monday = get_week_commencing(first_date)
                    coverage_result = update_coverage(table_name, resource_key, first_date)
                    if coverage_result.get('success'):
                        print(f"📅 Coverage tracker updated: {resource_name} - {coverage_result.get('clarity_month')} - Week {week_monday}")
                    else:
                        print(f"⚠️  Coverage tracker update failed: {coverage_result.get('error', 'Unknown')}")
            except Exception as e:
                print(f"⚠️  Coverage tracker error (non-fatal): {e}")

        except Exception as e:
            print(f"[DEBUG] Batch write FAILED with error: {type(e).__name__}: {str(e)}")
            print(f"[DEBUG] Table name was: {table_name}")
            print(f"[DEBUG] Table object name: {table.name}")
            print(f"[DEBUG] Error details: {repr(e)}")
            if hasattr(e, 'response'):
                print(f"[DEBUG] Response: {e.response}")
            raise

    # Log deduplication summary
    if duplicates_skipped > 0 or duplicates_updated > 0:
        print(f"\n📊 DEDUPLICATION SUMMARY:")
        print(f"   Duplicates skipped (older): {duplicates_skipped}")
        print(f"   Duplicates updated (newer): {duplicates_updated}")
        print(f"   New entries stored: {entries_stored}")

    return {
        'entries_stored': entries_stored,
        'resource_name': resource_name,
        'date_range': date_range_str,
        'projects_count': len(timesheet_data.get('projects', [])),
        'duplicates_skipped': duplicates_skipped,
        'duplicates_updated': duplicates_updated,
        'table_name': table_name
    }


def query_timesheet_by_resource(
    resource_name: str,
    start_date: str = None,
    end_date: str = None,
    table_name: str = None
) -> List[Dict]:
    """
    Query timesheet entries for a specific resource.

    Args:
        resource_name: Resource name (e.g., "Nik Coultas")
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)
        table_name: DynamoDB table name

    Returns:
        List of timesheet entries
    """
    if not table_name:
        raise ValueError("DynamoDB table name not provided")

    table = dynamodb.Table(table_name)
    resource_key = resource_name.replace(' ', '_')

    # Build query
    if start_date and end_date:
        response = table.query(
            KeyConditionExpression='ResourceName = :rn AND DateProjectCode BETWEEN :start AND :end',
            ExpressionAttributeValues={
                ':rn': resource_key,
                ':start': f"{start_date}#",
                ':end': f"{end_date}#ZZZZZZ"
            }
        )
    else:
        response = table.query(
            KeyConditionExpression='ResourceName = :rn',
            ExpressionAttributeValues={
                ':rn': resource_key
            }
        )

    return response.get('Items', [])


def query_timesheet_by_project(
    project_code: str,
    table_name: str = None
) -> List[Dict]:
    """
    Query timesheet entries for a specific project using GSI.

    Args:
        project_code: Project code (e.g., "PJ021931")
        table_name: DynamoDB table name

    Returns:
        List of timesheet entries
    """
    if not table_name:
        raise ValueError("DynamoDB table name not provided")

    table = dynamodb.Table(table_name)

    response = table.query(
        IndexName='ProjectCodeIndex',
        KeyConditionExpression='ProjectCodeGSI = :pc',
        ExpressionAttributeValues={
            ':pc': project_code
        }
    )

    return response.get('Items', [])


def scan_all_timesheets(table_name: str = None) -> List[Dict]:
    """
    Scan all timesheet entries (use with caution on large tables).

    Args:
        table_name: DynamoDB table name

    Returns:
        List of all timesheet entries
    """
    if not table_name:
        raise ValueError("DynamoDB table name not provided")

    table = dynamodb.Table(table_name)

    response = table.scan()
    items = response.get('Items', [])

    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))

    return items


def store_rejected_timesheet(
    resource_name: str,
    date_range: str,
    status: str,
    image_key: str,
    processing_time: float,
    reason: str,
    table_name: str
) -> Dict:
    """
    Store a rejection record for a timesheet that doesn't meet validation criteria.

    Used for timesheets with status != "Posted"

    Args:
        resource_name: Person's name
        date_range: Date range string
        status: The status found (e.g., "Submitted", "Draft")
        image_key: S3 key of source image
        processing_time: Processing time in seconds
        reason: Why the timesheet was rejected
        table_name: DynamoDB table name

    Returns:
        Dictionary with rejection record details
    """
    if not table_name:
        raise ValueError("DynamoDB table name not provided")

    table = dynamodb.Table(table_name)

    # Parse date range to get start date
    try:
        start_date, end_date = parse_date_range(date_range)
        start_date_str = start_date.strftime('%Y-%m-%d')
    except Exception as e:
        print(f"Warning: Could not parse date range '{date_range}': {e}")
        start_date_str = "UNKNOWN"

    # Clean resource name for partition key
    resource_key = resource_name.replace(' ', '_')

    # Create rejection record
    processing_timestamp = datetime.utcnow().isoformat() + 'Z'

    item = {
        # Primary keys - use REJECTED# prefix to distinguish from actual timesheet entries
        'ResourceName': resource_key,
        'DateProjectCode': f"REJECTED#{start_date_str}",

        # Rejection details
        'Status': status,
        'Reason': reason,
        'Rejected': True,
        'ResourceNameDisplay': resource_name,
        'DateRange': date_range,

        # Metadata
        'SourceImage': image_key,
        'ProcessingTimestamp': processing_timestamp,
        'ProcessingTimeSeconds': convert_float_to_decimal(processing_time),

        # GSI attributes
        'YearMonth': start_date_str[:7] if start_date_str != "UNKNOWN" else "UNKNOWN",
    }

    # Store rejection record
    table.put_item(Item=item)
    print(f"✅ Stored rejection record for {resource_name} - {date_range}")

    return {
        'rejected': True,
        'resource_name': resource_name,
        'date_range': date_range,
        'status': status,
        'reason': reason,
        'table_name': table_name
    }
