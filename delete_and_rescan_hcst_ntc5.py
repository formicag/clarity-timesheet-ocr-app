#!/usr/bin/env python3
"""
Delete and rescan HCST/NTC5 timesheet entries for Gareth Jones.

This script:
1. Deletes all DynamoDB entries for the 2 affected images
2. Triggers Lambda to reprocess those images
"""
import boto3
import json
import time

# AWS Configuration
REGION = 'us-east-1'
TABLE_NAME = 'TimesheetOCR-dev'
LAMBDA_FUNCTION = 'TimesheetOCR-ocr-dev'
S3_BUCKET = 'timesheetocr-input-dev-016164185850'

# Images to reprocess
IMAGES = [
    '2025-10-21_17h24_57.png',  # HCST314980
    '2025-10-15_20h40_56.png',  # NTC5124690
]

# Initialize AWS clients
dynamodb = boto3.client('dynamodb', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)

def delete_entries_for_image(image_name):
    """Delete all DynamoDB entries for a specific source image."""
    print(f"\n🗑️  Deleting entries for: {image_name}")

    # Scan for entries with this SourceImage
    scan_kwargs = {
        'TableName': TABLE_NAME,
        'FilterExpression': 'SourceImage = :img',
        'ExpressionAttributeValues': {
            ':img': {'S': image_name}
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
            project_name = item.get('ProjectName', {}).get('S', 'N/A')

            print(f"   - Deleting: {resource_name} | {date} | {project_code}")

            # Delete the item using correct composite key
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

def trigger_lambda_for_image(image_name):
    """Trigger Lambda to reprocess an image."""
    print(f"\n🔄 Triggering Lambda for: {image_name}")

    # Create S3 event payload
    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {
                        "name": S3_BUCKET
                    },
                    "object": {
                        "key": image_name
                    }
                }
            }
        ]
    }

    try:
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            InvocationType='Event',  # Async invocation
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
    print("Delete and Rescan HCST/NTC5 Timesheets")
    print("=" * 60)
    print(f"\nTarget images:")
    for img in IMAGES:
        print(f"  - {img}")
    print()

    total_deleted = 0

    # Step 1: Delete existing entries
    print("\n📋 STEP 1: Deleting existing DynamoDB entries")
    print("-" * 60)
    for image in IMAGES:
        deleted = delete_entries_for_image(image)
        total_deleted += deleted
        time.sleep(1)  # Brief pause between operations

    print(f"\n✅ Total entries deleted: {total_deleted}")

    # Step 2: Trigger Lambda to reprocess
    print("\n📋 STEP 2: Triggering Lambda to reprocess images")
    print("-" * 60)
    successful = 0
    for image in IMAGES:
        if trigger_lambda_for_image(image):
            successful += 1
        time.sleep(1)  # Brief pause between invocations

    print(f"\n✅ Successfully triggered: {successful}/{len(IMAGES)} images")

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Entries deleted: {total_deleted}")
    print(f"Images reprocessed: {successful}/{len(IMAGES)}")
    print("\n⏳ Wait 1-2 minutes for Lambda to process the images")
    print("Then check DynamoDB to verify the corrections:")
    print()
    print("Expected results:")
    print("  - HCST314980 should be recognized as valid (no warnings)")
    print("  - NTC5124690 should be recognized as valid (no warnings)")
    print("=" * 60)

if __name__ == '__main__':
    main()
