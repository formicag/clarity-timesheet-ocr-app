"""
Parsing functions for converting extracted JSON data to CSV format.
"""
import json
from datetime import datetime
from typing import Dict, List
from io import StringIO

# Pandas is optional - only needed for CSV export (not used in Lambda)
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from utils import (
    parse_date_range,
    generate_week_dates,
    is_valid_project_code,
    normalize_project_code,
    parse_hours,
    format_date_for_csv,
    validate_timesheet_data
)
from bank_holidays import is_bank_holiday, get_bank_holiday_name, validate_week_for_bank_holidays
from project_code_correction import (
    correct_project_data,
    validate_project_name_format,
    fix_project_name_format,
    analyze_project_code_quality
)
from team_manager import TeamManager


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

        # Enforce bank holiday rules
        data = enforce_bank_holiday_rules(data)

        # Enforce project code quality rules
        data = enforce_project_code_quality(data)

        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response from Claude: {str(e)}")


def enforce_bank_holiday_rules(data: dict) -> dict:
    """
    Enforce zero hours on UK bank holidays.

    This function ensures that any hours recorded on bank holidays are corrected to 0,
    even if the OCR extracted non-zero values.

    Args:
        data: Dictionary containing parsed timesheet data

    Returns:
        Dictionary with bank holiday hours corrected to 0
    """
    # Skip if zero-hour timesheet
    if data.get('is_zero_hour_timesheet'):
        return data

    # Parse date range to get week dates
    date_range_str = data.get('date_range', '')
    if not date_range_str:
        return data

    try:
        start_date, end_date = parse_date_range(date_range_str)
        week_dates = generate_week_dates(start_date, end_date)
    except ValueError as e:
        print(f"WARNING: Could not parse date range for bank holiday validation: {e}")
        return data

    # Check which days are bank holidays
    bank_holidays_in_week = validate_week_for_bank_holidays(week_dates)

    if not bank_holidays_in_week:
        # No bank holidays this week
        return data

    # Print bank holiday information
    for day_index, date_obj, holiday_name in bank_holidays_in_week:
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        print(f"🏦 Bank Holiday Detected: {day_names[day_index]} {date_obj.strftime('%b %d, %Y')} - {holiday_name}")

    # Correct hours for each bank holiday
    corrections_made = False

    for day_index, date_obj, holiday_name in bank_holidays_in_week:
        # Correct daily totals
        if 'daily_totals' in data and len(data['daily_totals']) > day_index:
            original_hours = data['daily_totals'][day_index]
            if original_hours != 0:
                print(f"   Correcting daily total from {original_hours} to 0")
                data['daily_totals'][day_index] = 0
                corrections_made = True

        # Correct project hours
        for project in data.get('projects', []):
            hours_by_day = project.get('hours_by_day', [])
            if len(hours_by_day) > day_index:
                day_data = hours_by_day[day_index]
                original_hours = parse_hours(day_data.get('hours', '0'))
                if original_hours != 0:
                    print(f"   Correcting {project.get('project_name', 'Unknown Project')} from {original_hours} to 0")
                    day_data['hours'] = '0'
                    corrections_made = True

    # Recalculate weekly total if corrections were made
    if corrections_made and 'daily_totals' in data:
        new_weekly_total = sum(parse_hours(str(h)) for h in data['daily_totals'])
        old_weekly_total = data.get('weekly_total', 0)
        if new_weekly_total != old_weekly_total:
            print(f"   Recalculating weekly total from {old_weekly_total} to {new_weekly_total}")
            data['weekly_total'] = new_weekly_total

    return data


