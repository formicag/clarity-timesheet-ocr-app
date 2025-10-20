#!/usr/bin/env python3
"""
Local test script for timesheet OCR.
Tests the OCR pipeline using Claude API directly (not Lambda).
"""
import sys
import os
import json
import base64
import boto3
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from prompt import get_ocr_prompt
from parsing import parse_timesheet_json, convert_to_csv, create_audit_json, calculate_cost_estimate
import time


def test_ocr_locally(image_path: str, output_dir: str = 'test-output'):
    """
    Test OCR locally using Bedrock directly.

    Args:
        image_path: Path to timesheet image
        output_dir: Directory for output files
    """
    print(f"\n{'='*60}")
    print("TIMESHEET OCR - LOCAL TEST")
    print(f"{'='*60}\n")

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Read image
    print(f"Reading image: {image_path}")
    with open(image_path, 'rb') as f:
        image_bytes = f.read()

    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    print(f"Image size: {len(image_bytes):,} bytes")

    # Determine media type
    if image_path.lower().endswith('.png'):
        media_type = 'image/png'
    elif image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
        media_type = 'image/jpeg'
    else:
        media_type = 'image/png'

    print(f"Media type: {media_type}")

    # Get prompt
    prompt = get_ocr_prompt()
    print(f"\nPrompt length: {len(prompt)} characters")

    # Call Claude via Bedrock
    print("\nCalling Claude Sonnet 4.5 on Bedrock...")
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

    model_id = 'us.anthropic.claude-sonnet-4-5-v1:0'

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0,
        "messages": [
            {
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
            }
        ]
    }

    start_time = time.time()

    try:
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )

        response_body = json.loads(response['body'].read())
        processing_time = time.time() - start_time

        print(f"✓ OCR completed in {processing_time:.2f} seconds")

        # Extract response
        extracted_text = response_body['content'][0]['text']
        input_tokens = response_body['usage']['input_tokens']
        output_tokens = response_body['usage']['output_tokens']

        print(f"\nToken usage:")
        print(f"  Input tokens:  {input_tokens:,}")
        print(f"  Output tokens: {output_tokens:,}")

        # Calculate cost
        cost_info = calculate_cost_estimate(input_tokens, output_tokens, model_id)
        print(f"\nEstimated cost: ${cost_info['total_cost_usd']:.6f}")
        print(f"  Input:  ${cost_info['input_cost_usd']:.6f}")
        print(f"  Output: ${cost_info['output_cost_usd']:.6f}")

        # Parse JSON response
        print("\nParsing extracted data...")
        timesheet_data = parse_timesheet_json(extracted_text)

        print(f"\n{'='*60}")
        print("EXTRACTED DATA")
        print(f"{'='*60}")
        print(f"Resource Name: {timesheet_data.get('resource_name')}")
        print(f"Date Range:    {timesheet_data.get('date_range')}")
        print(f"Projects:      {len(timesheet_data.get('projects', []))}")

        for i, project in enumerate(timesheet_data.get('projects', []), 1):
            total_hours = sum(float(day.get('hours', 0)) for day in project.get('hours_by_day', []))
            print(f"\n  {i}. {project.get('project_name')}")
            print(f"     Code: {project.get('project_code')}")
            print(f"     Total Hours: {total_hours}")

        # Convert to CSV
        print(f"\n{'='*60}")
        print("GENERATING CSV")
        print(f"{'='*60}")
        csv_output = convert_to_csv(timesheet_data)

        # Save CSV
        csv_filename = output_path / f"{Path(image_path).stem}_output.csv"
        with open(csv_filename, 'w') as f:
            f.write(csv_output)
        print(f"✓ CSV saved: {csv_filename}")

        # Display first 10 lines
        lines = csv_output.split('\n')
        print("\nFirst 10 rows:")
        for line in lines[:11]:
            print(f"  {line}")

        if len(lines) > 11:
            print(f"  ... ({len(lines)-11} more rows)")

        # Save audit JSON
        audit_json = create_audit_json(
            timesheet_data,
            image_path,
            csv_output,
            processing_time,
            model_id
        )

        audit_filename = output_path / f"{Path(image_path).stem}_audit.json"
        with open(audit_filename, 'w') as f:
            f.write(audit_json)
        print(f"✓ Audit JSON saved: {audit_filename}")

        # Save raw response
        raw_filename = output_path / f"{Path(image_path).stem}_raw.json"
        with open(raw_filename, 'w') as f:
            json.dump(timesheet_data, f, indent=2)
        print(f"✓ Raw data saved: {raw_filename}")

        print(f"\n{'='*60}")
        print("TEST COMPLETED SUCCESSFULLY")
        print(f"{'='*60}\n")

        return True

    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_local.py <image_path>")
        print("\nExample:")
        print("  python test_local.py 2025-10-15_20h43_56.png")
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)

    success = test_ocr_locally(image_path)
    sys.exit(0 if success else 1)
