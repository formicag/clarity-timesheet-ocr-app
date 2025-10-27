"""
Timesheet coverage checker for Clarity months.

Checks which team members have submitted timesheets for each week
in a Clarity month period.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
import boto3


def load_clarity_months():
    """Load Clarity month definitions from clarity_months.json."""
    try:
        with open('clarity_months.json', 'r') as f:
            data = json.load(f)
            # Convert array to dict keyed by month
            months = {}
            for month_data in data.get('clarity_months', []):
                month_key = month_data['month']
                months[month_key] = {
                    'start': month_data['start_date'],
                    'end': month_data['end_date']
                }
            return months
    except Exception as e:
        print(f"Error loading clarity_months.json: {e}")
        return {}


def load_team_roster():
    """Load team member names from team_roster.json."""
    try:
        with open('team_roster.json', 'r') as f:
            data = json.load(f)
            return sorted(data.get('team_members', []))
    except Exception as e:
        print(f"Error loading team_roster.json: {e}")
        return []


def get_monday_weeks_in_period(start_date: datetime, end_date: datetime) -> List[datetime]:
    """
    Get all Monday dates that start weeks within the period.

    Args:
        start_date: Start of period
        end_date: End of period

    Returns:
        List of Monday dates (weeks) in the period
    """
    weeks = []

    # Find the first Monday on or after start_date
    current = start_date
    days_until_monday = (7 - current.weekday()) % 7
    if days_until_monday > 0 and current.weekday() != 0:
        current += timedelta(days=days_until_monday)

    # If start_date is already Monday, use it
    if start_date.weekday() == 0:
        current = start_date

    # Collect all Mondays until end_date
    while current <= end_date:
        weeks.append(current)
        current += timedelta(days=7)

    return weeks


def parse_clarity_month(month_str: str) -> Tuple[datetime, datetime]:
    """
    Parse Clarity month string to get start and end dates.

    Args:
        month_str: Clarity month like "Sep-25"

    Returns:
        Tuple of (start_date, end_date)
    """
    clarity_months = load_clarity_months()

    if month_str not in clarity_months:
        raise ValueError(f"Clarity month '{month_str}' not found in clarity_months.json")

    month_data = clarity_months[month_str]
    start_str = month_data['start']
    end_str = month_data['end']

    # Parse dates (format: "2025-08-18" or "18 Aug 2025")
    try:
        # Try format: "2025-08-18" (primary format)
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
    except ValueError:
        try:
            # Try format: "18 Aug 2025" (fallback)
            start_date = datetime.strptime(start_str, "%d %b %Y")
            end_date = datetime.strptime(end_str, "%d %b %Y")
        except ValueError:
            raise ValueError(f"Cannot parse dates: {start_str}, {end_str}")

    return start_date, end_date


def check_timesheet_exists(resource_name: str, week_start: datetime,
                           dynamodb_table: str = 'TimesheetOCR-dev',
                           region: str = 'us-east-1') -> bool:
    """
    Check if a timesheet exists for a person for a specific week.

    Args:
        resource_name: Name like "Neil Pomfret"
        week_start: Monday date of the week
        dynamodb_table: DynamoDB table name
        region: AWS region

    Returns:
        True if timesheet exists, False otherwise
    """
    # Convert to ResourceName format (spaces to underscores)
    resource_key = resource_name.replace(' ', '_')

    # Week dates (Monday to Sunday)
    week_dates = []
    for i in range(7):
        week_dates.append(week_start + timedelta(days=i))

    # Query DynamoDB for any entry in this week
    dynamodb = boto3.client('dynamodb', region_name=region)

    for date in week_dates:
        date_str = date.strftime('%Y-%m-%d')

        try:
            # Query for this person on this date
            response = dynamodb.query(
                TableName=dynamodb_table,
                KeyConditionExpression='ResourceName = :rn AND begins_with(DateProjectCode, :date)',
                ExpressionAttributeValues={
                    ':rn': {'S': resource_key},
                    ':date': {'S': date_str}
                },
                Select='COUNT',
                Limit=1
            )

            if response['Count'] > 0:
                return True

        except Exception as e:
            print(f"Error checking {resource_key} for {date_str}: {e}")
            continue

    return False


def generate_coverage_report(clarity_month: str,
                             dynamodb_table: str = 'TimesheetOCR-dev',
                             region: str = 'us-east-1') -> Dict:
    """
    Generate timesheet coverage report for a Clarity month.

    OPTIMIZED VERSION: Reads from pre-computed coverage tracker data
    instead of querying each person/week individually.

    Args:
        clarity_month: Clarity month like "Sep-25"
        dynamodb_table: DynamoDB table name
        region: AWS region

    Returns:
        Dictionary with coverage data
    """
    # Parse Clarity month
    start_date, end_date = parse_clarity_month(clarity_month)

    # Get weeks (Mondays) in period
    weeks = get_monday_weeks_in_period(start_date, end_date)

    # Load team roster
    team_members = load_team_roster()

    # OPTIMIZED: Query coverage tracker data for all team members at once
    from src.coverage_tracker import get_coverage_for_person

    # Build coverage matrix from pre-computed data
    coverage = {}
    for person in team_members:
        resource_name = person.replace(' ', '_')

        # Get coverage data for this person/month (single query!)
        coverage_data = get_coverage_for_person(dynamodb_table, resource_name, clarity_month)
        weeks_submitted = coverage_data.get('weeks_submitted', set())

        # Build week-by-week coverage
        coverage[person] = {}
        for week in weeks:
            week_str = week.strftime('%Y-%m-%d')
            coverage[person][week_str] = week_str in weeks_submitted

    # Calculate statistics
    total_expected = len(team_members) * len(weeks)
    total_submitted = sum(
        sum(1 for submitted in person_weeks.values() if submitted)
        for person_weeks in coverage.values()
    )
    total_missing = total_expected - total_submitted

    # Per-person stats
    person_stats = {}
    for person, person_weeks in coverage.items():
        submitted = sum(1 for s in person_weeks.values() if s)
        missing = len(weeks) - submitted
        person_stats[person] = {
            'submitted': submitted,
            'missing': missing,
            'total': len(weeks),
            'percentage': (submitted / len(weeks) * 100) if len(weeks) > 0 else 0
        }

    return {
        'clarity_month': clarity_month,
        'period': {
            'start': start_date.strftime('%d %b %Y'),
            'end': end_date.strftime('%d %b %Y')
        },
        'weeks': [w.strftime('%Y-%m-%d') for w in weeks],
        'week_count': len(weeks),
        'team_count': len(team_members),
        'coverage': coverage,
        'statistics': {
            'total_expected': total_expected,
            'total_submitted': total_submitted,
            'total_missing': total_missing,
            'coverage_percentage': (total_submitted / total_expected * 100) if total_expected > 0 else 0
        },
        'person_stats': person_stats
    }


def format_coverage_report_text(report: Dict) -> str:
    """
    Format coverage report as readable text.

    Args:
        report: Report from generate_coverage_report()

    Returns:
        Formatted text report
    """
    lines = []

    lines.append("=" * 80)
    lines.append(f"TIMESHEET COVERAGE REPORT - {report['clarity_month']}")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Period: {report['period']['start']} to {report['period']['end']}")
    lines.append(f"Weeks: {report['week_count']} weeks")
    lines.append(f"Team: {report['team_count']} members")
    lines.append("")

    # Overall statistics
    stats = report['statistics']
    lines.append("OVERALL STATISTICS")
    lines.append("-" * 80)
    lines.append(f"Expected timesheets: {stats['total_expected']}")
    lines.append(f"Submitted: {stats['total_submitted']} ({stats['coverage_percentage']:.1f}%)")
    lines.append(f"Missing: {stats['total_missing']}")
    lines.append("")

    # Week headers
    weeks = report['weeks']
    week_labels = [datetime.strptime(w, '%Y-%m-%d').strftime('%d %b') for w in weeks]

    lines.append("COVERAGE MATRIX")
    lines.append("-" * 80)

    # Header
    header = "Name".ljust(25)
    for label in week_labels:
        header += label.rjust(10)
    header += "  Status"
    lines.append(header)
    lines.append("-" * 80)

    # Per person
    coverage = report['coverage']
    person_stats = report['person_stats']

    for person in sorted(coverage.keys()):
        person_weeks = coverage[person]
        stats = person_stats[person]

        row = person.ljust(25)
        for week in weeks:
            has_sheet = person_weeks[week]
            row += ("✓" if has_sheet else "✗").rjust(10)

        # Status
        if stats['missing'] == 0:
            status = "✅ Complete"
        elif stats['submitted'] == 0:
            status = f"❌ All missing ({stats['missing']})"
        else:
            status = f"⚠️  Missing {stats['missing']}"

        row += f"  {status}"
        lines.append(row)

    lines.append("")
    lines.append("=" * 80)
    lines.append("Legend: ✓ = Submitted, ✗ = Missing")
    lines.append("=" * 80)

    return "\n".join(lines)


def format_coverage_report_csv(report: Dict) -> str:
    """
    Format coverage report as CSV.

    Args:
        report: Report from generate_coverage_report()

    Returns:
        CSV string
    """
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)

    # Header
    weeks = report['weeks']
    week_labels = [datetime.strptime(w, '%Y-%m-%d').strftime('%d %b %Y') for w in weeks]
    header = ['Name', 'Submitted', 'Missing', 'Total', 'Percentage'] + week_labels
    writer.writerow(header)

    # Data
    coverage = report['coverage']
    person_stats = report['person_stats']

    for person in sorted(coverage.keys()):
        person_weeks = coverage[person]
        stats = person_stats[person]

        row = [
            person,
            stats['submitted'],
            stats['missing'],
            stats['total'],
            f"{stats['percentage']:.1f}%"
        ]

        for week in weeks:
            row.append('Yes' if person_weeks[week] else 'No')

        writer.writerow(row)

    return output.getvalue()


if __name__ == '__main__':
    # Test with Sep-25
    print("Testing coverage report for Sep-25...")
    report = generate_coverage_report('Sep-25')
    print(format_coverage_report_text(report))
