#!/usr/bin/env python3
"""
Test both failing images with the winning model.
"""
import sys
import os
import boto3
import base64
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from prompt import get_ocr_prompt
from parsing import parse_timesheet_json
from validation import validate_timesheet_data, format_validation_report


WINNING_MODEL = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'


def test_image(image_path: str, image_name: str):
    """Test OCR on an image"""
    print(f"\n{'='*80}")
    print(f"Testing: {image_name}")
    print(f"{'='*80}\n")

    with open(image_path, 'rb') as f:
        image_bytes = f.read()

    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    prompt = get_ocr_prompt(enable_grid_mode=True)

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

    response = bedrock.invoke_model(
        modelId=WINNING_MODEL,
        body=json.dumps(request_body),
        contentType='application/json',
        accept='application/json'
    )

    response_body = json.loads(response['body'].read())
    extracted_text = response_body['content'][0]['text']

    # Parse and validate
    timesheet_data = parse_timesheet_json(extracted_text)
    validation_result = validate_timesheet_data(timesheet_data)

    print(f"Resource: {timesheet_data.get('resource_name')}")
    print(f"Date Range: {timesheet_data.get('date_range')}")
    print(f"Projects: {len(timesheet_data.get('projects', []))}")
    print()

    print(format_validation_report(validation_result))

    return validation_result['valid']


def main():
    print("=" * 80)
    print("FINAL VALIDATION TEST - Both Failing Images")
    print(f"Model: Claude 3.5 Sonnet v2 (with Grid Detection)")
    print("=" * 80)

    results = []
    results.append(test_image('/tmp/test_image_1.png', 'Image 1 (2025-10-20_16h01_43.png)'))
    results.append(test_image('/tmp/test_image_2.png', 'Image 2 (2025-10-20_16h01_38.png)'))

    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    print(f"Image 1: {'✅ PASSED' if results[0] else '❌ FAILED'}")
    print(f"Image 2: {'✅ PASSED' if results[1] else '❌ FAILED'}")
    print(f"\nSuccess Rate: {sum(results)}/2 ({sum(results)/2*100:.0f}%)")
    print("=" * 80)


if __name__ == '__main__':
    main()
