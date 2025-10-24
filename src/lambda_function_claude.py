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
from validation import validate_timesheet_data, format_validation_report
from team_manager import TeamManager


# Environment variables
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', '')
# Use Claude 3.5 Sonnet v2 with inference profile for best OCR accuracy
MODEL_ID = os.environ.get('MODEL_ID', 'us.anthropic.claude-3-5-sonnet-20241022-v2:0')
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

        # Normalize resource name using team roster aliases
        resource_name = timesheet_data.get('resource_name', 'Unknown')
        try:
            team_mgr = TeamManager()
            normalized_name, confidence, match_type = team_mgr.normalize_name(resource_name)
            if match_type == 'alias':
                print(f"📝 Name normalization: '{resource_name}' → '{normalized_name}' (alias)")
                timesheet_data['resource_name'] = normalized_name
            elif match_type == 'fuzzy' and confidence >= 0.85:
                print(f"📝 Name normalization: '{resource_name}' → '{normalized_name}' (fuzzy match {confidence:.2f})")
                timesheet_data['resource_name'] = normalized_name
        except Exception as e:
            print(f"⚠️  Name normalization failed: {e}, using original name")

        print(f"Extracted data for: {timesheet_data.get('resource_name', 'Unknown')}")
        print(f"Date range: {timesheet_data.get('date_range', 'Unknown')}")
        print(f"Projects found: {len(timesheet_data.get('projects', []))}")

        # Log detailed extraction for debugging
        print("=" * 80)
        print("DETAILED EXTRACTION LOG")
        print("=" * 80)
        for i, project in enumerate(timesheet_data.get('projects', []), 1):
            print(f"\nProject {i}: {project.get('project_name', 'Unknown')}")
            print(f"  Code: {project.get('project_code', 'Unknown')}")
            print(f"  Hours by day:")
            for day_idx, day_data in enumerate(project.get('hours_by_day', [])):
                day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                hours = day_data.get('hours', '0')
                print(f"    {day_names[day_idx]}: {hours}h")
        print("=" * 80)

        # Validate extracted data
        print("Validating extracted data...")
        validation_result = validate_timesheet_data(timesheet_data)
        print(format_validation_report(validation_result))

        if not validation_result['valid']:
            # Log validation failure but continue processing
            print("⚠️  WARNING: Validation failed but continuing with storage")
            print(f"⚠️  Errors: {'; '.join(validation_result['errors'])}")

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
                'validation': {
                    'valid': validation_result['valid'],
                    'errors': validation_result['errors'],
                    'warnings': validation_result['warnings'],
                    'summary': validation_result['summary']
                },
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
    Implements exponential backoff for throttling errors.

    Args:
        image_base64: Base64 encoded image
        media_type: Image media type (image/png, image/jpeg)

    Returns:
        Claude response dictionary

    Raises:
        Exception: If Bedrock call fails after all retries
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

    # Exponential backoff configuration
    max_retries = 5
    base_delay = 2  # Start with 2 seconds
    max_delay = 60  # Cap at 60 seconds

    for attempt in range(max_retries):
        try:
            response = bedrock_runtime.invoke_model(
                modelId=MODEL_ID,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )

            # Parse response
            response_body = json.loads(response['body'].read())

            if attempt > 0:
                print(f"✓ Succeeded after {attempt} retries")

            return response_body

        except Exception as e:
            error_str = str(e)

            # Check if it's a throttling error
            if 'ThrottlingException' in error_str or 'Too many requests' in error_str:
                if attempt < max_retries - 1:
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    print(f"⚠️  Throttled (attempt {attempt + 1}/{max_retries}), waiting {delay}s before retry...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"❌ Failed after {max_retries} retries due to throttling")
                    raise
            else:
                # Non-throttling error, don't retry
                print(f"Error calling Bedrock: {error_str}")
                raise

    # Should never reach here
    raise Exception("Max retries exceeded")


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
