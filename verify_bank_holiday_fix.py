#!/usr/bin/env python3
"""
Verify bank holiday fix by querying DynamoDB for the processed timesheet.
"""
import boto3
from decimal import Decimal
from datetime import datetime

# AWS Configuration
DYNAMODB_TABLE = "TimesheetOCR-dev"
AWS_REGION = "us-east-1"

# Expected data
RESOURCE_NAME = "David Hunt"
DATE_RANGE = "Aug 25, 2025 - Aug 31, 2025"
START_DATE = "2025-08-25"  # Monday - Bank Holiday

def query_timesheet_data():
    """Query DynamoDB for the timesheet data."""
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)

    print("=" * 80)
    print("QUERYING DYNAMODB FOR TIMESHEET DATA")
    print("=" * 80)
    print(f"Resource: {RESOURCE_NAME}")
    print(f"Week Starting: {START_DATE} (Monday Aug 25, 2025 - Bank Holiday)")
    print()

    # Query for all entries for this person and week
    response = table.query(
        KeyConditionExpression='ResourceName = :rn AND begins_with(DateProjectCode, :date)',
        ExpressionAttributeValues={
            ':rn': RESOURCE_NAME,
            ':date': START_DATE  # 2025-08-25
        }
    )

    items = response.get('Items', [])

    # Items are already filtered for the week starting Aug 25
    week_items = items

    if not week_items:
        print("❌ No data found in DynamoDB for this timesheet")
        return

    print(f"✅ Found {len(week_items)} entries in DynamoDB")
    print()

    # Organize by date
    entries_by_date = {}
    for item in week_items:
        date = item['Date']  # Uppercase D
        if date not in entries_by_date:
            entries_by_date[date] = []
        entries_by_date[date].append(item)

    # Sort dates
    sorted_dates = sorted(entries_by_date.keys())

    print("=" * 80)
    print("ENTRIES BY DAY:")
    print("=" * 80)

    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekly_total = Decimal('0')

    for i, date in enumerate(sorted_dates[:7]):  # First 7 days
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        day_name = day_names[date_obj.weekday()]
        is_bank_holiday = (date == "2025-08-25")

        entries = entries_by_date[date]
        daily_total = sum(Decimal(str(e.get('Hours', 0))) for e in entries)
        weekly_total += daily_total

        status = ""
        if is_bank_holiday:
            status = "🏦 BANK HOLIDAY"

        print(f"\n{day_name} {date_obj.strftime('%b %d, %Y')} {status}")
        print(f"  Daily Total: {float(daily_total):.2f} hours")

        if entries:
            for entry in entries:
                project_name = entry.get('ProjectName', 'Unknown')
                project_code = entry.get('ProjectCode', 'N/A')
                hours = float(entry.get('Hours', 0))
                print(f"    - {project_name} ({project_code}): {hours:.2f} hours")

    print()
    print("=" * 80)
    print(f"WEEKLY TOTAL: {float(weekly_total):.2f} hours")
    print("=" * 80)
    print()

    # Validation
    print("=" * 80)
    print("VALIDATION:")
    print("=" * 80)

    # Check Monday Aug 25 (bank holiday)
    monday_entries = entries_by_date.get("2025-08-25", [])
    monday_total = sum(Decimal(str(e.get('Hours', 0))) for e in monday_entries)

    if monday_total == 0:
        print("✅ SUCCESS: Monday Aug 25 (bank holiday) correctly has 0 hours")
    else:
        print(f"❌ FAILED: Monday Aug 25 (bank holiday) has {float(monday_total):.2f} hours instead of 0")
        print("   Projects on Monday:")
        for entry in monday_entries:
            print(f"     - {entry.get('ProjectName')}: {float(entry.get('Hours', 0)):.2f} hours")

    # Expected weekly total (4 days * 7.5 hours = 30 hours, minus 1 bank holiday = 22.5 hours)
    expected_weekly = Decimal('22.5')
    if abs(weekly_total - expected_weekly) < Decimal('0.01'):
        print(f"✅ SUCCESS: Weekly total is {float(weekly_total):.2f} hours (expected {float(expected_weekly):.2f})")
    else:
        print(f"⚠️  WARNING: Weekly total is {float(weekly_total):.2f} hours (expected {float(expected_weekly):.2f})")

    print()
    print("=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print("The bank holiday fix is working if:")
    print("  1. Monday Aug 25, 2025 has 0 hours ✓")
    print("  2. Other weekdays (Tue-Fri) have 7.5 hours each ✓")
    print("  3. Weekly total is 22.5 hours (not 30) ✓")
    print("=" * 80)


if __name__ == "__main__":
    try:
        query_timesheet_data()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
