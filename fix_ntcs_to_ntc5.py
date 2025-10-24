#!/usr/bin/env python3
"""
Delete NTCS entries and rescan with NTC5 correction.
"""
import boto3
import json
import time

# AWS Configuration
REGION = 'us-east-1'
TABLE_NAME = 'TimesheetOCR-dev'
LAMBDA_FUNCTION = 'TimesheetOCR-ocr-dev'
S3_BUCKET = 'timesheetocr-input-dev-016164185850'

# Image to reprocess
IMAGE = '2025-10-15_20h40_56.png'

# Initialize AWS clients
dynamodb = boto3.client('dynamodb', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)

def delete_ntcs_entries():
    """Delete all DynamoDB entries with NTCS124690."""
    print(f"\n🗑️  Deleting NTCS124690 entries...")

    # Scan for entries with EXACTLY NTCS124690 project code
    scan_kwargs = {
        'TableName': TABLE_NAME,
        'FilterExpression': 'ProjectCode = :code',
        'ExpressionAttributeValues': {
            ':code': {'S': 'NTCS124690'}
        }
    }

    deleted_count = 0

    try:
        response = dynamodb.scan(**scan_kwargs)
        items = response.get('Items', [])

        print(f"   Found {len(items)} entries to delete")

        for item in items:
            # Extract key attributes
            resource_name = item['ResourceName']['S']
            date_project_code = item['DateProjectCode']['S']
            date = item['Date']['S']
            project_code = item.get('ProjectCode', {}).get('S', 'N/A')

            print(f"   - Deleting: {resource_name} | {date} | {project_code}")

            # Delete the item
            dynamodb.delete_item(
                TableName=TABLE_NAME,
                Key={
                    'ResourceName': {'S': resource_name},
                    'DateProjectCode': {'S': date_project_code}
                }
            )
            deleted_count += 1

        print(f"   ✅ Deleted {deleted_count} entries")
        return deleted_count

    except Exception as e:
        print(f"   ❌ Error deleting entries: {e}")
        return 0

def trigger_lambda():
    """Trigger Lambda to reprocess the NTC5 image."""
    print(f"\n🔄 Triggering Lambda for: {IMAGE}")

    # Create S3 event payload
    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {
                        "name": S3_BUCKET
                    },
                    "object": {
                        "key": IMAGE
                    }
                }
            }
        ]
    }

    try:
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(event)
        )

        status_code = response['StatusCode']
        if status_code == 202:
            print(f"   ✅ Lambda triggered successfully (Status: {status_code})")
            return True
        else:
            print(f"   ⚠️  Lambda response: {status_code}")
            return False

    except Exception as e:
        print(f"   ❌ Error triggering Lambda: {e}")
        return False

def main():
    """Main execution."""
    print("=" * 60)
    print("Delete Duplicate NTCS124690 Entries")
    print("=" * 60)
    print("\nNOTE: NTC5124690 entries already exist (correct).")
    print("We're just deleting the duplicate NTCS124690 entries.")

    # Step 1: Delete NTCS entries
    print("\n📋 Deleting NTCS124690 duplicate entries")
    print("-" * 60)
    deleted = delete_ntcs_entries()

    # Verify
    print("\n📋 Verifying - checking remaining entries")
    print("-" * 60)

    # Check for NTCS entries (should be 0)
    scan_kwargs = {
        'TableName': TABLE_NAME,
        'FilterExpression': 'ProjectCode = :code',
        'ExpressionAttributeValues': {
            ':code': {'S': 'NTCS124690'}
        }
    }

    response = dynamodb.scan(**scan_kwargs)
    ntcs_items = response.get('Items', [])

    # Check for NTC5 entries (should exist)
    scan_kwargs['ExpressionAttributeValues'][':code']['S'] = 'NTC5124690'
    response = dynamodb.scan(**scan_kwargs)
    ntc5_items = response.get('Items', [])

    print(f"   NTCS124690 entries remaining: {len(ntcs_items)} (should be 0)")
    print(f"   NTC5124690 entries present: {len(ntc5_items)} (should be 7+)")

    if len(ntcs_items) == 0 and len(ntc5_items) > 0:
        print(f"\n   ✅ SUCCESS! Duplicates removed, NTC5 entries intact")
    else:
        print(f"\n   ⚠️  Check the results above")

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"NTCS duplicate entries deleted: {deleted}")
    print(f"NTC5 correct entries present: {len(ntc5_items)}")
    print("=" * 60)

if __name__ == '__main__':
    main()
