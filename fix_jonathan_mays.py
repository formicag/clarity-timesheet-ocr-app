#!/usr/bin/env python3
"""
Fix Jonathan Mays OCR errors and rescan timesheets.

Problem:
- Team roster has "Jonathan Mays"
- OCR reads as "Jon Maya", "Jon Mayo", "Jon Mays"
- Creates 3 incorrect database entries

Solution:
1. Add name aliases to team_roster.json
2. Delete all entries for Jon_Maya, Jon_Mayo, Jon_Mays
3. Rescan all 16 images
4. Entries will be created as Jonathan_Mays (correct)
"""
import boto3
import json
import time

# AWS Configuration
REGION = 'us-east-1'
TABLE_NAME = 'TimesheetOCR-dev'
LAMBDA_FUNCTION = 'TimesheetOCR-ocr-dev'
S3_BUCKET = 'timesheetocr-input-dev-016164185850'

# Incorrect name variations to delete
INCORRECT_NAMES = ['Jon_Maya', 'Jon_Mayo', 'Jon_Mays']

# Initialize AWS clients
dynamodb = boto3.client('dynamodb', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)

def get_all_images_for_person(resource_name):
    """Get all unique source images for a person."""
    print(f"   Finding images for {resource_name}...")

    query_kwargs = {
        'TableName': TABLE_NAME,
        'KeyConditionExpression': 'ResourceName = :rn',
        'ProjectionExpression': 'SourceImage',
        'ExpressionAttributeValues': {
            ':rn': {'S': resource_name}
        }
    }

    images = set()

    try:
        response = dynamodb.query(**query_kwargs)
        for item in response.get('Items', []):
            if 'SourceImage' in item:
                images.add(item['SourceImage']['S'])

        print(f"   Found {len(images)} unique images for {resource_name}")
        return list(images)

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []

def delete_all_entries_for_person(resource_name):
    """Delete all DynamoDB entries for a person."""
    print(f"\n🗑️  Deleting all entries for: {resource_name}")

    query_kwargs = {
        'TableName': TABLE_NAME,
        'KeyConditionExpression': 'ResourceName = :rn',
        'ExpressionAttributeValues': {
            ':rn': {'S': resource_name}
        }
    }

    deleted_count = 0

    try:
        response = dynamodb.query(**query_kwargs)
        items = response.get('Items', [])

        print(f"   Found {len(items)} entries to delete")

        for item in items:
            resource_name = item['ResourceName']['S']
            date_project_code = item['DateProjectCode']['S']

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
        print(f"   ❌ Error: {e}")
        return 0

