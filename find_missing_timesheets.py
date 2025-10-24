#!/usr/bin/env python3
"""
Find missing timesheets for team members.

Checks which weeks are missing timesheets for each team member in a given time period.
Weeks run Monday to Sunday.
"""
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict
import boto3

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from team_manager import TeamManager

# AWS Configuration
DYNAMODB_TABLE = "TimesheetOCR-dev"
AWS_REGION = "us-east-1"

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE)


def get_all_mondays_in_range(start_date: datetime, end_date: datetime) -> list:
    """
    Get all Monday dates in the given date range.

    Args:
        start_date: Start of range
        end_date: End of range

    Returns:
        List of datetime objects for each Monday
    """
    mondays = []

    # Find the first Monday on or after start_date
    current = start_date
    days_until_monday = (7 - current.weekday()) % 7  # 0 = Monday
    if current.weekday() != 0:  # Not already Monday
        current = current + timedelta(days=days_until_monday)

    # Collect all Mondays until end_date
    while current <= end_date:
        mondays.append(current)
        current += timedelta(days=7)

    return mondays


def get_submitted_weeks_by_resource() -> dict:
    """
    Scan DynamoDB to get all weeks that have been submitted by each resource.

    Returns:
        Dictionary: {resource_name: set(week_start_dates)}
    """
    submitted_weeks = defaultdict(set)

    print("Scanning DynamoDB for all submitted timesheets...")

    # Scan all items
    response = table.scan(
        ProjectionExpression='ResourceName, WeekStartDate, IsZeroHourTimesheet'
    )

    items = response.get('Items', [])

    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            ProjectionExpression='ResourceName, WeekStartDate, IsZeroHourTimesheet',
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response.get('Items', []))

    print(f"Found {len(items)} entries in database")

    # Group by resource and week
    for item in items:
        resource_name = item.get('ResourceName', '').replace('_', ' ')
        week_start = item.get('WeekStartDate')

        if resource_name and week_start:
            # Add this week to the set for this resource
            submitted_weeks[resource_name].add(week_start)

    # Convert sets to sorted lists for easier reading
    for resource in submitted_weeks:
        submitted_weeks[resource] = sorted(list(submitted_weeks[resource]))

    return submitted_weeks


def find_missing_timesheets(start_date_str: str, end_date_str: str):
    """
    Find missing timesheets for all team members in the given date range.

    Args:
        start_date_str: Start date in YYYY-MM-DD format
        end_date_str: End date in YYYY-MM-DD format
    """
    # Parse dates
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    except ValueError as e:
        print(f"Error: Invalid date format. Use YYYY-MM-DD")
        print(f"  {e}")
        return

    # Get all Mondays in range
    mondays = get_all_mondays_in_range(start_date, end_date)
    expected_weeks = [m.strftime('%Y-%m-%d') for m in mondays]

    print(f"Date Range: {start_date_str} to {end_date_str}")
    print(f"Expected weeks (Mondays): {len(expected_weeks)}")
    for week in expected_weeks:
        week_end = (datetime.strptime(week, '%Y-%m-%d') + timedelta(days=6)).strftime('%Y-%m-%d')
        print(f"  - {week} to {week_end}")
    print()

    # Load team roster
    team_manager = TeamManager()
    team_members = team_manager.get_team_members()
    print(f"Team members: {len(team_members)}")
    print()

    # Get submitted weeks from database
    submitted_weeks = get_submitted_weeks_by_resource()

    # Find missing weeks for each team member
    print("=" * 80)
    print("MISSING TIMESHEETS REPORT")
    print("=" * 80)
    print()

    total_missing = 0
    members_with_missing = 0

    for member in sorted(team_members):
        member_key = member.replace(' ', '_')
        member_display = member

        # Get weeks this member has submitted
        submitted = set(submitted_weeks.get(member_display, []))

        # Find missing weeks
        missing = [week for week in expected_weeks if week not in submitted]

        if missing:
            members_with_missing += 1
            total_missing += len(missing)

            print(f"📋 {member_display}")
            print(f"   Submitted: {len(submitted)}/{len(expected_weeks)} weeks")
            print(f"   Missing: {len(missing)} weeks")

            for week in missing:
                week_date = datetime.strptime(week, '%Y-%m-%d')
                week_end = week_date + timedelta(days=6)
                print(f"      ❌ {week} to {week_end.strftime('%Y-%m-%d')} "
                      f"({week_date.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')})")
            print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Team members: {len(team_members)}")
    print(f"Expected weeks per member: {len(expected_weeks)}")
    print(f"Total timesheets expected: {len(team_members) * len(expected_weeks)}")
    print(f"Total timesheets submitted: {len(team_members) * len(expected_weeks) - total_missing}")
    print(f"Total missing: {total_missing}")
    print(f"Members with missing timesheets: {members_with_missing}")
    print(f"Completion rate: {((len(team_members) * len(expected_weeks) - total_missing) / (len(team_members) * len(expected_weeks)) * 100):.1f}%")
    print("=" * 80)


def main():
    """Main entry point."""
    print("=" * 80)
    print("MISSING TIMESHEET DETECTOR")
    print("=" * 80)
    print()

    if len(sys.argv) == 3:
        # Command line arguments provided
        start_date = sys.argv[1]
        end_date = sys.argv[2]
        find_missing_timesheets(start_date, end_date)
    else:
        # Interactive mode
        print("Find missing timesheets for team members")
        print("Weeks run Monday to Sunday")
        print()

        start_date = input("Start date (YYYY-MM-DD): ").strip()
        end_date = input("End date (YYYY-MM-DD): ").strip()

        print()
        find_missing_timesheets(start_date, end_date)


if __name__ == '__main__':
    main()
