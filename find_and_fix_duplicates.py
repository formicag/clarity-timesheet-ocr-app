#!/usr/bin/env python3
"""
Find and fix duplicate timesheet entries in DynamoDB.

A duplicate is defined as: same person, same date, same project code
(but different SourceImage, meaning the same timesheet was scanned multiple times
or OCR errors created variations of the same project code).

Strategy:
- For each person, scan all their entries
- Group by (Date, ProjectCode)
- If multiple entries exist, keep the MOST RECENT one (by ProcessingTimestamp)
- Delete older duplicates
"""
import boto3
from datetime import datetime
from collections import defaultdict
import time

# AWS Configuration
REGION = 'us-east-1'
TABLE_NAME = 'TimesheetOCR-dev'

# Initialize AWS clients
dynamodb = boto3.client('dynamodb', region_name=REGION)


def get_all_resources():
    """Get all unique ResourceName values."""
    print("📋 Scanning for all unique resources...")

    # Use scan with projection to get only ResourceName
    resources = set()
    scan_kwargs = {
        'TableName': TABLE_NAME,
        'ProjectionExpression': 'ResourceName'
    }

    while True:
        response = dynamodb.scan(**scan_kwargs)
        for item in response.get('Items', []):
            resources.add(item['ResourceName']['S'])

        if 'LastEvaluatedKey' not in response:
            break
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    return sorted(resources)


def get_all_entries_for_resource(resource_name):
    """Get all entries for a specific resource."""
    query_kwargs = {
        'TableName': TABLE_NAME,
        'KeyConditionExpression': 'ResourceName = :rn',
        'ExpressionAttributeValues': {
            ':rn': {'S': resource_name}
        }
    }

    entries = []
    while True:
        response = dynamodb.query(**query_kwargs)
        entries.extend(response.get('Items', []))

        if 'LastEvaluatedKey' not in response:
            break
        query_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    return entries


def find_duplicates_for_resource(resource_name):
    """
    Find duplicate entries for a resource.

    Returns:
        Dict mapping (date, project_code) -> list of duplicate items
    """
    entries = get_all_entries_for_resource(resource_name)

    # Group by (Date, ProjectCode)
    groups = defaultdict(list)

    for entry in entries:
        # Skip zero-hour timesheets (they have DateProjectCode = "WEEK#...")
        date_project_code = entry.get('DateProjectCode', {}).get('S', '')
        if date_project_code.startswith('WEEK#'):
            continue

        # Extract date and project code
        if '#' not in date_project_code:
            continue

        parts = date_project_code.split('#')
        if len(parts) != 2:
            continue

        date_str = parts[0]
        project_code = parts[1]

        key = (date_str, project_code)
        groups[key].append(entry)

    # Find groups with duplicates (more than 1 entry)
    duplicates = {}
    for key, items in groups.items():
        if len(items) > 1:
            duplicates[key] = items

    return duplicates


def get_item_timestamp(item):
    """Extract ProcessingTimestamp from item."""
    timestamp_str = item.get('ProcessingTimestamp', {}).get('S', '1970-01-01T00:00:00Z')
    return timestamp_str


def delete_duplicate_entries(resource_name, duplicates, dry_run=True):
    """
    Delete duplicate entries, keeping only the most recent.

    Args:
        resource_name: Person's name
        duplicates: Dict from find_duplicates_for_resource()
        dry_run: If True, only print what would be deleted

    Returns:
        (kept_count, deleted_count)
    """
    kept_count = 0
    deleted_count = 0

    for (date_str, project_code), items in duplicates.items():
        # Sort by timestamp (newest first)
        sorted_items = sorted(items, key=get_item_timestamp, reverse=True)

        # Keep the newest
        newest = sorted_items[0]
        to_delete = sorted_items[1:]

        newest_source = newest.get('SourceImage', {}).get('S', 'unknown')
        newest_timestamp = get_item_timestamp(newest)
        newest_hours = newest.get('Hours', {}).get('N', '0')

        print(f"\n📅 {date_str} | {project_code}")
        print(f"   ✅ KEEPING: {newest_hours}h from '{newest_source}' @ {newest_timestamp}")

        for old_item in to_delete:
            old_source = old_item.get('SourceImage', {}).get('S', 'unknown')
            old_timestamp = get_item_timestamp(old_item)
            old_hours = old_item.get('Hours', {}).get('N', '0')

            if dry_run:
                print(f"   🗑️  WOULD DELETE: {old_hours}h from '{old_source}' @ {old_timestamp}")
                deleted_count += 1
            else:
                print(f"   🗑️  DELETING: {old_hours}h from '{old_source}' @ {old_timestamp}")

                try:
                    dynamodb.delete_item(
                        TableName=TABLE_NAME,
                        Key={
                            'ResourceName': {'S': resource_name},
                            'DateProjectCode': old_item['DateProjectCode']
                        }
                    )
                    deleted_count += 1
                except Exception as e:
                    print(f"      ❌ Failed to delete: {e}")

        kept_count += 1

    return kept_count, deleted_count


def main():
    """Main execution."""
    print("=" * 80)
    print("         FIND AND FIX DUPLICATE TIMESHEET ENTRIES")
    print("=" * 80)
    print()
    print("This script will find duplicate entries where the same person has")
    print("multiple entries for the same date and project code.")
    print()
    print("Strategy: Keep the MOST RECENT entry (by ProcessingTimestamp)")
    print()

    # Get all resources
    resources = get_all_resources()
    print(f"✅ Found {len(resources)} unique resources\n")

    # First pass: DRY RUN - find all duplicates
    print("=" * 80)
    print("PHASE 1: DRY RUN - Finding duplicates")
    print("=" * 80)
    print()

    total_duplicates = 0
    resources_with_duplicates = []

    for resource in resources:
        duplicates = find_duplicates_for_resource(resource)

        if len(duplicates) > 0:
            display_name = resource.replace('_', ' ')
            print(f"\n👤 {display_name}")
            print(f"   Found {len(duplicates)} duplicate groups")

            kept, deleted = delete_duplicate_entries(resource, duplicates, dry_run=True)
            total_duplicates += deleted
            resources_with_duplicates.append((resource, duplicates))

    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Resources with duplicates: {len(resources_with_duplicates)}")
    print(f"Total duplicate entries to delete: {total_duplicates}")

    if total_duplicates == 0:
        print("\n✅ No duplicates found! Database is clean.")
        return

    # Ask for confirmation
    print("\n" + "=" * 80)
    print("PHASE 2: DELETION")
    print("=" * 80)

    response = input(f"\nDo you want to DELETE {total_duplicates} duplicate entries? (yes/no): ")

    if response.lower() != 'yes':
        print("\n❌ Aborted. No changes made.")
        return

    # Actual deletion
    print("\n🗑️  Deleting duplicates...\n")

    total_kept = 0
    total_deleted = 0

    for resource, duplicates in resources_with_duplicates:
        display_name = resource.replace('_', ' ')
        print(f"\n👤 {display_name}")

        kept, deleted = delete_duplicate_entries(resource, duplicates, dry_run=False)
        total_kept += kept
        total_deleted += deleted

    # Final summary
    print("\n" + "=" * 80)
    print("✅ DELETION COMPLETE")
    print("=" * 80)
    print(f"Entries kept: {total_kept}")
    print(f"Entries deleted: {total_deleted}")
    print()


if __name__ == '__main__':
    main()
