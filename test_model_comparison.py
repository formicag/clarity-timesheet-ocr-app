#!/usr/bin/env python3
"""
Test multiple Claude models to find the best one for OCR accuracy.
"""
import sys
import os
import boto3
import base64
import json
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from prompt import get_ocr_prompt
from parsing import parse_timesheet_json
from validation import validate_timesheet_data, format_validation_report


# Models to test (in order of power/cost) - Using inference profiles
MODELS = [
    {
        'id': 'us.anthropic.claude-3-haiku-20240307-v1:0',
        'name': 'Claude 3 Haiku (Fastest/Cheapest)',
        'cost_per_mtok_in': 0.25,
        'cost_per_mtok_out': 1.25
    },
    {
        'id': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
        'name': 'Claude 3.5 Sonnet v2 (Balanced)',
        'cost_per_mtok_in': 3.00,
        'cost_per_mtok_out': 15.00
    },
    {
        'id': 'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
        'name': 'Claude 3.7 Sonnet (Advanced)',
        'cost_per_mtok_in': 3.00,
        'cost_per_mtok_out': 15.00
    },
    {
        'id': 'us.anthropic.claude-sonnet-4-5-20250929-v1:0',
        'name': 'Claude Sonnet 4.5 (Most Powerful)',
        'cost_per_mtok_in': 3.00,
        'cost_per_mtok_out': 15.00
    },
    {
        'id': 'us.anthropic.claude-opus-4-1-20250805-v1:0',
        'name': 'Claude Opus 4.1 (Highest Intelligence)',
        'cost_per_mtok_in': 15.00,
        'cost_per_mtok_out': 75.00
    }
]


def test_model_on_image(model_info: dict, image_path: str, enable_grid_mode: bool = True):
    """Test a specific model on an image"""
    print(f"\n{'='*80}")
    print(f"Testing: {model_info['name']}")
    print(f"Model ID: {model_info['id']}")
    print(f"Grid Mode: {'ENABLED' if enable_grid_mode else 'DISABLED'}")
    print(f"{'='*80}\n")

    # Read image
    with open(image_path, 'rb') as f:
        image_bytes = f.read()

    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

    # Call Bedrock
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    prompt = get_ocr_prompt(enable_grid_mode=enable_grid_mode)

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

    start_time = time.time()

    try:
        response = bedrock.invoke_model(
            modelId=model_info['id'],
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )

        processing_time = time.time() - start_time

        response_body = json.loads(response['body'].read())
        extracted_text = response_body['content'][0]['text']

        # Calculate cost
        input_tokens = response_body['usage']['input_tokens']
        output_tokens = response_body['usage']['output_tokens']
        cost = (input_tokens * model_info['cost_per_mtok_in'] / 1_000_000 +
                output_tokens * model_info['cost_per_mtok_out'] / 1_000_000)

        # Parse JSON
        timesheet_data = parse_timesheet_json(extracted_text)

        # Validate
        validation_result = validate_timesheet_data(timesheet_data)

        # Print summary
        print(f"⏱️  Processing Time: {processing_time:.2f}s")
        print(f"💰 Cost: ${cost:.6f}")
        print(f"📊 Tokens: {input_tokens} in + {output_tokens} out")
        print(f"✅ Validation: {'PASSED' if validation_result['valid'] else 'FAILED'}")
        print()

        if not validation_result['valid']:
            print("VALIDATION ERRORS:")
            for error in validation_result['errors']:
                print(f"  {error}")
            print()

        if validation_result['warnings']:
            print("WARNINGS:")
            for warning in validation_result['warnings']:
                print(f"  {warning}")
            print()

        return {
            'model': model_info['name'],
            'model_id': model_info['id'],
            'valid': validation_result['valid'],
            'errors': len(validation_result['errors']),
            'warnings': len(validation_result['warnings']),
            'cost': cost,
            'time': processing_time,
            'validation_result': validation_result
        }

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return {
            'model': model_info['name'],
            'model_id': model_info['id'],
            'valid': False,
            'errors': 999,
            'warnings': 0,
            'cost': 0,
            'time': 0,
            'error': str(e)
        }


def main():
    print("=" * 80)
    print("CLAUDE MODEL COMPARISON FOR OCR ACCURACY")
    print("=" * 80)
    print("\nTesting on failing image: /tmp/test_image_1.png")
    print("Expected: Validation should pass with correct column alignment\n")

    results = []

    # Test each model
    for model_info in MODELS:
        result = test_model_on_image(model_info, '/tmp/test_image_1.png', enable_grid_mode=True)
        results.append(result)
        time.sleep(2)  # Rate limiting

    # Print comparison table
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"{'Model':<35} {'Valid':<8} {'Errors':<8} {'Cost':<12} {'Time':<8}")
    print("-" * 80)

    for result in results:
        valid_mark = "✅" if result['valid'] else "❌"
        print(f"{result['model']:<35} {valid_mark:<8} {result['errors']:<8} ${result['cost']:<11.6f} {result['time']:<7.2f}s")

    print("=" * 80)

    # Find best model
    valid_results = [r for r in results if r['valid']]
    if valid_results:
        best = min(valid_results, key=lambda x: (x['cost'], x['time']))
        print(f"\n🏆 WINNER: {best['model']}")
        print(f"   Validation: PASSED")
        print(f"   Cost: ${best['cost']:.6f}")
        print(f"   Time: {best['time']:.2f}s")
    else:
        print("\n⚠️  NO MODEL ACHIEVED VALIDATION - OCR accuracy needs more work")

        # Show which model got closest
        least_errors = min(results, key=lambda x: x['errors'])
        print(f"\nClosest: {least_errors['model']} with {least_errors['errors']} errors")


if __name__ == '__main__':
    main()
