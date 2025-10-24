#!/usr/bin/env python3
"""
Rescan timesheets for people with remaining format violations.
This will reprocess only the affected images with the enhanced prompt.
"""
import boto3
import json
import time
from collections import defaultdict

# AWS Configuration
DYNAMODB_TABLE = "TimesheetOCR-dev"
S3_BUCKET = "timesheetocr-input-dev-016164185850"
LAMBDA_FUNCTION = "TimesheetOCR-ocr-dev"
REGION = "us-east-1"

# People with remaining issues (from quality report)
AFFECTED_PEOPLE = [
    'Jon_Mays',        # 7 records - DESIGNA label
    'Gareth_Jones',    # 7 records - NTCS prefix
    'Matthew_Garretty' # 14 records - various
]

def get_source_images_for_people(people):
    """Get unique source images for affected people from DynamoDB."""
    print("Finding source images for affected people...")
    print("=" * 80)

    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)

    images_by_person = defaultdict(set)

    for person in people:
        print(f"Querying for: {person}")

        # Query for this person
        response = table.query(
            KeyConditionExpression='ResourceName = :rn',
            ExpressionAttributeValues={
                ':rn': person
            },
            ProjectionExpression='SourceImage'
        )

        items = response.get('Items', [])

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.query(
                KeyConditionExpression='ResourceName = :rn',
                ExpressionAttributeValues={
                    ':rn': person
                },
                ExclusiveStartKey=response['LastEvaluatedKey'],
                ProjectionExpression='SourceImage'
            )
            items.extend(response.get('Items', []))

        # Collect unique source images
        for item in items:
            source_image = item.get('SourceImage')
            if source_image:
                images_by_person[person].add(source_image)

        print(f"  Found {len(images_by_person[person])} unique images")

    print()
    return images_by_person


def delete_entries_for_people(people):
    """Delete all DynamoDB entries for affected people."""
    print("Deleting entries for affected people...")
    print("=" * 80)

    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)

    total_deleted = 0

    for person in people:
        print(f"Deleting entries for: {person}")

        # Query for this person
        response = table.query(
            KeyConditionExpression='ResourceName = :rn',
            ExpressionAttributeValues={
                ':rn': person
            }
        )

        items = response.get('Items', [])

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.query(
                KeyConditionExpression='ResourceName = :rn',
                ExpressionAttributeValues={
                    ':rn': person
                },
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        # Delete in batch
        deleted = 0
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(
                    Key={
                        'ResourceName': item['ResourceName'],
                        'DateProjectCode': item['DateProjectCode']
                    }
                )
                deleted += 1

        print(f"  Deleted {deleted} entries")
        total_deleted += deleted

    print(f"\n✓ Total deleted: {total_deleted} entries")
    print()
    return total_deleted


def trigger_lambda_for_image(lambda_client, image_key):
    """Trigger Lambda function for a specific image."""
    payload = {
        "Records": [{
            "s3": {
                "bucket": {
                    "name": S3_BUCKET
                },
                "object": {
                    "key": image_key
                }
            }
        }]
    }

    try:
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        return response['StatusCode'] == 202
    except Exception as e:
        print(f"  ✗ Error invoking Lambda for {image_key}: {e}")
        return False


def rescan_images(images_by_person):
    """Rescan all images for affected people."""
    print("Rescanning images with enhanced quality improvements...")
    print("=" * 80)

    # Flatten to unique images
    all_images = set()
    for images in images_by_person.values():
        all_images.update(images)

    print(f"Total unique images to process: {len(all_images)}")
    print()
    print("Enhanced features active:")
    print("  ✓ DESIGNA category label detection")
    print("  ✓ NTCS alternative reference code detection")
    print("  ✓ Bank holiday detection")
    print("  ✓ OCR digit confusion correction")
    print()

    confirm = input("Continue with rescan? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Aborted.")
        return

    lambda_client = boto3.client('lambda', region_name=REGION)

    print()
    print("Triggering Lambda invocations...")

    success = 0
    failed = 0

    for i, image in enumerate(sorted(all_images), 1):
        if trigger_lambda_for_image(lambda_client, image):
            success += 1
        else:
            failed += 1

        # Progress update
        if i % 5 == 0:
            print(f"  Progress: {i}/{len(all_images)} ({success} triggered, {failed} failed)")

        # Small delay to avoid rate limiting
        if i % 10 == 0:
            time.sleep(0.5)

    print()
    print("=" * 80)
    print(f"✓ Triggered OCR for {success} images")
    if failed > 0:
        print(f"✗ Failed to trigger {failed} images")
    print("=" * 80)
    print()


def main():
    print()
    print("=" * 80)
    print("RESCAN AFFECTED PEOPLE - TARGETED REPROCESSING")
    print("=" * 80)
    print()
    print("This script will:")
    print("1. Find all source images for affected people")
    print("2. Delete their current entries from DynamoDB")
    print("3. Rescan their images with enhanced quality improvements")
    print()
    print(f"Affected people ({len(AFFECTED_PEOPLE)}):")
    for person in AFFECTED_PEOPLE:
        print(f"  - {person}")
    print()

    confirm = input("Proceed with targeted rescan? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Aborted.")
        return

    print()

    # Step 1: Get source images
    images_by_person = get_source_images_for_people(AFFECTED_PEOPLE)

    # Show summary
    print("Summary:")
    print("-" * 80)
    for person, images in images_by_person.items():
        print(f"{person}: {len(images)} images")
    print()

    # Step 2: Delete entries
    delete_entries_for_people(AFFECTED_PEOPLE)

    # Step 3: Rescan images
    rescan_images(images_by_person)

    print()
    print("Processing is happening in the background.")
    print()
    print("📊 Monitor progress:")
    print(f"   aws logs tail /aws/lambda/{LAMBDA_FUNCTION} --follow --region {REGION}")
    print()
    print("📈 After ~5 minutes, run quality report:")
    print("   python3 generate_quality_report.py")
    print()
    print("Expected result: Format violations should drop to ~0-5 records")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
