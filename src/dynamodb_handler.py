"""
DynamoDB handler for storing timesheet data.
"""
import boto3
from datetime import datetime
from decimal import Decimal
from typing import Dict, List
from utils import (
    parse_date_range,
    generate_week_dates,
    normalize_project_code,
    parse_hours,
    format_date_for_csv,
    validate_timesheet_data
)

dynamodb = boto3.resource('dynamodb')


def convert_float_to_decimal(obj):
    """Convert float values to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_float_to_decimal(item) for item in obj]
    return obj


def store_timesheet_entries(
    timesheet_data: dict,
    image_key: str,
    processing_time: float,
    model_id: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_estimate: float = 0.0,
    table_name: str = None
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

    Returns:
        Dictionary with summary of stored entries
    """
    if not table_name:
        raise ValueError("DynamoDB table name not provided")

    table = dynamodb.Table(table_name)

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

            # Week context
            'WeekStartDate': start_date.strftime('%Y-%m-%d'),
            'WeekEndDate': end_date.strftime('%Y-%m-%d'),

            # GSI attributes
            'YearMonth': start_date.strftime('%Y-%m'),
        }

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

    # Use batch write for efficiency
    with table.batch_writer() as batch:
        for project in timesheet_data.get('projects', []):
            project_name = project.get('project_name', '')
            project_code = project.get('project_code', '')
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

                    # Week context
                    'WeekStartDate': start_date.strftime('%Y-%m-%d'),
                    'WeekEndDate': end_date.strftime('%Y-%m-%d'),

                    # GSI attributes
                    'YearMonth': date_str[:7],  # e.g., "2025-09" for GSI queries
                    'ProjectCodeGSI': project_code,  # For project-based queries
                }

                batch.put_item(Item=item)
                entries_stored += 1

    return {
        'entries_stored': entries_stored,
        'resource_name': resource_name,
        'date_range': date_range_str,
        'projects_count': len(timesheet_data.get('projects', [])),
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
