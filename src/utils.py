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

        # Try multiple date formats
        date_formats = [
            "%b %d, %Y",      # Aug 25, 2025
            "%b %d %Y",       # Aug 25 2025
            "%d %b, %Y",      # 25 Aug, 2025
            "%d %b %Y",       # 25 Aug 2025
            "%m.%d.%Y",       # 03.13.2023
            "%m/%d/%Y",       # 03/13/2023
        ]

        # Formats without year (we'll use end date's year)
        short_formats = [
            "%b %d",          # Aug 25
            "%d %b",          # 25 Aug
        ]

        start_date = None
        end_date = None

        # First try full formats on both dates
        for fmt in date_formats:
            try:
                start_date = datetime.strptime(start_str, fmt)
                end_date = datetime.strptime(end_str, fmt)
                break
            except ValueError:
                continue

        # If that failed, try short format on start date with year from end date
        if start_date is None or end_date is None:
            # First parse end date to get the year
            for fmt in date_formats:
                try:
                    end_date = datetime.strptime(end_str, fmt)
                    break
                except ValueError:
                    continue

            if end_date:
                # Now try short formats on start date
                for fmt in short_formats:
                    try:
                        start_date = datetime.strptime(start_str, fmt)
                        # Add year from end date
                        start_date = start_date.replace(year=end_date.year)
                        # Handle year boundary (e.g., "Dec 30 - Jan 5 2025")
                        if start_date > end_date:
                            start_date = start_date.replace(year=end_date.year - 1)
                        break
                    except ValueError:
                        continue

        if start_date is None or end_date is None:
            raise ValueError(f"Could not parse dates with any known format")

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

    # Validate starts on Monday (weekday 0) - but be flexible and auto-adjust if needed
    if dates[0].weekday() != 0:
        # Calculate how many days back to Monday
        days_since_monday = dates[0].weekday()
        # If week doesn't start on Monday, adjust to previous Monday
        monday = dates[0] - timedelta(days=days_since_monday)

        # Regenerate dates from Monday
        dates = []
        for i in range(7):
            dates.append(monday + timedelta(days=i))

    return dates


def is_valid_project_code(project_code: str) -> bool:
    """
    Check if a project code is valid.

    Valid project codes are:
    - PJ followed by 6 digits (e.g., PJ025043)
    - REAG followed by 6 digits (e.g., REAG042910)
    - HCST followed by digits (e.g., HCST314980)
    - NTC5 followed by digits (e.g., NTC5124690)
    - Other letter prefixes followed by digits (flexible for future codes)

    Invalid patterns (subtask labels):
    - Pure words like DESIGN, LABOUR, TESTING
    - Anything without digits

    Args:
        project_code: Project code to validate

    Returns:
        True if valid, False otherwise
    """
    if not project_code or len(project_code) < 3:
        return False

    code = project_code.upper().strip()

    # Must contain at least one digit (project codes have numbers)
    if not any(c.isdigit() or c in 'OIL' for c in code):  # OIL are OCR errors for 0,1,1
        return False

    # Reject pure words (subtask labels)
    if code.isalpha():
        return False

    # Check common valid patterns
    # Pattern 1: PJ + 6 digits
    if code.startswith('PJ') and len(code) >= 8:
        return True

    # Pattern 2: REAG + 6 digits
    if code.startswith('REAG') and len(code) >= 10:
        return True

    # Pattern 3: HCST + digits
    if code.startswith('HCST') and len(code) >= 8:
        return True

    # Pattern 4: NTC5 + digits
    if code.startswith('NTC5') and len(code) >= 8:
        return True

    # Pattern 5: Other letter prefix + digits (e.g., SCR1476, PR12345)
    # Must start with letters, then have digits
    has_letter_prefix = False
    has_digits = False
    for i, c in enumerate(code):
        if i == 0 and not c.isalpha():
            return False  # Must start with letter
        if c.isalpha():
            has_letter_prefix = True
        elif c.isdigit() or c in 'OIL':
            has_digits = True

    return has_letter_prefix and has_digits


def normalize_project_code(project_code: str) -> str:
    """
    Normalize project code to fix common OCR errors.

    Common OCR errors:
    - Letter O mistaken for digit 0
    - Letter I mistaken for digit 1
    - Letter l mistaken for digit 1
    - Letter S mistaken for digit 5 (in NTCS vs NTC5)

    Args:
        project_code: Raw project code from OCR

    Returns:
        Normalized project code
    """
    if not project_code:
        return project_code

    # Project codes typically start with 'PJ' followed by digits
    normalized = project_code.upper()

    # REMOVED INCORRECT NORMALIZATION:
    # Old code wrongly converted NTCS→NTC5, but NTCS158600 is a valid code!
    # Project code correction in project_code_correction.py now handles this properly
    # using the master codes dictionary

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


def validate_timesheet_totals(data: dict) -> dict:
    """
    Validate that daily and weekly totals match the sum of project hours.

    Args:
        data: Dictionary containing parsed timesheet data with 'daily_totals' and 'weekly_total'

    Returns:
        Dictionary with validation results:
        {
            'valid': bool,
            'daily_validation': [{'day': str, 'expected': float, 'actual': float, 'match': bool}, ...],
            'weekly_validation': {'expected': float, 'actual': float, 'match': bool},
            'errors': [str, ...]
        }
    """
    result = {
        'valid': True,
        'daily_validation': [],
        'weekly_validation': {},
        'errors': []
    }

    # Skip validation for zero-hour timesheets
    if data.get('is_zero_hour_timesheet'):
        # For zero-hour timesheets, everything should be 0
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for i in range(7):
            result['daily_validation'].append({
                'day': day_names[i],
                'expected': 0.0,
                'actual': 0.0,
                'match': True
            })
        result['weekly_validation'] = {
            'expected': 0.0,
            'actual': 0.0,
            'match': True
        }
        return result

    # Get expected totals from the header row
    daily_totals_header = data.get('daily_totals', [])  # [Mon, Tue, Wed, Thu, Fri, Sat, Sun]
    weekly_total_header = data.get('weekly_total', 0)

    # Calculate actual totals from projects
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    calculated_daily = [0.0] * 7
    calculated_weekly = 0.0

    for project in data.get('projects', []):
        hours_by_day = project.get('hours_by_day', [])
        for i, day_data in enumerate(hours_by_day):
            if i >= 7:
                break
            hours = parse_hours(day_data.get('hours', '0'))
            calculated_daily[i] += hours
            calculated_weekly += hours

    # Validate each day
    tolerance = 0.01  # Allow 0.01 hour difference for floating point
    for i in range(7):
        expected = parse_hours(str(daily_totals_header[i])) if i < len(daily_totals_header) else 0.0
        actual = calculated_daily[i]
        match = abs(expected - actual) < tolerance

        result['daily_validation'].append({
            'day': day_names[i],
            'expected': expected,
            'actual': actual,
            'match': match
        })

        if not match:
            result['valid'] = False
            result['errors'].append(
                f"{day_names[i]}: Expected {expected:.2f}h but projects sum to {actual:.2f}h"
            )

    # Validate weekly total
    expected_weekly = parse_hours(str(weekly_total_header))
    match_weekly = abs(expected_weekly - calculated_weekly) < tolerance

    result['weekly_validation'] = {
        'expected': expected_weekly,
        'actual': calculated_weekly,
        'match': match_weekly
    }

    if not match_weekly:
        result['valid'] = False
        result['errors'].append(
            f"Weekly Total: Expected {expected_weekly:.2f}h but projects sum to {calculated_weekly:.2f}h"
        )

    return result


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
