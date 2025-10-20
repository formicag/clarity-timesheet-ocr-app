"""
Utility functions for timesheet OCR processing.
"""
import re
from datetime import datetime, timedelta
from typing import List, Tuple


def parse_date_range(date_range_str: str) -> Tuple[datetime, datetime]:
    """
    Parse date range string like "Sep 29 2025 - Oct 5 2025".

    Args:
        date_range_str: Date range in format "MMM DD YYYY - MMM DD YYYY"

    Returns:
        Tuple of (start_date, end_date) as datetime objects

    Raises:
        ValueError: If date format is invalid
    """
    try:
        # Remove extra whitespace and split by dash
        parts = date_range_str.strip().split('-')
        if len(parts) != 2:
            raise ValueError(f"Invalid date range format: {date_range_str}")

        start_str = parts[0].strip()
        end_str = parts[1].strip()

        # Parse dates - handle both "Sep 29 2025" and "29 Sep 2025" formats
        start_date = datetime.strptime(start_str, "%b %d %Y")
        end_date = datetime.strptime(end_str, "%b %d %Y")

        return start_date, end_date
    except Exception as e:
        raise ValueError(f"Error parsing date range '{date_range_str}': {str(e)}")


def generate_week_dates(start_date: datetime, end_date: datetime) -> List[datetime]:
    """
    Generate list of dates from Monday to Sunday for the given week.

    Args:
        start_date: Start of the week (should be Monday)
        end_date: End of the week (should be Sunday)

    Returns:
        List of datetime objects for each day of the week

    Raises:
        ValueError: If date range doesn't span exactly one week
    """
    dates = []
    current_date = start_date

    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)

    # Validate we have exactly 7 days (Mon-Sun)
    if len(dates) != 7:
        raise ValueError(f"Date range must be exactly 7 days (Mon-Sun), got {len(dates)} days")

    # Validate starts on Monday (weekday 0)
    if dates[0].weekday() != 0:
        raise ValueError(f"Week must start on Monday, but starts on {dates[0].strftime('%A')}")

    return dates


def normalize_project_code(project_code: str) -> str:
    """
    Normalize project code to fix common OCR errors.

    Common OCR errors:
    - Letter O mistaken for digit 0
    - Letter I mistaken for digit 1
    - Letter l mistaken for digit 1

    Args:
        project_code: Raw project code from OCR

    Returns:
        Normalized project code
    """
    if not project_code:
        return project_code

    # Project codes typically start with 'PJ' followed by digits
    normalized = project_code.upper()

    # If it starts with 'PJ', ensure the rest are digits
    if normalized.startswith('PJ'):
        prefix = normalized[:2]
        suffix = normalized[2:]

        # Replace common OCR errors in the numeric part
        suffix = suffix.replace('O', '0')
        suffix = suffix.replace('I', '1')
        suffix = suffix.replace('L', '1')

        normalized = prefix + suffix

    return normalized


def parse_hours(hours_str: str) -> float:
    """
    Parse hours string to float, handling empty values.

    Args:
        hours_str: Hours as string (may be empty, "7.5", "7.50", etc)

    Returns:
        Hours as float (0.0 if empty)
    """
    if not hours_str or hours_str.strip() == '' or hours_str.strip() == '-':
        return 0.0

    try:
        return float(hours_str.strip())
    except ValueError:
        # If parsing fails, assume 0 hours
        return 0.0


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[^\w\s\-.]', '_', filename)
    # Remove duplicate underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')

    return sanitized


def format_date_for_csv(date_obj: datetime) -> str:
    """
    Format date for CSV output.

    Args:
        date_obj: Date as datetime object

    Returns:
        Date formatted as YYYY-MM-DD
    """
    return date_obj.strftime("%Y-%m-%d")


def validate_timesheet_data(data: dict) -> List[str]:
    """
    Validate extracted timesheet data and return list of warnings.

    Args:
        data: Dictionary containing parsed timesheet data

    Returns:
        List of validation warning messages (empty if all valid)
    """
    warnings = []

    # Check required fields
    if not data.get('resource_name'):
        warnings.append("Missing resource name")

    if not data.get('date_range'):
        warnings.append("Missing date range")

    if not data.get('projects') or len(data['projects']) == 0:
        warnings.append("No projects found")

    # Validate projects
    for i, project in enumerate(data.get('projects', [])):
        project_name = project.get('project_name', f'Project {i+1}')

        if not project.get('project_code'):
            warnings.append(f"Missing project code for '{project_name}'")

        if not project.get('hours_by_day'):
            warnings.append(f"Missing hours data for '{project_name}'")
        else:
            # Check we have exactly 7 days of data
            if len(project['hours_by_day']) != 7:
                warnings.append(f"Expected 7 days of hours for '{project_name}', got {len(project['hours_by_day'])}")

    return warnings
