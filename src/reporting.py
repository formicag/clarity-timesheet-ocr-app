"""
Reporting functions for timesheet data analysis.
"""
import boto3
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from collections import defaultdict

dynamodb = boto3.resource('dynamodb')


def get_all_resources(table_name: str) -> List[Dict]:
    """
    Get all unique resources from the database.

    Args:
        table_name: DynamoDB table name

    Returns:
        List of dictionaries with resource information
    """
    table = dynamodb.Table(table_name)

    # Scan table to get all unique resources
    response = table.scan(
        ProjectionExpression='ResourceName, ResourceNameDisplay'
    )

    items = response.get('Items', [])

    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            ProjectionExpression='ResourceName, ResourceNameDisplay',
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response.get('Items', []))

    # Get unique resources
    seen = set()
    unique_resources = []

    for item in items:
        resource_key = item.get('ResourceName')
        if resource_key and resource_key not in seen:
            seen.add(resource_key)
            unique_resources.append({
                'resource_key': resource_key,
                'resource_name': item.get('ResourceNameDisplay', resource_key.replace('_', ' '))
            })

    # Sort by name
    unique_resources.sort(key=lambda x: x['resource_name'])

    return unique_resources


def get_resource_week_summary(
    resource_name: str,
    table_name: str,
    start_date: str = None,
    end_date: str = None
) -> Dict:
    """
    Get summary of all weeks with data for a specific resource.

    Args:
        resource_name: Resource name (e.g., "Nik Coultas")
        table_name: DynamoDB table name
        start_date: Optional start date (YYYY-MM-DD), defaults to earliest data
        end_date: Optional end date (YYYY-MM-DD), defaults to today

    Returns:
        Dictionary with week-by-week summary
    """
    table = dynamodb.Table(table_name)
    resource_key = resource_name.replace(' ', '_')

    # Query all entries for this resource
    response = table.query(
        KeyConditionExpression='ResourceName = :rn',
        ExpressionAttributeValues={
            ':rn': resource_key
        }
    )

    items = response.get('Items', [])

    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.query(
            KeyConditionExpression='ResourceName = :rn',
            ExpressionAttributeValues={
                ':rn': resource_key
            },
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response.get('Items', []))

    if not items:
        return {
            'resource_name': resource_name,
            'total_entries': 0,
            'weeks': [],
            'date_range': {
                'start': None,
                'end': None
            }
        }

    # Group by week
    weeks_data = defaultdict(lambda: {
        'week_start': None,
        'week_end': None,
        'is_zero_hour': False,
        'zero_hour_reason': None,
        'total_hours': 0,
        'projects': set(),
        'source_images': set(),
        'entries': []
    })

    earliest_date = None
    latest_date = None

    for item in items:
        week_start = item.get('WeekStartDate')
        week_end = item.get('WeekEndDate')
        is_zero_hour = item.get('IsZeroHourTimesheet', False)

        if not week_start:
            continue

        # Track earliest and latest dates
        if not earliest_date or week_start < earliest_date:
            earliest_date = week_start
        if not latest_date or week_start > latest_date:
            latest_date = week_start

        week_key = week_start

        # Update week data
        weeks_data[week_key]['week_start'] = week_start
        weeks_data[week_key]['week_end'] = week_end
        weeks_data[week_key]['source_images'].add(item.get('SourceImage', ''))

        if is_zero_hour:
            weeks_data[week_key]['is_zero_hour'] = True
            weeks_data[week_key]['zero_hour_reason'] = item.get('ZeroHourReason', 'ABSENCE')
        else:
            hours = float(item.get('Hours', 0))
            weeks_data[week_key]['total_hours'] += hours
            project_code = item.get('ProjectCode')
            if project_code:
                weeks_data[week_key]['projects'].add(project_code)

        weeks_data[week_key]['entries'].append(item)

    # Convert to list and sort
    weeks_list = []
    for week_key, week_info in weeks_data.items():
        weeks_list.append({
            'week_start': week_info['week_start'],
            'week_end': week_info['week_end'],
            'is_zero_hour': week_info['is_zero_hour'],
            'zero_hour_reason': week_info['zero_hour_reason'],
            'total_hours': week_info['total_hours'],
            'projects_count': len(week_info['projects']),
            'project_codes': sorted(list(week_info['projects'])),
            'source_images': sorted(list(week_info['source_images'])),
            'entries_count': len(week_info['entries'])
        })

    weeks_list.sort(key=lambda x: x['week_start'])

    # Apply date filters if provided
    if start_date:
        weeks_list = [w for w in weeks_list if w['week_start'] >= start_date]
    if end_date:
        weeks_list = [w for w in weeks_list if w['week_start'] <= end_date]

    return {
        'resource_name': resource_name,
        'total_entries': len(items),
        'weeks': weeks_list,
        'weeks_with_data': len(weeks_list),
        'date_range': {
            'start': earliest_date,
            'end': latest_date
        }
    }


