#!/usr/bin/env python3
"""
Re-process failed images by triggering Lambda function.
Reads failed_images.json and processes each image.
"""
import boto3
import json
import time
from datetime import datetime

S3_BUCKET = "timesheetocr-input-dev-016164185850"
LAMBDA_FUNCTION = "TimesheetOCR-ocr-dev"
REGION = "us-east-1"


def load_failed_images():
    """Load failed images from JSON file"""
    try:
        with open('failed_images.json', 'r') as f:
            data = json.load(f)
            return data.get('failed_images', [])
    except FileNotFoundError:
        print("❌ failed_images.json not found. Run find_failed_images.py first.")
        return None


def trigger_lambda_for_image(lambda_client, image_key):
    """Trigger Lambda function for a specific image"""
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
            InvocationType='RequestResponse',  # Synchronous for better error tracking
            Payload=json.dumps(payload)
        )

        # Parse response
        result = json.loads(response['Payload'].read())

        if response['StatusCode'] == 200 and 'errorMessage' not in result:
            # Success
            if isinstance(result, dict) and 'body' in result:
                body = json.loads(result['body'])
                return {
                    'success': True,
                    'resource_name': body.get('resource_name', 'Unknown'),
                    'entries': body.get('entries_stored', 0),
                    'message': 'Success'
                }
            return {'success': True, 'message': 'Processed'}
        else:
            # Error
            error_msg = result.get('errorMessage', 'Unknown error')
            return {'success': False, 'message': error_msg}

    except Exception as e:
        return {'success': False, 'message': str(e)}


def reprocess_failed_images(failed_images, batch_size=10):
    """Re-process all failed images with rate limiting"""
    print(f"🔄 Starting re-processing of {len(failed_images)} failed images...")
    print(f"⏱️  Rate limiting: 3 second delay between each request")
    print()

    lambda_client = boto3.client('lambda', region_name=REGION)

    results = {
        'success': 0,
        'failed': 0,
        'errors': []
    }

    for i, img in enumerate(failed_images, 1):
        image_key = img['key']
        print(f"[{i}/{len(failed_images)}] Processing: {image_key}")

        result = trigger_lambda_for_image(lambda_client, image_key)

        if result['success']:
            print(f"  ✓ Success: {result.get('resource_name', '')} - {result.get('entries', 0)} entries")
            results['success'] += 1
        else:
            print(f"  ✗ Failed: {result['message']}")
            results['failed'] += 1
            results['errors'].append({
                'image': image_key,
                'error': result['message']
            })

        # Rate limiting: delay between EVERY request to avoid throttling
        if i < len(failed_images):  # Don't delay after the last one
            time.sleep(3)  # 3 seconds between requests (20 requests/minute)

        # Extra delay every batch
        if i % batch_size == 0:
            print(f"  📊 Processed {i} images, extra 5 second pause...")
            time.sleep(5)

    return results


def save_reprocess_results(results):
    """Save re-processing results to file"""
    output_file = f"reprocess_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    return output_file


def main():
    print("=" * 80)
    print("RE-PROCESS FAILED IMAGES")
    print("=" * 80)
    print()

    # Load failed images
    failed_images = load_failed_images()
    if failed_images is None:
        return

    if len(failed_images) == 0:
        print("🎉 No failed images to process!")
        return

    print(f"Found {len(failed_images)} failed images to re-process")
    print()

    # Confirm
    confirm = input("Continue with re-processing? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Aborted.")
        return

    print()

    # Process
    results = reprocess_failed_images(failed_images)

    # Save results
    output_file = save_reprocess_results(results)

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total attempted:     {len(failed_images)}")
    print(f"✓ Successful:        {results['success']}")
    print(f"✗ Still failed:      {results['failed']}")
    print(f"Success rate:        {(results['success'] / len(failed_images) * 100):.1f}%")
    print()
    print(f"Detailed results saved to: {output_file}")

    if results['errors']:
        print()
        print("Still failing images (first 5):")
        for error in results['errors'][:5]:
            print(f"  - {error['image']}: {error['error']}")

    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
