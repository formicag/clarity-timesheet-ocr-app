"""
Duplicate detection and handling for timesheet uploads.
"""
import boto3
from typing import Dict, List, Tuple
from datetime import datetime

dynamodb = boto3.resource('dynamodb')


def check_for_existing_entries(
    resource_name: str,
    start_date: str,
    end_date: str,
    project_codes: List[str],
    table_name: str
) -> Dict:
    """
    Check if entries already exist for this resource/date/projects combination.

    Args:
        resource_name: Resource name (e.g., "Nik Coultas")
        start_date: Week start date (YYYY-MM-DD)
        end_date: Week end date (YYYY-MM-DD)
        project_codes: List of project codes in this timesheet
        table_name: DynamoDB table name

    Returns:
        Dictionary with:
        - exists: bool - whether any matching entries exist
        - existing_entries: List of existing entries
        - source_images: List of source images that created existing entries
        - entry_count: Number of existing entries found
    """
    table = dynamodb.Table(table_name)
    resource_key = resource_name.replace(' ', '_')

    # Query for all entries in this date range for this resource
    response = table.query(
        KeyConditionExpression='ResourceName = :rn AND DateProjectCode BETWEEN :start AND :end',
        ExpressionAttributeValues={
            ':rn': resource_key,
            ':start': f"{start_date}#",
            ':end': f"{end_date}#ZZZZZZ"
        }
    )

    existing_entries = response.get('Items', [])

    if not existing_entries:
        return {
            'exists': False,
            'existing_entries': [],
            'source_images': [],
            'entry_count': 0,
            'message': 'No existing entries found'
        }

    # Get unique source images
    source_images = list(set(item.get('SourceImage', 'Unknown') for item in existing_entries))

    # Check if any of the project codes match
    existing_project_codes = set(item.get('ProjectCode', '') for item in existing_entries)
    matching_projects = set(project_codes) & existing_project_codes

    return {
        'exists': True,
        'existing_entries': existing_entries,
        'source_images': source_images,
        'entry_count': len(existing_entries),
        'existing_project_codes': list(existing_project_codes),
        'matching_projects': list(matching_projects),
        'message': f"Found {len(existing_entries)} existing entries from {len(source_images)} source(s)"
    }


def generate_duplicate_warning_message(check_result: Dict, new_image_key: str) -> str:
    """
    Generate a user-friendly warning message about potential duplicates.

    Args:
        check_result: Result from check_for_existing_entries()
        new_image_key: Name of the new image being uploaded

    Returns:
        Formatted warning message
    """
    if not check_result['exists']:
        return ""

    entry_count = check_result['entry_count']
    source_images = check_result['source_images']
    matching_projects = check_result.get('matching_projects', [])

    message = f"⚠️  DUPLICATE DETECTION\n\n"
    message += f"Found {entry_count} existing entries for this resource and date range.\n\n"
    message += f"Previously uploaded from:\n"
    for img in source_images[:3]:  # Show first 3 sources
        message += f"  • {img}\n"

    if len(source_images) > 3:
        message += f"  • ...and {len(source_images) - 3} more\n"

    if matching_projects:
        message += f"\nMatching projects: {', '.join(matching_projects[:5])}\n"

    message += f"\nUploading '{new_image_key}' will:\n"
    message += f"✓ OVERWRITE existing entries with new data\n"
    message += f"✓ Update processing timestamp and metadata\n"
    message += f"✓ Keep the most recent hours values\n\n"
    message += f"Do you want to continue?"

    return message


def get_upload_history_summary(resource_name: str, table_name: str) -> Dict:
    """
    Get a summary of all uploads for a specific resource.

    Args:
        resource_name: Resource name
        table_name: DynamoDB table name

    Returns:
        Dictionary with upload history summary
    """
    table = dynamodb.Table(table_name)
    resource_key = resource_name.replace(' ', '_')

    response = table.query(
        KeyConditionExpression='ResourceName = :rn',
        ExpressionAttributeValues={
            ':rn': resource_key
        }
    )

    entries = response.get('Items', [])

    if not entries:
        return {
            'total_entries': 0,
            'source_images': [],
            'date_ranges': [],
            'last_upload': None
        }

    # Extract unique information
    source_images = list(set(item.get('SourceImage', '') for item in entries))
    processing_timestamps = [item.get('ProcessingTimestamp', '') for item in entries]

    # Get date ranges
    date_ranges = []
    seen_weeks = set()
    for item in entries:
        week_key = f"{item.get('WeekStartDate')}-{item.get('WeekEndDate')}"
        if week_key not in seen_weeks:
            seen_weeks.add(week_key)
            date_ranges.append({
                'start': item.get('WeekStartDate'),
                'end': item.get('WeekEndDate'),
                'source': item.get('SourceImage')
            })

    # Get last upload timestamp
    last_upload = max(processing_timestamps) if processing_timestamps else None

    return {
        'total_entries': len(entries),
        'source_images': source_images,
        'date_ranges': sorted(date_ranges, key=lambda x: x['start'], reverse=True),
        'last_upload': last_upload,
        'unique_weeks': len(seen_weeks)
    }
