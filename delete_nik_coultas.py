#!/usr/bin/env python3
"""
Delete all entries for Nik Coultas from DynamoDB.
This allows rescanning his timesheets to verify the zero-hour fix.
"""
import boto3
from decimal import Decimal

# AWS Configuration
REGION = 'us-east-1'
TABLE_NAME = 'TimesheetOCR-dev'

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

print("=" * 80)
print("DELETING ALL NIK COULTAS ENTRIES")
print("=" * 80)
print()

# Query all entries for Nik_Coultas
resource_name = "Nik_Coultas"

print(f"🔍 Querying entries for: {resource_name}")

response = table.query(
    KeyConditionExpression='ResourceName = :rn',
    ExpressionAttributeValues={
        ':rn': resource_name
    }
)

items = response.get('Items', [])

# Handle pagination
while 'LastEvaluatedKey' in response:
    response = table.query(
        KeyConditionExpression='ResourceName = :rn',
        ExpressionAttributeValues={
            ':rn': resource_name
        },
        ExclusiveStartKey=response['LastEvaluatedKey']
    )
    items.extend(response.get('Items', []))

print(f"✓ Found {len(items)} entries for {resource_name}")
print()

if len(items) == 0:
    print("❌ No entries found!")
else:
    print(f"🗑️  Deleting {len(items)} entries...")

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
            if deleted_count % 10 == 0:
                print(f"   Deleted {deleted_count}/{len(items)}...")

    print()
    print("=" * 80)
    print(f"✅ DELETED {deleted_count} ENTRIES FOR NIK COULTAS")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Find Nik's timesheet images in S3")
    print("2. Re-upload them to trigger Lambda OCR")
    print("3. Check database - should only have entries for days with >0 hours")
    print()
