#!/usr/bin/env python3
"""
Fix ALL name duplicates in the database.

Variations found:
- Nell_Pomfret (315) → Neil_Pomfret
- Diego_Diego (133) → Diogo_Diogo
- Gary_Manderacas (7) → Gary_Mandaracas
"""
import boto3
import json
import time

# AWS Configuration
REGION = 'us-east-1'
TABLE_NAME = 'TimesheetOCR-dev'
LAMBDA_FUNCTION = 'TimesheetOCR-ocr-dev'
S3_BUCKET = 'timesheetocr-input-dev-016164185850'

# Name corrections to apply
NAME_CORRECTIONS = {
    'Nell_Pomfret': 'Neil_Pomfret',
    'Diego_Diego': 'Diogo_Diogo',
    'Gary_Manderacas': 'Gary_Mandaracas'
}

# Initialize AWS clients
dynamodb = boto3.client('dynamodb', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)

def get_all_images_for_person(resource_name):
    """Get all unique source images for a person."""
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
        return list(images)
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []

def delete_all_entries_for_person(resource_name):
    """Delete all DynamoDB entries for a person."""
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

        for item in items:
            resource_name_key = item['ResourceName']['S']
            date_project_code = item['DateProjectCode']['S']

            dynamodb.delete_item(
                TableName=TABLE_NAME,
                Key={
                    'ResourceName': {'S': resource_name_key},
                    'DateProjectCode': {'S': date_project_code}
                }
            )
            deleted_count += 1

        return deleted_count
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return 0

def trigger_lambda_for_images(images, batch_size=5):
    """Trigger Lambda to reprocess a list of images."""
    successful = 0
    failed = 0

    for i, image in enumerate(images, 1):
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": S3_BUCKET},
                        "object": {"key": image}
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
                print(f"   [{i}/{len(images)}] ✓ {image}")
            else:
                failed += 1
                print(f"   [{i}/{len(images)}] ✗ {image} (Status: {response['StatusCode']})")

        except Exception as e:
            failed += 1
            print(f"   [{i}/{len(images)}] ✗ {image} (Error: {e})")

        # Throttle
        if i % batch_size == 0:
            time.sleep(2)

    return successful, failed

def main():
    """Main execution."""
    print("=" * 80)
    print("         FIX ALL NAME DUPLICATES")
    print("=" * 80)

    print("\n📊 NAME CORRECTIONS TO APPLY:")
    for wrong, correct in NAME_CORRECTIONS.items():
        print(f"   {wrong} → {correct}")

    total_deleted = 0
    total_images = 0
    all_images = []

    # Process each incorrect name
    for incorrect_name, correct_name in NAME_CORRECTIONS.items():
        print("\n" + "=" * 80)
        print(f"Processing: {incorrect_name} → {correct_name}")
        print("=" * 80)

        # Get images
        print(f"\n📁 Finding images for {incorrect_name}...")
        images = get_all_images_for_person(incorrect_name)
        print(f"   Found {len(images)} unique images")

        if len(images) == 0:
            print(f"   ⚠️  No entries found for {incorrect_name}")
            continue

        all_images.extend(images)
        total_images += len(images)

        # Delete entries
        print(f"\n🗑️  Deleting {incorrect_name} entries...")
        deleted = delete_all_entries_for_person(incorrect_name)
        print(f"   ✅ Deleted {deleted} entries")
        total_deleted += deleted

    # Rescan all images
    print("\n" + "=" * 80)
    print(f"RESCANNING {total_images} IMAGES")
    print("=" * 80)
    print("(Name normalization will create correct entries)\n")

    successful, failed = trigger_lambda_for_images(all_images)

    # Wait for processing
    print("\n" + "=" * 80)
    print("WAITING FOR PROCESSING")
    print("=" * 80)

    wait_time = min(90, total_images * 3)
    print(f"⏳ Waiting {wait_time} seconds...\n")
    time.sleep(wait_time)

    # Verify results
    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)

    for incorrect_name, correct_name in NAME_CORRECTIONS.items():
        # Check incorrect (should be 0)
        query_kwargs = {
            'TableName': TABLE_NAME,
            'KeyConditionExpression': 'ResourceName = :rn',
            'Select': 'COUNT',
            'ExpressionAttributeValues': {':rn': {'S': incorrect_name}}
        }
        incorrect_count = dynamodb.query(**query_kwargs)['Count']

        # Check correct (should have entries)
        query_kwargs['ExpressionAttributeValues'][':rn']['S'] = correct_name
        correct_count = dynamodb.query(**query_kwargs)['Count']

        status_incorrect = "✅" if incorrect_count == 0 else "❌"
        status_correct = "✅" if correct_count > 0 else "⚠️"

        print(f"\n{incorrect_name}:")
        print(f"   {status_incorrect} Incorrect entries: {incorrect_count} (should be 0)")
        print(f"   {status_correct} Correct entries ({correct_name}): {correct_count}")

    # Final summary
    print("\n" + "=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    print(f"Entries deleted: {total_deleted}")
    print(f"Images rescanned: {successful}/{total_images}")
    print(f"Failed: {failed}")

    if failed == 0:
        print("\n✅ ALL OPERATIONS SUCCESSFUL!")
    else:
        print(f"\n⚠️  {failed} images failed to process")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
