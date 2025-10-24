#!/usr/bin/env python3
"""
Test OCR on a single image to debug zero-hour detection.
"""
import sys
import os
import json
import base64
import boto3

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from prompt import get_ocr_prompt
from parsing import parse_timesheet_json

# Configuration
INPUT_BUCKET = "timesheetocr-input-dev-016164185850"
AWS_REGION = "us-east-1"
IMAGE_KEY = "2025-10-20_15h54_43.png"  # The zero-hour timesheet

def test_single_image():
    print("=" * 80)
    print(f"TESTING OCR ON SINGLE IMAGE: {IMAGE_KEY}")
    print("=" * 80)
    print()

    # Get the prompt
    prompt = get_ocr_prompt()
    print("CHECKING PROMPT:")
    if "PROJECT TIME: 0%" in prompt:
        print("✓ Prompt contains 'PROJECT TIME: 0%' detection")
    else:
        print("✗ WARNING: Prompt MISSING 'PROJECT TIME: 0%' detection!")

    if "is_zero_hour_timesheet" in prompt:
        print("✓ Prompt mentions is_zero_hour_timesheet field")
    else:
        print("✗ WARNING: Prompt does NOT mention is_zero_hour_timesheet!")
    print()

    # Download image from S3
    print(f"Downloading image from S3...")
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    try:
        response = s3_client.get_object(Bucket=INPUT_BUCKET, Key=IMAGE_KEY)
        image_bytes = response['Body'].read()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        print(f"✓ Downloaded {len(image_bytes)} bytes")
    except Exception as e:
        print(f"✗ ERROR downloading image: {e}")
        return

    # Determine media type
    media_type = 'image/png' if IMAGE_KEY.lower().endswith('.png') else 'image/jpeg'
    print(f"Media type: {media_type}")
    print()

    # Call Bedrock for OCR
    print("Calling Bedrock Claude for OCR...")
    bedrock_runtime = boto3.client('bedrock-runtime', region_name=AWS_REGION)

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }]
    }

    try:
        response = bedrock_runtime.invoke_model(
            modelId='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )

        response_body = json.loads(response['body'].read())
        extracted_text = response_body['content'][0]['text']

        print("=" * 80)
        print("FULL CLAUDE RESPONSE:")
        print("=" * 80)
        print(extracted_text)
        print("=" * 80)
        print()

        # Save to file
        output_file = f"/tmp/claude_response_{IMAGE_KEY.replace('/', '_').replace('.png', '.json')}"
        with open(output_file, 'w') as f:
            f.write(extracted_text)
        print(f"✓ Response saved to: {output_file}")
        print()

        # Parse JSON
        print("PARSING JSON...")
        timesheet_data = parse_timesheet_json(extracted_text)

        print("PARSED DATA:")
        print(f"  resource_name: {timesheet_data.get('resource_name')}")
        print(f"  date_range: {timesheet_data.get('date_range')}")
        print(f"  is_zero_hour_timesheet: {timesheet_data.get('is_zero_hour_timesheet')}")
        print(f"  zero_hour_reason: {timesheet_data.get('zero_hour_reason')}")
        print(f"  daily_totals: {timesheet_data.get('daily_totals')}")
        print(f"  weekly_total: {timesheet_data.get('weekly_total')}")
        print(f"  projects: {len(timesheet_data.get('projects', []))} found")

        if timesheet_data.get('projects'):
            print()
            print("PROJECTS:")
            for i, p in enumerate(timesheet_data.get('projects', []), 1):
                print(f"  {i}. {p.get('project_name')} ({p.get('project_code')})")
                total = sum(float(d.get('hours', 0)) for d in p.get('hours_by_day', []))
                print(f"     Total hours: {total}")

        print()
        print("=" * 80)
        if timesheet_data.get('is_zero_hour_timesheet'):
            print("✅ SUCCESS: Zero-hour timesheet correctly detected!")
        else:
            print("❌ FAILURE: Zero-hour timesheet NOT detected!")
            print("   Expected: is_zero_hour_timesheet = true")
            print(f"   Got: is_zero_hour_timesheet = {timesheet_data.get('is_zero_hour_timesheet')}")
        print("=" * 80)

    except Exception as e:
        print(f"✗ ERROR calling Bedrock: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_single_image()
