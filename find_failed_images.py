#!/usr/bin/env python3
"""
Find images that failed to process by comparing S3 bucket with DynamoDB records.

This script:
1. Gets all images from S3 bucket
2. Checks DynamoDB for successful processing records
3. Identifies images that have no corresponding DB records (failed)
4. Saves list of failed images for re-processing
"""
import boto3
import json
from datetime import datetime
from collections import defaultdict

S3_BUCKET = "timesheetocr-input-dev-016164185850"
DYNAMODB_TABLE = "TimesheetOCR-dev"
REGION = "us-east-1"


def get_all_s3_images():
    """Get list of all PNG/JPG images from S3 bucket"""
    print("📁 Scanning S3 bucket for images...")
    s3 = boto3.client('s3', region_name=REGION)

    images = []
    paginator = s3.get_paginator('list_objects_v2')

    for page in paginator.paginate(Bucket=S3_BUCKET):
        if 'Contents' not in page:
            continue

        for obj in page['Contents']:
            key = obj['Key']
            # Only process image files, skip directories
            if key.lower().endswith(('.png', '.jpg', '.jpeg')) and not key.startswith('quicksight-data/'):
                images.append({
                    'key': key,
                    'size': obj['Size'],
                    'last_modified': obj['LastModified']
                })

    print(f"✓ Found {len(images)} images in S3")
    return images


def get_processed_images():
    """Get list of source images that were successfully processed in DynamoDB"""
    print("📊 Checking DynamoDB for processed images...")
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)

    # Scan entire table
    response = table.scan(
        ProjectionExpression='SourceImage'
    )
    items = response.get('Items', [])

    while 'LastEvaluatedKey' in response:
        response = table.scan(
            ProjectionExpression='SourceImage',
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response.get('Items', []))

    # Extract unique source images
    processed_images = set()
    for item in items:
        source = item.get('SourceImage', '')
        if source:
            processed_images.add(source)

    print(f"✓ Found {len(processed_images)} unique processed images in DynamoDB")
    return processed_images


def find_failed_images(all_images, processed_images):
    """Identify images that don't have DB records"""
    print("\n🔍 Analyzing for failed images...")

    failed = []
    for img in all_images:
        if img['key'] not in processed_images:
            failed.append(img)

    return failed


def save_failed_images(failed_images):
    """Save list of failed images to file"""
    output_file = 'failed_images.json'

    data = {
        'scan_timestamp': datetime.utcnow().isoformat() + 'Z',
        'total_s3_images': 0,
        'failed_count': len(failed_images),
        'failed_images': failed_images
    }

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)

    return output_file


def main():
    print("=" * 80)
    print("FAILED IMAGE DETECTION")
    print("=" * 80)
    print()

    # Get all images from S3
    all_images = get_all_s3_images()

    # Get processed images from DynamoDB
    processed_images = get_processed_images()

    # Find failed images
    failed = find_failed_images(all_images, processed_images)

    # Display results
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Total images in S3:        {len(all_images)}")
    print(f"Successfully processed:     {len(processed_images)}")
    print(f"Failed to process:          {len(failed)}")
    print(f"Success rate:               {(len(processed_images) / len(all_images) * 100):.1f}%")
    print()

    if failed:
        # Save to file
        output_file = save_failed_images(failed)
        print(f"✓ Failed images list saved to: {output_file}")
        print()
        print("Failed images:")
        for img in failed[:10]:  # Show first 10
            print(f"  - {img['key']}")

        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")

        print()
        print("Next steps:")
        print("1. Review failed_images.json")
        print("2. Run: python3 reprocess_failed.py")
        print("   OR")
        print("3. Use the UI 'Re-scan Failed Images' button")
    else:
        print("🎉 No failed images found! All S3 images have been processed.")

    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