def trigger_lambda_for_images(images):
    """Trigger Lambda to reprocess a list of images."""
    print(f"\n🔄 Triggering Lambda for {len(images)} images...")

    successful = 0
    failed = 0

    for i, image in enumerate(images, 1):
        print(f"   [{i}/{len(images)}] Processing: {image}")

        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {
                            "name": S3_BUCKET
                        },
                        "object": {
                            "key": image
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

            if response['StatusCode'] == 202:
                successful += 1
            else:
                failed += 1
                print(f"      ⚠️  Status: {response['StatusCode']}")

        except Exception as e:
            failed += 1
            print(f"      ❌ Error: {e}")

        # Throttle to avoid overwhelming Lambda
        if i % 5 == 0:
            time.sleep(2)

    print(f"\n   ✅ Successfully triggered: {successful}/{len(images)}")
    if failed > 0:
        print(f"   ⚠️  Failed: {failed}/{len(images)}")

    return successful, failed

def verify_results():
    """Verify that entries were created correctly."""
    print("\n📋 Verifying results...")

    # Check incorrect names (should be 0)
    print("\n   Checking incorrect name variations (should be 0):")
    for name in INCORRECT_NAMES:
        query_kwargs = {
            'TableName': TABLE_NAME,
            'KeyConditionExpression': 'ResourceName = :rn',
            'Select': 'COUNT',
            'ExpressionAttributeValues': {
                ':rn': {'S': name}
            }
        }
        response = dynamodb.query(**query_kwargs)
        count = response['Count']
        status = "✅" if count == 0 else "❌"
        print(f"   {status} {name}: {count} entries")

    # Check correct name (should have entries)
    print("\n   Checking correct name (should have entries):")
    query_kwargs = {
        'TableName': TABLE_NAME,
        'KeyConditionExpression': 'ResourceName = :rn',
        'Select': 'COUNT',
        'ExpressionAttributeValues': {
            ':rn': {'S': 'Jonathan_Mays'}
        }
    }
    response = dynamodb.query(**query_kwargs)
    count = response['Count']
    status = "✅" if count > 0 else "⚠️"
    print(f"   {status} Jonathan_Mays: {count} entries")

    return count

def main():
    """Main execution."""
    print("=" * 70)
    print("         FIX JONATHAN MAYS OCR ERRORS")
    print("=" * 70)

    print("\n📊 CURRENT STATE:")
    print("   Team roster: Jonathan Mays")
    print("   Database has: Jon_Maya, Jon_Mayo, Jon_Mays (incorrect)")
    print("   Goal: All entries under Jonathan_Mays\n")

    # Step 1: Collect all images
    print("=" * 70)
    print("STEP 1: Collecting all source images")
    print("=" * 70)

    all_images = set()
    for name in INCORRECT_NAMES:
        images = get_all_images_for_person(name)
        all_images.update(images)

    all_images = sorted(list(all_images))
    print(f"\n   📁 Total unique images to reprocess: {len(all_images)}")

    # Step 2: Delete all incorrect entries
    print("\n" + "=" * 70)
    print("STEP 2: Deleting incorrect entries")
    print("=" * 70)

    total_deleted = 0
    for name in INCORRECT_NAMES:
        deleted = delete_all_entries_for_person(name)
        total_deleted += deleted
        time.sleep(1)

    print(f"\n   📊 Total entries deleted: {total_deleted}")

    # Step 3: Rescan all images
    print("\n" + "=" * 70)
    print("STEP 3: Rescanning images with corrected name normalization")
    print("=" * 70)
    print("   (Name aliases added to team_roster.json)")
    print("   Jon Maya/Mayo/Mays → Jonathan Mays\n")

    successful, failed = trigger_lambda_for_images(all_images)

    # Step 4: Wait for processing
    print("\n" + "=" * 70)
    print("STEP 4: Waiting for Lambda processing")
    print("=" * 70)

    wait_time = min(60, len(all_images) * 3)  # 3 seconds per image, max 60s
    print(f"   ⏳ Waiting {wait_time} seconds for processing...")
    time.sleep(wait_time)

    # Step 5: Verify
    print("\n" + "=" * 70)
    print("STEP 5: Verification")
    print("=" * 70)

    jonathan_count = verify_results()

    # Summary
    print("\n" + "=" * 70)
    print("                    📊 FINAL SUMMARY")
    print("=" * 70)

    print(f"\n   Images processed: {len(all_images)}")
    print(f"   Entries deleted: {total_deleted}")
    print(f"   Lambda invocations: {successful} successful, {failed} failed")
    print(f"   Jonathan_Mays entries: {jonathan_count}")

    if jonathan_count > 0 and failed == 0:
        print("\n   ✅ SUCCESS! All timesheets now under Jonathan_Mays")
    elif jonathan_count > 0 and failed > 0:
        print("\n   ⚠️  Mostly successful, but some images may need manual retry")
    else:
        print("\n   ⚠️  Wait a bit longer and check database manually")

    print("\n   Expected entries: ~217 (133 + 77 + 7)")
    print(f"   Actual entries: {jonathan_count}")

    if jonathan_count > 200:
        print("   ✅ Entry count looks correct!")

    print("\n" + "=" * 70)
    print("\n💡 TIP: You can now use the Team Management UI to verify")
    print("   that Jonathan Mays appears correctly in the dropdown.\n")

if __name__ == '__main__':
    main()