def generate_calendar_weeks(start_date: str, end_date: str) -> List[Dict]:
    """
    Generate list of all calendar weeks between start and end date.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        List of week dictionaries with start/end dates
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    # Adjust to Monday
    while start.weekday() != 0:
        start -= timedelta(days=1)

    weeks = []
    current = start

    while current <= end:
        week_end = current + timedelta(days=6)
        weeks.append({
            'week_start': current.strftime('%Y-%m-%d'),
            'week_end': week_end.strftime('%Y-%m-%d'),
            'iso_week': current.isocalendar()[1],
            'year': current.year
        })
        current += timedelta(days=7)

    return weeks


def generate_resource_calendar_report(
    resource_name: str,
    table_name: str,
    start_date: str = None,
    end_date: str = None
) -> Dict:
    """
    Generate a calendar-style report showing which weeks have data.

    Args:
        resource_name: Resource name
        table_name: DynamoDB table name
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD), defaults to today

    Returns:
        Dictionary with calendar report data
    """
    # Get resource data
    resource_data = get_resource_week_summary(resource_name, table_name)

    if resource_data['total_entries'] == 0:
        return {
            'resource_name': resource_name,
            'has_data': False,
            'message': 'No data found for this resource'
        }

    # Determine date range
    data_start = resource_data['date_range']['start']
    data_end = resource_data['date_range']['end']

    if not start_date:
        start_date = data_start
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')

    # Generate all calendar weeks in range
    all_weeks = generate_calendar_weeks(start_date, end_date)

    # Create a map of weeks with data
    weeks_with_data_map = {
        week['week_start']: week
        for week in resource_data['weeks']
    }

    # Build calendar with status
    calendar = []
    for week in all_weeks:
        week_start = week['week_start']
        has_data = week_start in weeks_with_data_map

        if has_data:
            week_info = weeks_with_data_map[week_start]
            calendar.append({
                'week_start': week_start,
                'week_end': week['week_end'],
                'iso_week': week['iso_week'],
                'year': week['year'],
                'status': 'present',
                'is_zero_hour': week_info['is_zero_hour'],
                'zero_hour_reason': week_info.get('zero_hour_reason'),
                'total_hours': week_info['total_hours'],
                'projects_count': week_info['projects_count'],
                'project_codes': week_info['project_codes']
            })
        else:
            calendar.append({
                'week_start': week_start,
                'week_end': week['week_end'],
                'iso_week': week['iso_week'],
                'year': week['year'],
                'status': 'missing',
                'is_zero_hour': False,
                'total_hours': 0,
                'projects_count': 0,
                'project_codes': []
            })

    # Calculate statistics
    total_weeks = len(calendar)
    weeks_present = sum(1 for w in calendar if w['status'] == 'present')
    weeks_missing = total_weeks - weeks_present
    zero_hour_weeks = sum(1 for w in calendar if w['is_zero_hour'])

    return {
        'resource_name': resource_name,
        'has_data': True,
        'date_range': {
            'start': start_date,
            'end': end_date
        },
        'statistics': {
            'total_weeks': total_weeks,
            'weeks_present': weeks_present,
            'weeks_missing': weeks_missing,
            'zero_hour_weeks': zero_hour_weeks,
            'completion_percentage': round((weeks_present / total_weeks * 100), 1) if total_weeks > 0 else 0
        },
        'calendar': calendar
    }
