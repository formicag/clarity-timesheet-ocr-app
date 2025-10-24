#!/usr/bin/env python3
"""
Flush DynamoDB database - Delete all timesheet entries
"""
import boto3
from datetime import datetime

DYNAMODB_TABLE = "TimesheetOCR-dev"
REGION = "us-east-1"

def flush_database():
    """Delete all items from DynamoDB table"""
    print("=" * 80)
    print("FLUSH DATABASE - DELETE ALL ENTRIES")
    print("=" * 80)
    print()
    print(f"Table: {DYNAMODB_TABLE}")
    print(f"Region: {REGION}")
    print()
    
    # Confirm
    response = input("⚠️  WARNING: This will delete ALL entries. Type 'DELETE ALL' to confirm: ")
    if response != 'DELETE ALL':
        print("Aborted. No data was deleted.")
        return
    
    print()
    print("Creating backup before deletion...")
    
    # Backup first
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)
    
    backup_file = f"backup_before_flush_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Scan all items
    response = table.scan()
    items = response['Items']
    
    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response['Items'])
    
    print(f"Found {len(items)} entries to delete")
    
    # Save backup
    import json
    from decimal import Decimal
    
    # Convert Decimal to float for JSON
    def decimal_to_float(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [decimal_to_float(item) for item in obj]
        return obj
    
    items_serializable = [decimal_to_float(item) for item in items]
    
    with open(backup_file, 'w') as f:
        json.dump(items_serializable, f, indent=2)
    
    print(f"✓ Backup saved to: {backup_file}")
    print()
    print("Deleting all entries...")
    
    # Delete all items
    deleted_count = 0
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(
                Key={
                    'ResourceName': item['ResourceName'],
                    'DateProjectCode': item['DateProjectCode']
                }
            )
            deleted_count += 1
            
            if deleted_count % 100 == 0:
                print(f"  Deleted {deleted_count}/{len(items)}...")
    
    print()
    print("=" * 80)
    print("✓ DATABASE FLUSHED")
    print("=" * 80)
    print(f"Deleted: {deleted_count} entries")
    print(f"Backup: {backup_file}")
    print()
    print("You can now start fresh imports!")
    print()

if __name__ == "__main__":
    try:
        flush_database()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
