#!/usr/bin/env python3
"""
Test script to reprocess a specific timesheet with bank holiday detection.
Tests the image "2025-10-21_17h20_34.png" which has Aug 25 bank holiday.
"""
import boto3
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# AWS Configuration
INPUT_BUCKET = "timesheetocr-input-dev-016164185850"
LAMBDA_FUNCTION = "TimesheetOCR-ocr-dev"
AWS_REGION = "us-east-1"

# The specific image to test
TEST_IMAGE = "2025-10-21_17h20_34.png"

def invoke_lambda_for_image(image_key: str):
    """
    Invoke Lambda function to reprocess a specific image.

    Args:
        image_key: S3 key of the image to process
    """
    print(f"Testing bank holiday detection with image: {image_key}")
    print(f"Expected: Monday Aug 25, 2025 should have 0 hours (UK Summer bank holiday)")
    print("-" * 80)

    # Create Lambda client
    lambda_client = boto3.client('lambda', region_name=AWS_REGION)

    # Create S3 event payload
    payload = {
        "Records": [{
            "s3": {
                "bucket": {
                    "name": INPUT_BUCKET
                },
                "object": {
                    "key": image_key
                }
            }
        }]
    }

    print(f"\nInvoking Lambda function: {LAMBDA_FUNCTION}")
    print(f"Processing: s3://{INPUT_BUCKET}/{image_key}")
    print()

    # Invoke Lambda
    response = lambda_client.invoke(
        FunctionName=LAMBDA_FUNCTION,
        InvocationType='RequestResponse',  # Synchronous
        Payload=json.dumps(payload)
    )

    # Parse response
    response_payload = json.loads(response['Payload'].read())

    print("=" * 80)
    print("LAMBDA RESPONSE:")
    print("=" * 80)
    print(json.dumps(response_payload, indent=2))
    print()

    # Extract and display the parsed data
    if response_payload.get('statusCode') == 200:
        body = json.loads(response_payload.get('body', '{}'))
        extracted_data = body.get('extracted_data', {})

        print("=" * 80)
        print("EXTRACTED DATA SUMMARY:")
        print("=" * 80)
        print(f"Resource: {extracted_data.get('resource_name')}")
        print(f"Date Range: {extracted_data.get('date_range')}")
        print(f"Daily Totals: {extracted_data.get('daily_totals')}")
        print(f"Weekly Total: {extracted_data.get('weekly_total')}")
        print()

        # Show projects and hours
        print("PROJECTS AND HOURS:")
        print("-" * 80)
        for project in extracted_data.get('projects', []):
            print(f"\n{project.get('project_name')} ({project.get('project_code')})")
            day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            hours_by_day = project.get('hours_by_day', [])
            for i, day_data in enumerate(hours_by_day):
                hours = day_data.get('hours', '0')
                print(f"  {day_names[i]}: {hours}")

        print()
        print("=" * 80)
        print("VALIDATION:")
        print("=" * 80)

        # Check if Monday (Aug 25) has 0 hours
        daily_totals = extracted_data.get('daily_totals', [])
        if len(daily_totals) > 0:
            monday_hours = daily_totals[0]
            if monday_hours == 0:
                print("✅ SUCCESS: Monday Aug 25 (bank holiday) correctly has 0 hours")
            else:
                print(f"❌ FAILED: Monday Aug 25 (bank holiday) has {monday_hours} hours instead of 0")

        # Check all projects have 0 hours on Monday
        all_correct = True
        for project in extracted_data.get('projects', []):
            hours_by_day = project.get('hours_by_day', [])
            if len(hours_by_day) > 0:
                monday_hours = float(hours_by_day[0].get('hours', '0'))
                if monday_hours != 0:
                    print(f"❌ FAILED: {project.get('project_name')} has {monday_hours} hours on Monday (should be 0)")
                    all_correct = False

        if all_correct:
            print("✅ All projects correctly have 0 hours on Monday Aug 25 (bank holiday)")

    else:
        print(f"❌ Lambda invocation failed with status: {response_payload.get('statusCode')}")
        print(f"Error: {response_payload.get('body')}")


if __name__ == "__main__":
    print("=" * 80)
    print("BANK HOLIDAY DETECTION TEST")
    print("=" * 80)
    print()
    print("This test will reprocess the timesheet for the week of Aug 25-31, 2025")
    print("Aug 25, 2025 (Monday) is a UK Summer bank holiday")
    print("The system should automatically set hours to 0 for this day")
    print()

    try:
        invoke_lambda_for_image(TEST_IMAGE)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
