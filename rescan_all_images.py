#!/usr/bin/env python3
"""
Re-trigger OCR for all S3 images (after database flush)
Uses the improved OCR prompt with quality improvements
"""
import boto3
import json
import time
from botocore.exceptions import ClientError

S3_BUCKET = "timesheetocr-input-dev-016164185850"
LAMBDA_FUNCTION = "TimesheetOCR-ocr-dev"
REGION = "us-east-1"

def get_s3_images():
    """Get list of all images in S3 bucket"""
    print("Getting list of images from S3...")
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
    print("Triggering OCR for all images...")
    print("=" * 80)
    print(f"This will process {len(images)} images")
    print("Note: Processing will happen asynchronously in the background")
    print()
    print("Quality improvements active:")
    print("  ✓ Bank holiday detection")
    print("  ✓ Project code format validation")
    print("  ✓ OCR digit confusion correction (0↔9, 0↔8, 6↔5, etc.)")
    print("  ✓ Category label detection (DESIGN, LABOUR, INFRA, DATA)")
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

        # Small delay to avoid rate limiting
        if i % 50 == 0:
            time.sleep(1)

    print()
    print("=" * 80)
    print(f"✓ Triggered OCR for {success} images")
    if failed > 0:
        print(f"✗ Failed to trigger {failed} images")
    print("=" * 80)
    print()
    print("Processing is happening in the background.")
    print("Depending on the number of images, this may take 10-30 minutes.")
    print()
    print("📊 Monitor progress:")
    print()
    print("1. Check Lambda logs (look for 📝 🏦 ⚠️  indicators):")
    print(f"   aws logs tail /aws/lambda/{LAMBDA_FUNCTION} --follow --region {REGION}")
    print()
    print("2. Check DynamoDB item count:")
    print(f"   aws dynamodb describe-table --table-name TimesheetOCR-dev --region {REGION} --query 'Table.ItemCount'")
    print()
    print("3. Use the UI:")
    print("   python3 timesheet_ui.py")
    print()
    print("📈 After processing is complete, run quality report:")
    print("   python3 generate_quality_report.py")
    print()

def main():
    print()
    print("=" * 80)
    print("RESCAN ALL TIMESHEET IMAGES")
    print("=" * 80)
    print()
    print("Database has been flushed. Ready to rescan with quality improvements!")
    print()

    # Get images from S3
    images = get_s3_images()

    if len(images) == 0:
        print("No images found in S3 bucket.")
        return

    # Trigger OCR for all images
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