def enforce_project_code_quality(data: dict) -> dict:
    """
    Enforce project code quality rules and auto-correct common OCR errors.

    This function:
    1. Validates project name format (code must be in parentheses at end)
    2. Corrects common OCR digit confusions (0↔9, 0↔8, 6↔5, 2↔3, 1↔7)
    3. Fixes project names missing codes or having wrong codes
    4. Detects and corrects category labels (DESIGN, LABOUR, etc.) used as codes

    Args:
        data: Dictionary containing parsed timesheet data

    Returns:
        Dictionary with corrected project codes and names
    """
    # Skip if zero-hour timesheet
    if data.get('is_zero_hour_timesheet'):
        return data

    projects = data.get('projects', [])
    if not projects:
        return data

    corrections_made = False

    for project in projects:
        project_name = project.get('project_name', '')
        project_code = project.get('project_code', '')

        if not project_name or not project_code:
            continue

        # Analyze quality
        quality = analyze_project_code_quality(project_code, project_name)

        # Apply corrections if needed
        if not quality['valid'] or quality['warnings']:
            # Try to load master codes (if project_manager is available)
            try:
                from project_manager import ProjectManager
                pm = ProjectManager()
                master_codes = [p['code'] for p in pm.projects]
            except:
                master_codes = None

            # Correct the data
            correction = correct_project_data(project_name, project_code, master_codes)

            if correction['changes_made']:
                old_name = project_name
                old_code = project_code

                # Apply corrections
                project['project_name'] = correction['corrected_name']
                project['project_code'] = correction['corrected_code']

                # Log the changes
                print(f"📝 Project Code Quality Correction:")
                print(f"   Project: {old_code}")
                for change in correction['changes_made']:
                    print(f"   - {change}")
                print(f"   Before: {old_name}")
                print(f"   After:  {correction['corrected_name']}")
                print(f"   Confidence: {correction['confidence']}")

                corrections_made = True

        # Additional check: detect common OCR patterns even if validation passed
        # Check for leading 9 that should be 0
        if project_code.startswith('PJ9'):
            possible_correction = 'PJ0' + project_code[3:]
            print(f"⚠️  Possible OCR Error Detected:")
            print(f"   Project: {project_name}")
            print(f"   Code: {project_code}")
            print(f"   Suggestion: Might be {possible_correction} (9→0 confusion)")
            print(f"   Action: Manual review recommended")

    return data


def convert_to_csv(timesheet_data: dict) -> str:
    """
    Convert timesheet data to CSV format.

    Args:
        timesheet_data: Dictionary containing parsed timesheet data

    Returns:
        CSV string with format: Resource Name, Date, Project Name, Project Code, Hours

    Raises:
        ValueError: If data is invalid or missing required fields
        ImportError: If pandas is not installed
    """
    if not HAS_PANDAS:
        raise ImportError("pandas is required for CSV export. Install with: pip install pandas")

    # Validate data first
    warnings = validate_timesheet_data(timesheet_data)
    if warnings:
        print(f"WARNING: Data validation issues: {', '.join(warnings)}")

    # Extract basic info
    resource_name = timesheet_data.get('resource_name', 'Unknown')

    # Normalize resource name using team roster aliases
    try:
        team_mgr = TeamManager()
        normalized_name, confidence, match_type = team_mgr.normalize_name(resource_name)
        if match_type == 'alias':
            print(f"📝 Name normalization: '{resource_name}' → '{normalized_name}' (alias)")
            resource_name = normalized_name
        elif match_type == 'fuzzy' and confidence >= 0.85:
            print(f"📝 Name normalization: '{resource_name}' → '{normalized_name}' (fuzzy match {confidence:.2f})")
            resource_name = normalized_name
    except Exception as e:
        print(f"⚠️  Name normalization failed: {e}, using original name")

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

        # Validate project code - skip if invalid (e.g., subtask labels like "DESIGN", "LABOUR")
        if not is_valid_project_code(project_code):
            print(f"WARNING: Skipping invalid project code '{project_code}' for project '{project_name}'")
            print(f"         This appears to be a subtask label, not a valid project code")
            continue

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

            # CRITICAL FIX: Skip entries with 0 hours to prevent database bloat
            # Only create database entries for days where actual work was logged
            # Exception: Bank holidays should still be recorded as 0 hours
            if hours == 0 and not is_bank_holiday(date_obj):
                continue

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
