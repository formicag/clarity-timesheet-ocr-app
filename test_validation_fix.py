#!/usr/bin/env python3
"""
Test validation fixes on the failing images.
"""
import sys
import os
import boto3
import base64
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from prompt import get_ocr_prompt
from parsing import parse_timesheet_json
from validation import validate_timesheet_data, format_validation_report


def test_image(image_path: str):
    """Test OCR and validation on an image"""
    print(f"\n{'='*80}")
    print(f"Testing: {image_path}")
    print(f"{'='*80}\n")

    # Read image
    with open(image_path, 'rb') as f:
        image_bytes = f.read()

    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

    # Call Bedrock
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    prompt = get_ocr_prompt()

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
                        "media_type": "image/png",
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

    print("Calling Bedrock for OCR...")
    response = bedrock.invoke_model(
        modelId='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
        body=json.dumps(request_body),
        contentType='application/json',
        accept='application/json'
    )

    response_body = json.loads(response['body'].read())
    extracted_text = response_body['content'][0]['text']

    print("\n" + "="*80)
    print("CLAUDE RESPONSE:")
    print("="*80)
    print(extracted_text)
    print("="*80 + "\n")

    # Parse JSON
    timesheet_data = parse_timesheet_json(extracted_text)

    print(f"Resource: {timesheet_data.get('resource_name')}")
    print(f"Date Range: {timesheet_data.get('date_range')}")
    print(f"Projects: {len(timesheet_data.get('projects', []))}")
    print(f"Daily Totals: {timesheet_data.get('daily_totals')}")
    print(f"Weekly Total: {timesheet_data.get('weekly_total')}")
    print()

    # Show project details
    for i, project in enumerate(timesheet_data.get('projects', []), 1):
        print(f"Project {i}: {project.get('project_code')} - {project.get('project_name')}")
        hours = [day.get('hours', '0') for day in project.get('hours_by_day', [])]
        total = sum(float(h) for h in hours)
        print(f"  Hours: {hours}")
        print(f"  Total: {total}")

    print()

    # Validate
    validation_result = validate_timesheet_data(timesheet_data)
    print(format_validation_report(validation_result))

    return validation_result


def main():
    test_image('/tmp/test_image_1.png')
    test_image('/tmp/test_image_2.png')


if __name__ == '__main__':
    main()
