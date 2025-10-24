#!/usr/bin/env python3
"""
Check timesheet coverage for team members.

Usage:
  python check_coverage.py --month 2025-09              # Whole team for September 2025
  python check_coverage.py --month 2025-09 --name "Matthew Garretty"  # Individual
  python check_coverage.py --month 2025-09 --name "Matthew"  # Fuzzy match
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import argparse
import boto3
from datetime import datetime, timedelta
from collections import defaultdict
from team_manager import TeamManager
from bank_holidays import is_bank_holiday

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('TimesheetOCR-dev')


def get_workdays_in_month(year, month):
    """Get list of workdays (Mon-Fri, excluding bank holidays) in a given month."""
    start_date = datetime(year, month, 1)

    # Get last day of month
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)

    workdays = []
    current = start_date

    while current <= end_date:
        # Monday = 0, Sunday = 6
        if current.weekday() < 5:  # Mon-Fri
            if not is_bank_holiday(current):
                workdays.append(current)
        current += timedelta(days=1)

    return workdays


def get_week_start(date):
    """Get the Monday of the week containing this date."""
    days_since_monday = date.weekday()
    return date - timedelta(days=days_since_monday)


def get_timesheets_for_person(resource_name, year, month):
    """Get all timesheets for a person in a given month."""
    year_month = f"{year:04d}-{month:02d}"

    try:
        response = table.query(
            KeyConditionExpression='ResourceName = :rn',
            FilterExpression='begins_with(YearMonth, :ym)',
            ExpressionAttributeValues={
                ':rn': resource_name,
                ':ym': year_month
            }
        )

        items = response.get('Items', [])

        # Continue pagination if needed
        while 'LastEvaluatedKey' in response:
            response = table.query(
                KeyConditionExpression='ResourceName = :rn',
                FilterExpression='begins_with(YearMonth, :ym)',
                ExpressionAttributeValues={
                    ':rn': resource_name,
                    ':ym': year_month
                },
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        return items
    except Exception as e:
        print(f"Error querying DynamoDB: {e}")
        return []


def parse_date_range(date_range_str):
    """Parse date range string like 'Sep 1 2025 - Sep 7 2025'."""
    try:
        parts = date_range_str.split(' - ')
        start_str = parts[0].strip()
        end_str = parts[1].strip()

        start_date = datetime.strptime(start_str, '%b %d %Y')
        end_date = datetime.strptime(end_str, '%b %d %Y')

        return start_date, end_date
    except Exception as e:
        print(f"Warning: Could not parse date range '{date_range_str}': {e}")
        return None, None


def analyze_coverage(resource_name, year, month):
    """Analyze timesheet coverage for a person in a given month."""
    workdays = get_workdays_in_month(year, month)
    timesheets = get_timesheets_for_person(resource_name, year, month)

    # Group timesheets by week
    weeks_covered = set()
    weeks_with_zero_hours = set()

    for item in timesheets:
        date_range = item.get('DateRange')
        if not date_range:
            continue

        start_date, end_date = parse_date_range(date_range)
        if not start_date:
            continue

        week_start = get_week_start(start_date)
        weeks_covered.add(week_start)

        # Check if this is a zero-hour timesheet
        if item.get('DateProjectCode', '').startswith('ZERO_HOUR#'):
            weeks_with_zero_hours.add(week_start)

    # Determine which weeks should have timesheets
    weeks_needed = set()
    for workday in workdays:
        week_start = get_week_start(workday)
        weeks_needed.add(week_start)

    # Calculate coverage
    missing_weeks = weeks_needed - weeks_covered
    covered_weeks = weeks_covered & weeks_needed

    return {
        'resource_name': resource_name,
        'workdays_count': len(workdays),
        'weeks_needed': sorted(weeks_needed),
        'weeks_covered': sorted(covered_weeks),
        'weeks_with_zero_hours': sorted(weeks_with_zero_hours),
        'missing_weeks': sorted(missing_weeks),
        'coverage_percent': (len(covered_weeks) / len(weeks_needed) * 100) if weeks_needed else 100.0
    }


def print_coverage_report(coverage_data, month_str):
    """Print a formatted coverage report."""
    name = coverage_data['resource_name'].replace('_', ' ')
    coverage_pct = coverage_data['coverage_percent']

    # Determine status emoji
    if coverage_pct == 100:
        status = "✅"
    elif coverage_pct >= 75:
        status = "⚠️ "
    else:
        status = "❌"

    print(f"\n{status} {name}")
    print(f"   Coverage: {coverage_pct:.0f}% ({len(coverage_data['weeks_covered'])}/{len(coverage_data['weeks_needed'])} weeks)")

    if coverage_data['missing_weeks']:
        print(f"   Missing weeks:")
        for week in coverage_data['missing_weeks']:
            print(f"      - Week of {week.strftime('%b %d, %Y')}")

    if coverage_data['weeks_with_zero_hours']:
        print(f"   Zero-hour weeks (leave/absence):")
        for week in coverage_data['weeks_with_zero_hours']:
            print(f"      - Week of {week.strftime('%b %d, %Y')}")


def main():
    parser = argparse.ArgumentParser(
        description='Check timesheet coverage for team members',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check whole team for September 2025
  python check_coverage.py --month 2025-09

  # Check specific person for September 2025
  python check_coverage.py --month 2025-09 --name "Matthew Garretty"

  # Check with fuzzy name match
  python check_coverage.py --month 2025-09 --name "Matthew"
        """
    )

    parser.add_argument('--month', required=True, help='Month in YYYY-MM format (e.g., 2025-09)')
    parser.add_argument('--name', help='Team member name (optional, checks whole team if omitted)')

    args = parser.parse_args()

    # Parse month
    try:
        year, month = map(int, args.month.split('-'))
        if not (1 <= month <= 12):
            raise ValueError("Month must be between 1 and 12")
    except ValueError as e:
        print(f"Error: Invalid month format. Use YYYY-MM (e.g., 2025-09)")
        return 1

    month_str = datetime(year, month, 1).strftime('%B %Y')

    # Load team roster
    try:
        team_mgr = TeamManager()
    except Exception as e:
        print(f"Error loading team roster: {e}")
        return 1

    # Determine which team members to check
    if args.name:
        # Check specific person
        normalized_name, confidence, match_type = team_mgr.normalize_name(args.name)

        if match_type == 'none':
            print(f"Error: Could not find team member matching '{args.name}'")
            print(f"\nAvailable team members:")
            for member in sorted(team_mgr.get_team_members()):
                print(f"  - {member}")
            return 1

        if match_type in ['alias', 'fuzzy'] and confidence < 0.85:
            print(f"Warning: Low confidence match for '{args.name}' -> '{normalized_name}' ({confidence:.2f})")
            response = input("Continue? (y/n): ")
            if response.lower() != 'y':
                return 0

        resource_names = [normalized_name.replace(' ', '_')]
        print(f"\n{'='*60}")
        print(f"COVERAGE REPORT: {normalized_name}")
        print(f"Month: {month_str}")
        print(f"{'='*60}")
    else:
        # Check whole team
        resource_names = [name.replace(' ', '_') for name in team_mgr.get_team_members()]
        print(f"\n{'='*60}")
        print(f"TEAM COVERAGE REPORT")
        print(f"Month: {month_str}")
        print(f"{'='*60}")

    # Analyze coverage for each person
    all_coverage = []

    for resource_name in resource_names:
        coverage = analyze_coverage(resource_name, year, month)
        all_coverage.append(coverage)

    # Sort by coverage percentage (worst first)
    all_coverage.sort(key=lambda x: x['coverage_percent'])

    # Print individual reports
    for coverage in all_coverage:
        print_coverage_report(coverage, month_str)

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    complete = sum(1 for c in all_coverage if c['coverage_percent'] == 100)
    partial = sum(1 for c in all_coverage if 0 < c['coverage_percent'] < 100)
    missing = sum(1 for c in all_coverage if c['coverage_percent'] == 0)

    print(f"Total team members: {len(all_coverage)}")
    print(f"✅ Complete coverage: {complete}")
    print(f"⚠️  Partial coverage: {partial}")
    print(f"❌ No timesheets: {missing}")

    avg_coverage = sum(c['coverage_percent'] for c in all_coverage) / len(all_coverage) if all_coverage else 0
    print(f"\nAverage coverage: {avg_coverage:.1f}%")

    return 0


if __name__ == '__main__':
    sys.exit(main())
