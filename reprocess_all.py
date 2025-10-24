#!/usr/bin/env python3
"""
Flush DynamoDB and re-trigger OCR for all S3 images
This will use the improved OCR prompt and normalization rules
"""
import boto3
import json
import time
from botocore.exceptions import ClientError

DYNAMODB_TABLE = "TimesheetOCR-dev"
S3_BUCKET = "timesheetocr-input-dev-016164185850"
LAMBDA_FUNCTION = "TimesheetOCR-ocr-dev"
REGION = "us-east-1"

def flush_dynamodb():
    """Delete all items from DynamoDB table"""
    print("Step 1: Flushing DynamoDB table...")
    print("=" * 80)

    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)

    # Get all items
    response = table.scan()
    items = response.get('Items', [])

    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))

    print(f"Found {len(items)} items to delete")

    if len(items) == 0:
        print("✓ Table is already empty")
        return

    # Delete in batches
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
            if deleted % 100 == 0:
                print(f"  Deleted {deleted}/{len(items)}...")

    print(f"✓ Deleted all {deleted} items from DynamoDB")
    print()

def get_s3_images():
    """Get list of all images in S3 bucket"""
    print("Step 2: Getting list of images from S3...")
    print("=" * 80)

    s3 = boto3.client('s3', region_name=REGION)

    images = []
    paginator = s3.get_paginator('list_objects_v2')

    for page in paginator.paginate(Bucket=S3_BUCKET):
        if 'Contents' not in page:
            continue

        for obj in page['Contents']:
            key = obj['Key']
            # Only process .png and .jpg files, skip directories
            if key.lower().endswith(('.png', '.jpg', '.jpeg')) and not key.startswith('quicksight-data/'):
                images.append(key)

    print(f"✓ Found {len(images)} images to process")
    print()
    return images

def trigger_lambda_for_image(lambda_client, image_key):
    """Trigger Lambda function for a specific image"""

    # Create S3 event payload
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
    except ClientError as e:
        print(f"  ✗ Error invoking Lambda for {image_key}: {e}")
        return False

def trigger_ocr_for_all_images(images):
    """Trigger OCR Lambda for all images"""
    print("Step 3: Triggering OCR for all images...")
    print("=" * 80)
    print(f"This will process {len(images)} images")
    print("Note: Processing will happen asynchronously in the background")
    print()

    confirm = input("Continue? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Aborted.")
        return

    lambda_client = boto3.client('lambda', region_name=REGION)

    print()
    print("Triggering Lambda invocations...")

    success = 0
    failed = 0

    for i, image in enumerate(images, 1):
        if trigger_lambda_for_image(lambda_client, image):
            success += 1
        else:
            failed += 1

        # Progress update every 10 images
        if i % 10 == 0:
            print(f"  Progress: {i}/{len(images)} ({success} triggered, {failed} failed)")

        # Small delay to avoid rate limiting (optional)
        if i % 50 == 0:
            time.sleep(1)

    print()
    print(f"✓ Triggered OCR for {success} images")
    if failed > 0:
        print(f"✗ Failed to trigger {failed} images")
    print()
    print("=" * 80)
    print()
    print("Processing is happening in the background.")
    print("Depending on the number of images, this may take several minutes.")
    print()
    print("You can monitor progress by:")
    print("1. Checking DynamoDB item count:")
    print(f"   aws dynamodb describe-table --table-name {DYNAMODB_TABLE} --region {REGION} --query 'Table.ItemCount'")
    print()
    print("2. Checking Lambda logs:")
    print(f"   aws logs tail /aws/lambda/{LAMBDA_FUNCTION} --follow --region {REGION}")
    print()
    print("3. Checking the UI:")
    print("   python3 timesheet_ui.py")
    print()
    print("Once processing is complete, run:")
    print("   python3 analyze_projects.py")
    print()

def main():
    print()
    print("=" * 80)
    print("BULK RE-PROCESSING OF TIMESHEET IMAGES")
    print("=" * 80)
    print()
    print("This script will:")
    print("1. Delete all existing data from DynamoDB")
    print("2. Re-trigger OCR for all images in S3")
    print("3. Use the improved OCR prompt and normalization rules")
    print()
    print("⚠️  WARNING: This will delete all current DynamoDB data!")
    print("    (A backup has been created in the current directory)")
    print()

    confirm = input("Are you sure you want to proceed? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Aborted.")
        return

    print()

    # Step 1: Flush DynamoDB
    flush_dynamodb()

    # Step 2: Get images from S3
    images = get_s3_images()

    # Step 3: Trigger OCR for all images
    trigger_ocr_for_all_images(images)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
