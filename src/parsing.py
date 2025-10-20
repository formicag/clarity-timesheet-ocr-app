"""
Parsing functions for converting extracted JSON data to CSV format.
"""
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List
from io import StringIO

from utils import (
    parse_date_range,
    generate_week_dates,
    normalize_project_code,
    parse_hours,
    format_date_for_csv,
    validate_timesheet_data
)


def parse_timesheet_json(json_str: str) -> dict:
    """
    Parse JSON string from Claude response.

    Args:
        json_str: JSON string containing timesheet data

    Returns:
        Dictionary with parsed timesheet data

    Raises:
        ValueError: If JSON is invalid or malformed
    """
    try:
        # Try to extract JSON if wrapped in markdown code blocks
        if '```json' in json_str:
            start = json_str.find('```json') + 7
            end = json_str.find('```', start)
            json_str = json_str[start:end].strip()
        elif '```' in json_str:
            start = json_str.find('```') + 3
            end = json_str.find('```', start)
            json_str = json_str[start:end].strip()

        data = json.loads(json_str)
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response from Claude: {str(e)}")


def convert_to_csv(timesheet_data: dict) -> str:
    """
    Convert timesheet data to CSV format.

    Args:
        timesheet_data: Dictionary containing parsed timesheet data

    Returns:
        CSV string with format: Resource Name, Date, Project Name, Project Code, Hours

    Raises:
        ValueError: If data is invalid or missing required fields
    """
    # Validate data first
    warnings = validate_timesheet_data(timesheet_data)
    if warnings:
        print(f"WARNING: Data validation issues: {', '.join(warnings)}")

    # Extract basic info
    resource_name = timesheet_data.get('resource_name', 'Unknown')
    date_range_str = timesheet_data.get('date_range', '')

    # Parse date range to get individual dates
    try:
        start_date, end_date = parse_date_range(date_range_str)
        week_dates = generate_week_dates(start_date, end_date)
    except ValueError as e:
        raise ValueError(f"Error processing date range: {str(e)}")

    # Build rows for CSV
    rows = []

    for project in timesheet_data.get('projects', []):
        project_name = project.get('project_name', '')
        project_code = project.get('project_code', '')

        # Normalize project code to fix OCR errors
        project_code = normalize_project_code(project_code)

        hours_by_day = project.get('hours_by_day', [])

        # Ensure we have exactly 7 days
        if len(hours_by_day) != 7:
            print(f"WARNING: Project '{project_name}' has {len(hours_by_day)} days instead of 7")

        # Create a row for each day
        for i, day_data in enumerate(hours_by_day):
            if i >= len(week_dates):
                print(f"WARNING: More days than expected for project '{project_name}'")
                break

            date_obj = week_dates[i]
            hours_str = day_data.get('hours', '0')
            hours = parse_hours(hours_str)

            row = {
                'Resource Name': resource_name,
                'Date': format_date_for_csv(date_obj),
                'Project Name': project_name,
                'Project Code': project_code,
                'Hours': hours
            }
            rows.append(row)

    # Convert to DataFrame and then to CSV
    df = pd.DataFrame(rows)

    # Ensure proper column order
    df = df[['Resource Name', 'Date', 'Project Name', 'Project Code', 'Hours']]

    # Convert to CSV string
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_str = csv_buffer.getvalue()

    return csv_str


def create_audit_json(
    timesheet_data: dict,
    image_key: str,
    csv_output: str,
    processing_time: float,
    model_id: str
) -> str:
    """
    Create audit JSON for traceability.

    Args:
        timesheet_data: Original extracted data
        image_key: S3 key of source image
        csv_output: Generated CSV content
        processing_time: Time taken to process (seconds)
        model_id: Bedrock model ID used

    Returns:
        JSON string with audit information
    """
    audit_data = {
        'source_image': image_key,
        'processing_timestamp': datetime.utcnow().isoformat() + 'Z',
        'processing_time_seconds': round(processing_time, 2),
        'model_id': model_id,
        'extracted_data': timesheet_data,
        'csv_rows_generated': len(csv_output.split('\n')) - 2,  # Subtract header and trailing newline
        'validation_warnings': validate_timesheet_data(timesheet_data)
    }

    return json.dumps(audit_data, indent=2)


def generate_output_filename(timesheet_data: dict, extension: str = 'csv') -> str:
    """
    Generate output filename based on timesheet data.

    Args:
        timesheet_data: Dictionary containing parsed timesheet data
        extension: File extension (default: 'csv')

    Returns:
        Filename in format: YYYY-MM-DD_ResourceName_timesheet.ext
    """
    resource_name = timesheet_data.get('resource_name', 'Unknown')
    date_range_str = timesheet_data.get('date_range', '')

    # Clean up resource name for filename
    resource_name_clean = resource_name.replace(' ', '_')
    resource_name_clean = ''.join(c for c in resource_name_clean if c.isalnum() or c == '_')

    # Get start date for filename
    try:
        start_date, _ = parse_date_range(date_range_str)
        date_str = start_date.strftime('%Y-%m-%d')
    except:
        date_str = datetime.now().strftime('%Y-%m-%d')

    return f"{date_str}_{resource_name_clean}_timesheet.{extension}"


def calculate_cost_estimate(input_tokens: int, output_tokens: int, model_id: str) -> dict:
    """
    Calculate estimated cost for Bedrock API call.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model_id: Bedrock model ID

    Returns:
        Dictionary with cost breakdown
    """
    # Pricing as of January 2025 (per 1K tokens)
    # Claude Sonnet 4.5: $3.00/1M input, $15.00/1M output
    if 'sonnet-4' in model_id.lower():
        input_cost_per_1k = 0.003
        output_cost_per_1k = 0.015
    # Claude Opus 4: $15.00/1M input, $75.00/1M output
    elif 'opus-4' in model_id.lower():
        input_cost_per_1k = 0.015
        output_cost_per_1k = 0.075
    else:
        # Default to Sonnet pricing
        input_cost_per_1k = 0.003
        output_cost_per_1k = 0.015

    input_cost = (input_tokens / 1000) * input_cost_per_1k
    output_cost = (output_tokens / 1000) * output_cost_per_1k
    total_cost = input_cost + output_cost

    return {
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'input_cost_usd': round(input_cost, 6),
        'output_cost_usd': round(output_cost, 6),
        'total_cost_usd': round(total_cost, 6),
        'model_id': model_id
    }
