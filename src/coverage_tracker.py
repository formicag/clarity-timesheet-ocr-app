"""
Real-time Timesheet Coverage Tracker

Maintains a live map of which weeks each team member has submitted timesheets for,
organized by Clarity month. Updates instantly as timesheets are processed.

DynamoDB Table Structure:
  Partition Key: ResourceName_ClarityMonth (e.g., "Nik_Coultas#2025-10")
  Attributes:
    - ResourceName: Person's name
    - ClarityMonth: YYYY-MM format
    - WeeksSubmitted: Set of week-commencing dates in the month
    - LastUpdated: Timestamp of last update
    - TotalWeeks: Expected number of weeks in this Clarity month
"""
import boto3
from datetime import datetime, timedelta
from typing import List, Set, Dict
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')


def get_clarity_month(date_str: str) -> str:
    """
    Get Clarity month for a date.
    Clarity months run from the 16th of one month to the 15th of the next.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Clarity month in YYYY-MM format

    Examples:
        "2025-10-10" -> "2025-09" (Oct 10 is in Sep 16 - Oct 15 period)
        "2025-10-20" -> "2025-10" (Oct 20 is in Oct 16 - Nov 15 period)
    """
    date = datetime.strptime(date_str, '%Y-%m-%d')

    # If date is between 1st and 15th, it's in the previous month's Clarity period
    if date.day <= 15:
        clarity_date = date - timedelta(days=date.day)  # Go to previous month
    else:
        clarity_date = date

    return clarity_date.strftime('%Y-%m')


def get_week_commencing(date_str: str) -> str:
    """
    Get the Monday (week commencing date) for any date.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Monday of that week in YYYY-MM-DD format
    """
    date = datetime.strptime(date_str, '%Y-%m-%d')
    # Get Monday of the week (weekday 0 = Monday)
    days_since_monday = date.weekday()
    monday = date - timedelta(days=days_since_monday)
    return monday.strftime('%Y-%m-%d')


def update_coverage(
    table_name: str,
    resource_name: str,
    date_str: str
) -> Dict:
    """
    Update coverage tracker when a timesheet is processed.

    Args:
        table_name: DynamoDB table name (main timesheet table)
        resource_name: Person's name (e.g., "Nik_Coultas")
        date_str: Date from the timesheet in YYYY-MM-DD format

    Returns:
        Updated coverage information
    """
    table = dynamodb.Table(table_name)

    # Calculate Clarity month and week commencing
    clarity_month = get_clarity_month(date_str)
    week_commencing = get_week_commencing(date_str)

    # Composite key for coverage tracking
    coverage_key = f"{resource_name}#COVERAGE#{clarity_month}"

    try:
        # Use UpdateItem with ADD operation to add week to the set
        response = table.update_item(
            Key={
                'ResourceName': resource_name,
                'DateProjectCode': coverage_key
            },
            UpdateExpression='ADD WeeksSubmitted :week SET LastUpdated = :now, ClarityMonth = :month, RecordType = :type',
            ExpressionAttributeValues={
                ':week': {week_commencing},  # DynamoDB String Set
                ':now': datetime.utcnow().isoformat(),
                ':month': clarity_month,
                ':type': 'COVERAGE_TRACKER'
            },
            ReturnValues='ALL_NEW'
        )

        return {
            'success': True,
            'resource_name': resource_name,
            'clarity_month': clarity_month,
            'week_added': week_commencing,
            'total_weeks': len(response['Attributes'].get('WeeksSubmitted', set()))
        }

    except Exception as e:
        print(f"⚠️  Coverage tracker update failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def get_coverage_for_person(
    table_name: str,
    resource_name: str,
    clarity_month: str
) -> Dict:
    """
    Get coverage information for a person in a specific Clarity month.

    Args:
        table_name: DynamoDB table name
        resource_name: Person's name
        clarity_month: YYYY-MM format

    Returns:
        Coverage data including weeks submitted
    """
    table = dynamodb.Table(table_name)
    coverage_key = f"{resource_name}#COVERAGE#{clarity_month}"

    try:
        response = table.get_item(
            Key={
                'ResourceName': resource_name,
                'DateProjectCode': coverage_key
            }
        )

        if 'Item' in response:
            item = response['Item']
            weeks = item.get('WeeksSubmitted', set())
            return {
                'found': True,
                'weeks_submitted': sorted(list(weeks)),
                'total_weeks': len(weeks),
                'last_updated': item.get('LastUpdated', 'Unknown')
            }
        else:
            return {
                'found': False,
                'weeks_submitted': [],
                'total_weeks': 0
            }

    except Exception as e:
        print(f"⚠️  Failed to get coverage: {e}")
        return {
            'found': False,
            'error': str(e),
            'weeks_submitted': [],
            'total_weeks': 0
        }


def get_all_coverage_for_month(
    table_name: str,
    clarity_month: str
) -> List[Dict]:
    """
    Get coverage for ALL team members for a specific Clarity month.
    This provides instant coverage check results.

    Args:
        table_name: DynamoDB table name
        clarity_month: YYYY-MM format

    Returns:
        List of coverage records for all team members
    """
    table = dynamodb.Table(table_name)

    try:
        # Scan for all COVERAGE_TRACKER records in this month
        # We use a FilterExpression to find coverage records for the month
        response = table.scan(
            FilterExpression='RecordType = :type AND ClarityMonth = :month',
            ExpressionAttributeValues={
                ':type': 'COVERAGE_TRACKER',
                ':month': clarity_month
            }
        )

        results = []
        for item in response.get('Items', []):
            # Extract resource name from the composite key
            resource_name = item.get('ResourceName', '')
            weeks = item.get('WeeksSubmitted', set())

            results.append({
                'resource_name': resource_name,
                'clarity_month': clarity_month,
                'weeks_submitted': sorted(list(weeks)),
                'total_weeks': len(weeks),
                'last_updated': item.get('LastUpdated', 'Unknown')
            })

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression='RecordType = :type AND ClarityMonth = :month',
                ExpressionAttributeValues={
                    ':type': 'COVERAGE_TRACKER',
                    ':month': clarity_month
                },
                ExclusiveStartKey=response['LastEvaluatedKey']
            )

            for item in response.get('Items', []):
                resource_name = item.get('ResourceName', '')
                weeks = item.get('WeeksSubmitted', set())

                results.append({
                    'resource_name': resource_name,
                    'clarity_month': clarity_month,
                    'weeks_submitted': sorted(list(weeks)),
                    'total_weeks': len(weeks),
                    'last_updated': item.get('LastUpdated', 'Unknown')
                })

        return results

    except Exception as e:
        print(f"⚠️  Failed to get coverage for month: {e}")
        return []


def get_expected_weeks_in_month(clarity_month: str) -> List[str]:
    """
    Get all week-commencing dates (Mondays) for a Clarity month.

    Args:
        clarity_month: YYYY-MM format

    Returns:
        List of Monday dates in YYYY-MM-DD format
    """
    year, month = map(int, clarity_month.split('-'))

    # Clarity month runs from 16th of month to 15th of next month
    start_date = datetime(year, month, 16)

    # Calculate end date (15th of next month)
    if month == 12:
        end_date = datetime(year + 1, 1, 15)
    else:
        end_date = datetime(year, month + 1, 15)

    # Find all Mondays in this range
    mondays = []
    current = start_date

    # Go back to the previous Monday if start_date isn't Monday
    while current.weekday() != 0:  # 0 = Monday
        current -= timedelta(days=1)

    # Collect all Mondays until we pass the end date
    while current <= end_date:
        mondays.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=7)

    return mondays
