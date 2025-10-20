"""
AWS Lambda function for timesheet OCR processing.
"""
import json
import os
import boto3
import base64
import time
from typing import Dict, Any

from prompt import get_ocr_prompt
from parsing import (
    parse_timesheet_json,
    calculate_cost_estimate
)
from dynamodb_handler import store_timesheet_entries
from duplicate_detection import check_for_existing_entries
from utils import parse_date_range


# Environment variables
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', '')
MODEL_ID = os.environ.get('MODEL_ID', 'us.anthropic.claude-sonnet-4-5-v1:0')
MAX_TOKENS = int(os.environ.get('MAX_TOKENS', '4096'))
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

# AWS clients
s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for S3 triggered OCR processing.

    Args:
        event: S3 event containing bucket and object key
        context: Lambda context

    Returns:
        Response dictionary with status and details
    """
    start_time = time.time()

    try:
        # Extract S3 bucket and key from event
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        print(f"Processing image: s3://{bucket}/{key}")

        # Download image from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        image_bytes = response['Body'].read()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Determine image format
        if key.lower().endswith('.png'):
            media_type = 'image/png'
        elif key.lower().endswith('.jpg') or key.lower().endswith('.jpeg'):
            media_type = 'image/jpeg'
        else:
            media_type = 'image/png'  # Default

        print(f"Image size: {len(image_bytes)} bytes, format: {media_type}")

        # Call Claude for OCR
        print("Calling Claude Bedrock for OCR...")
        ocr_response = call_claude_vision(image_base64, media_type)

        # Parse response
        print("Parsing Claude response...")
        extracted_text = ocr_response['content'][0]['text']
        timesheet_data = parse_timesheet_json(extracted_text)

        print(f"Extracted data for: {timesheet_data.get('resource_name', 'Unknown')}")
        print(f"Date range: {timesheet_data.get('date_range', 'Unknown')}")
        print(f"Projects found: {len(timesheet_data.get('projects', []))}")

        # Check for duplicate entries
        resource_name = timesheet_data.get('resource_name', 'Unknown')
        date_range_str = timesheet_data.get('date_range', '')
        project_codes = [p.get('project_code', '') for p in timesheet_data.get('projects', [])]

        try:
            start_date, end_date = parse_date_range(date_range_str)
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')

            duplicate_check = check_for_existing_entries(
                resource_name=resource_name,
                start_date=start_date_str,
                end_date=end_date_str,
                project_codes=project_codes,
                table_name=DYNAMODB_TABLE
            )

            if duplicate_check['exists']:
                print(f"⚠️  Duplicate detection: {duplicate_check['message']}")
                print(f"   Previous sources: {', '.join(duplicate_check['source_images'][:3])}")
                print(f"   Will overwrite {duplicate_check['entry_count']} existing entries")
            else:
                print(f"✓ No duplicates found - new entries will be created")

        except Exception as e:
            print(f"Warning: Duplicate check failed: {str(e)}")
            # Continue processing even if duplicate check fails

        # Calculate cost
        input_tokens = ocr_response['usage']['input_tokens']
        output_tokens = ocr_response['usage']['output_tokens']
        cost_info = calculate_cost_estimate(input_tokens, output_tokens, MODEL_ID)

        print(f"Cost estimate: ${cost_info['total_cost_usd']:.6f} "
              f"({input_tokens} input + {output_tokens} output tokens)")

        # Store in DynamoDB
        processing_time = time.time() - start_time
        print(f"Storing data in DynamoDB table: {DYNAMODB_TABLE}...")
        db_result = store_timesheet_entries(
            timesheet_data=timesheet_data,
            image_key=key,
            processing_time=processing_time,
            model_id=MODEL_ID,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_estimate=cost_info['total_cost_usd'],
            table_name=DYNAMODB_TABLE
        )
        print(f"Stored {db_result['entries_stored']} entries in DynamoDB")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Timesheet processed successfully',
                'input_image': f"s3://{bucket}/{key}",
                'dynamodb_table': DYNAMODB_TABLE,
                'entries_stored': db_result['entries_stored'],
                'resource_name': timesheet_data.get('resource_name'),
                'date_range': timesheet_data.get('date_range'),
                'projects_count': len(timesheet_data.get('projects', [])),
                'processing_time_seconds': round(processing_time, 2),
                'cost_estimate_usd': cost_info['total_cost_usd'],
                'duplicate_info': {
                    'was_duplicate': duplicate_check.get('exists', False),
                    'overwritten_entries': duplicate_check.get('entry_count', 0) if duplicate_check.get('exists') else 0
                } if 'duplicate_check' in locals() else {'was_duplicate': False, 'overwritten_entries': 0}
            })
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Error processing timesheet',
                'error': str(e)
            })
        }


def call_claude_vision(image_base64: str, media_type: str) -> Dict[str, Any]:
    """
    Call Claude on Bedrock with vision capabilities.

    Args:
        image_base64: Base64 encoded image
        media_type: Image media type (image/png, image/jpeg)

    Returns:
        Claude response dictionary

    Raises:
        Exception: If Bedrock call fails
    """
    prompt = get_ocr_prompt()

    # Prepare request body for Claude 3/4
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "temperature": 0,  # Deterministic results
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

    # Call Bedrock
    try:
        response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )

        # Parse response
        response_body = json.loads(response['body'].read())
        return response_body

    except Exception as e:
        print(f"Error calling Bedrock: {str(e)}")
        raise


# For local testing
if __name__ == "__main__":
    # Test event
    test_event = {
        "Records": [
            {
                "s3": {
                    "bucket": {
                        "name": "test-bucket"
                    },
                    "object": {
                        "key": "test-timesheet.png"
                    }
                }
            }
        ]
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
