"""
AWS Lambda function for timesheet OCR processing using Textract for table extraction.
"""
import json
import os
import boto3
import time
import re
import base64
import random
from typing import Dict, Any
from decimal import Decimal

from dynamodb_handler import store_timesheet_entries, store_rejected_timesheet
from duplicate_detection import check_for_existing_entries
from utils import parse_date_range
from validation import validate_timesheet_data, format_validation_report
from team_manager import TeamManager
from parsing import calculate_cost_estimate

# Environment variables
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', '')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

# AWS clients
s3_client = boto3.client('s3')
textract_client = boto3.client('textract', region_name='us-east-1')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')


def get_text_from_cell(cell_block, blocks_map):
    """Get text from a Textract cell."""
    text = ''
    if 'Relationships' in cell_block:
        for relationship in cell_block['Relationships']:
            if relationship.get('Type') == 'CHILD':
                for child_id in relationship['Ids']:
                    child_block = blocks_map.get(child_id)
                    if child_block and child_block['BlockType'] == 'WORD':
                        text += child_block['Text'] + ' '
    return text.strip()


def extract_metadata_with_claude(bucket, key):
    """Use Claude to extract resource name and date range from the image with retry logic."""
    # Download image
    response = s3_client.get_object(Bucket=bucket, Key=key)
    image_bytes = response['Body'].read()

    # Determine image format
    if key.lower().endswith('.png'):
        media_type = 'image/png'
    elif key.lower().endswith('.jpg') or key.lower().endswith('.jpeg'):
        media_type = 'image/jpeg'
    else:
        media_type = 'image/png'

    # Simple prompt for metadata extraction
    prompt = """Look at this timesheet image and extract ONLY the following information:
1. Resource name - This is the PERSON'S NAME (not their job title). Look for a proper name like "Matthew Garretty", "John Smith", etc. at the top of the timesheet. DO NOT use job titles like "Solution Designer", "Developer", etc.
2. Date range (format: "MMM DD YYYY - MMM DD YYYY", e.g., "Oct 6 2025 - Oct 12 2025")
3. Status (look for "Status: Posted" or "Status: Submitted" etc.)

Return ONLY this JSON (no explanations):
{
  "resource_name": "Full Name",
  "date_range": "MMM DD YYYY - MMM DD YYYY",
  "status": "Posted"
}

IMPORTANT: The resource_name must be a person's actual name (first name and last name), not a job title or role."""

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
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
                            "data": base64.b64encode(image_bytes).decode('utf-8')
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

    # Retry logic with exponential backoff for throttling
    max_retries = 5
    base_delay = 2

    for attempt in range(max_retries):
        try:
            response = bedrock_runtime.invoke_model(
                modelId='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )

            response_body = json.loads(response['body'].read())
            text = response_body['content'][0]['text']

            # Parse JSON
            if '```json' in text:
                start = text.find('```json') + 7
                end = text.find('```', start)
                text = text[start:end].strip()

            metadata = json.loads(text)
            return metadata, response_body['usage']

        except Exception as e:
            error_str = str(e)
            if 'ThrottlingException' in error_str or 'Too many requests' in error_str:
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Bedrock throttled, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    print(f"Bedrock throttled after {max_retries} attempts, giving up")
                    raise
            else:
                # Non-throttling error, don't retry
                raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for S3 triggered OCR processing using Textract.
    """
    start_time = time.time()

    try:
        # Extract S3 bucket and key from event
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        print(f"Processing image: s3://{bucket}/{key}")

        # Step 1: Extract metadata (name, dates, status) with Claude
        print("Extracting metadata with Claude...")
        metadata, claude_usage = extract_metadata_with_claude(bucket, key)
        resource_name = metadata['resource_name']
        date_range = metadata['date_range']
        status = metadata.get('status', 'Unknown').strip()

        print(f"Resource: {resource_name}")
        print(f"Date range: {date_range}")
        print(f"Status: {status}")

        # Validate status is "Posted"
        if status.lower() != 'posted':
            print(f"❌ REJECTED: Timesheet status is '{status}', not 'Posted'")

            # Store rejection record in DynamoDB
            processing_time = time.time() - start_time
            rejection_result = store_rejected_timesheet(
                resource_name=resource_name,
                date_range=date_range,
                status=status,
                image_key=key,
                processing_time=processing_time,
                reason=f"Status is '{status}' instead of 'Posted'",
                table_name=DYNAMODB_TABLE
            )

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'Timesheet rejected: Status is {status}, not Posted',
                    'input_image': f"s3://{bucket}/{key}",
                    'resource_name': resource_name,
                    'date_range': date_range,
                    'status': status,
                    'rejected': True,
                    'reason': f"Status is '{status}' instead of 'Posted'"
                })
            }

        # Step 2: Extract table structure with Textract
        print("Calling Textract for table extraction...")
        textract_response = textract_client.analyze_document(
            Document={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            },
            FeatureTypes=['TABLES']
        )

        # Build blocks map
        blocks_map = {block['Id']: block for block in textract_response['Blocks']}

        # Extract tables
        tables = [block for block in textract_response['Blocks'] if block['BlockType'] == 'TABLE']

        if not tables:
            raise ValueError("No tables found in image")

        table = tables[0]
        cells = []

        if 'Relationships' in table:
            for relationship in table['Relationships']:
                if relationship.get('Type') == 'CHILD':
                    for cell_id in relationship['Ids']:
                        cell = blocks_map.get(cell_id)
                        if cell and cell['BlockType'] == 'CELL':
                            cells.append(cell)

        # Organize cells by row and column
        table_data = {}
        for cell in cells:
            row_index = cell.get('RowIndex', 0)
            col_index = cell.get('ColumnIndex', 0)
            text = get_text_from_cell(cell, blocks_map)

            if row_index not in table_data:
                table_data[row_index] = {}
            table_data[row_index][col_index] = text

        # Parse header row to identify day columns and extract daily totals
        # Search for header row (might not always be row 1 due to UI elements)
        header = {}
        header_row_idx = None
        for row_idx in range(1, min(5, len(table_data) + 1)):  # Check first 5 rows
            candidate = table_data.get(row_idx, {})
            # Header row contains "Mon." or "Monday"
            if any('Mon.' in str(cell) or 'Monday' in str(cell) for cell in candidate.values()):
                header = candidate
                header_row_idx = row_idx
                print(f"Found header row at index {row_idx}")
                break

        day_columns = {}
        daily_totals = [0.0] * 7
        weekly_total = 0.0

        print(f"DEBUG: Header row content: {header}")

        for col_idx, text in header.items():
            # Header cells contain: "Mon. 6 7.50" where 7.50 is the daily total
            if 'Mon.' in text:
                day_columns[col_idx] = 0
                # Extract daily total (last number in the cell)
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[0] = float(parts[-1])
                    except ValueError:
                        pass
            elif 'Tue.' in text:
                day_columns[col_idx] = 1
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[1] = float(parts[-1])
                    except ValueError:
                        pass
            elif 'Wed.' in text:
                day_columns[col_idx] = 2
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[2] = float(parts[-1])
                    except ValueError:
                        pass
            elif 'Thu.' in text:
                day_columns[col_idx] = 3
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[3] = float(parts[-1])
                    except ValueError:
                        pass
            elif 'Fri.' in text:
                day_columns[col_idx] = 4
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[4] = float(parts[-1])
                    except ValueError:
                        pass
            elif 'Sat.' in text:
                day_columns[col_idx] = 5
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[5] = float(parts[-1])
                    except ValueError:
                        pass
            elif 'Sun.' in text:
                day_columns[col_idx] = 6
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        daily_totals[6] = float(parts[-1])
                    except ValueError:
                        pass
            elif 'Total' in text and 'Posted' not in text:
                # Extract weekly total from "Total 22.50"
                parts = text.split()
                if len(parts) >= 2:
                    try:
                        weekly_total = float(parts[-1])
                    except ValueError:
                        pass

        print(f"Identified {len(day_columns)} day columns")
        print(f"Daily totals: {daily_totals}")
        print(f"Weekly total: {weekly_total}")

        # Extract projects and hours
        projects = {}
        current_project = None
        project_code_pattern = re.compile(r'\((PJ\d+|DATA\d+|REAG\d+|HCST\d+|NTC5\d+)\)')

        for row_idx in sorted(table_data.keys()):
            if header_row_idx and row_idx == header_row_idx:  # Skip header row
                continue

            row = table_data[row_idx]
            first_cell = row.get(1, '').strip()

            # Check if this is a parent project row
            match = project_code_pattern.search(first_cell)
            if match:
                current_project = match.group(1)
                projects[current_project] = {
                    'project_name': first_cell,
                    'project_code': current_project,
                    'hours_by_day': [
                        {"day": "Monday", "hours": "0"},
                        {"day": "Tuesday", "hours": "0"},
                        {"day": "Wednesday", "hours": "0"},
                        {"day": "Thursday", "hours": "0"},
                        {"day": "Friday", "hours": "0"},
                        {"day": "Saturday", "hours": "0"},
                        {"day": "Sunday", "hours": "0"}
                    ]
                }
                print(f"Found project: {current_project}")

            # If we have a current project, look for hours in this row
            if current_project:
                for col_idx, day_idx in day_columns.items():
                    cell_text = row.get(col_idx, '').strip()
                    if cell_text:
                        try:
                            hours = float(cell_text.split()[0])
                            if hours > 0:
                                # Accumulate hours instead of overwriting (for multiple child tasks)
                                current_hours = float(projects[current_project]['hours_by_day'][day_idx]['hours'])
                                new_total = current_hours + hours
                                projects[current_project]['hours_by_day'][day_idx]['hours'] = str(new_total)
                                print(f"  {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day_idx]}: +{hours}h (total: {new_total}h)")
                        except (ValueError, IndexError):
                            pass

        # Build timesheet_data structure
        timesheet_data = {
            'resource_name': resource_name,
            'date_range': date_range,
            'is_zero_hour_timesheet': False,
            'zero_hour_reason': None,
            'projects': list(projects.values()),
            'daily_totals': daily_totals,
            'weekly_total': weekly_total
        }

        print(f"Extracted {len(projects)} projects")

        # Normalize resource name using team roster
        try:
            team_mgr = TeamManager()
            normalized_name, confidence, match_type = team_mgr.normalize_name(resource_name)
            if match_type in ['alias', 'fuzzy'] and confidence >= 0.85:
                print(f"📝 Name normalization: '{resource_name}' → '{normalized_name}'")
                timesheet_data['resource_name'] = normalized_name
        except Exception as e:
            print(f"⚠️  Name normalization failed: {e}")

        # Validate extracted data
        print("Validating extracted data...")
        validation_result = validate_timesheet_data(timesheet_data)
        print(format_validation_report(validation_result))

        # Calculate cost (Textract + Claude metadata)
        textract_pages = 1
        textract_cost = textract_pages * 0.0015  # $0.0015 per page for table analysis
        claude_cost = calculate_cost_estimate(
            claude_usage['input_tokens'],
            claude_usage['output_tokens'],
            'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
        )['total_cost_usd']
        total_cost = textract_cost + claude_cost

        print(f"Cost estimate: ${total_cost:.6f} (Textract: ${textract_cost:.6f}, Claude: ${claude_cost:.6f})")

        # Store in DynamoDB
        processing_time = time.time() - start_time
        print(f"Storing data in DynamoDB table: {DYNAMODB_TABLE}...")
        db_result = store_timesheet_entries(
            timesheet_data=timesheet_data,
            image_key=key,
            processing_time=processing_time,
            model_id='textract+claude',
            input_tokens=claude_usage['input_tokens'],
            output_tokens=claude_usage['output_tokens'],
            cost_estimate=total_cost,
            table_name=DYNAMODB_TABLE
        )
        print(f"Stored {db_result['entries_stored']} entries in DynamoDB")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Timesheet processed successfully (Textract)',
                'input_image': f"s3://{bucket}/{key}",
                'dynamodb_table': DYNAMODB_TABLE,
                'entries_stored': db_result['entries_stored'],
                'resource_name': timesheet_data['resource_name'],
                'date_range': timesheet_data['date_range'],
                'projects_count': len(timesheet_data['projects']),
                'processing_time_seconds': round(processing_time, 2),
                'cost_estimate_usd': total_cost,
                'validation': {
                    'valid': validation_result['valid'],
                    'errors': validation_result['errors'],
                    'warnings': validation_result['warnings'],
                    'summary': validation_result['summary']
                }
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
