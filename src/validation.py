"""
Validation module for timesheet data integrity checks.
"""
from typing import Dict, List, Any
from utils import parse_hours


def validate_timesheet_data(timesheet_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate timesheet data for accuracy and integrity.

    Checks:
    1. Project hours sum to daily totals
    2. Daily totals sum to weekly total
    3. Each project's hours sum correctly
    4. Detects potential "Posted Actuals" confusion

    Args:
        timesheet_data: Parsed timesheet data dictionary

    Returns:
        Dictionary with validation results:
        {
            'valid': bool,
            'errors': List[str],
            'warnings': List[str],
            'summary': str
        }
    """
    errors = []
    warnings = []

    resource_name = timesheet_data.get('resource_name', 'Unknown')
    is_zero_hour = timesheet_data.get('is_zero_hour_timesheet', False)
    projects = timesheet_data.get('projects', [])
    daily_totals = timesheet_data.get('daily_totals', [0] * 7)
    weekly_total = timesheet_data.get('weekly_total', 0)
    day_alignment_errors = timesheet_data.get('day_alignment_errors', [])

    # Skip validation for zero-hour timesheets
    if is_zero_hour:
        return {
            'valid': True,
            'errors': [],
            'warnings': [],
            'summary': f'✓ Zero-hour timesheet validation passed for {resource_name}'
        }

    # CRITICAL Validation 0: Check for wrong-day assignments
    # This is the MOST IMPORTANT validation - if days are misaligned, the entire timesheet is unusable
    if day_alignment_errors:
        for alignment_error in day_alignment_errors:
            errors.append(f"🚨 {alignment_error}")

    # Validation 1: Calculate project hours by day
    calculated_daily_totals = [0.0] * 7

    for project in projects:
        project_name = project.get('project_name', 'Unknown')
        project_code = project.get('project_code', 'Unknown')
        hours_by_day = project.get('hours_by_day', [])

        project_total = 0.0

        for i, day_data in enumerate(hours_by_day):
            if i >= 7:
                break

            hours = parse_hours(day_data.get('hours', '0'))
            calculated_daily_totals[i] += hours
            project_total += hours

        # Check if project total seems suspiciously high (might be Posted Actuals)
        if project_total > 50:
            warnings.append(
                f"⚠️  Project '{project_code}' has {project_total} hours - "
                f"this seems very high for one week. Check if 'Posted Actuals' was extracted instead of 'Total'."
            )

    # Validation 2: Compare calculated daily totals with extracted daily totals
    tolerance = 0.01  # Allow small floating point differences

    for i in range(7):
        calculated = calculated_daily_totals[i]
        extracted = float(daily_totals[i]) if i < len(daily_totals) else 0.0

        if abs(calculated - extracted) > tolerance:
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            errors.append(
                f"❌ {day_names[i]}: Project hours sum to {calculated:.2f} but header shows {extracted:.2f}"
            )

    # Validation 3: Check weekly total matches sum of daily totals
    calculated_weekly = sum(calculated_daily_totals)
    extracted_weekly = float(weekly_total)

    if abs(calculated_weekly - extracted_weekly) > tolerance:
        errors.append(
            f"❌ Weekly total mismatch: Project hours sum to {calculated_weekly:.2f} "
            f"but header shows {extracted_weekly:.2f}"
        )

    # Validation 4: Check if daily totals sum to weekly total
    sum_of_daily = sum(float(d) for d in daily_totals)
    if abs(sum_of_daily - extracted_weekly) > tolerance:
        errors.append(
            f"❌ Header inconsistency: Daily totals sum to {sum_of_daily:.2f} "
            f"but weekly total shows {extracted_weekly:.2f}"
        )

    # Validation 5: Detect Posted Actuals confusion
    # If weekly total is very high (> 60 hours), likely extracted Posted Actuals
    if extracted_weekly > 60:
        errors.append(
            f"❌ Weekly total is {extracted_weekly} hours - this is suspiciously high! "
            f"Likely extracted 'Posted Actuals' instead of 'Total' column."
        )

    # Generate summary
    if errors:
        summary = f"❌ VALIDATION FAILED for {resource_name}: {len(errors)} error(s), {len(warnings)} warning(s)"
    elif warnings:
        summary = f"⚠️  VALIDATION PASSED WITH WARNINGS for {resource_name}: {len(warnings)} warning(s)"
    else:
        summary = f"✓ VALIDATION PASSED for {resource_name}: All hours match correctly"

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'summary': summary
    }


def format_validation_report(validation_result: Dict[str, Any]) -> str:
    """
    Format validation results as a readable report.

    Args:
        validation_result: Result from validate_timesheet_data()

    Returns:
        Formatted string report
    """
    lines = []
    lines.append("=" * 80)
    lines.append("VALIDATION REPORT")
    lines.append("=" * 80)
    lines.append(validation_result['summary'])
    lines.append("")

    if validation_result['errors']:
        lines.append("ERRORS:")
        for error in validation_result['errors']:
            lines.append(f"  {error}")
        lines.append("")

    if validation_result['warnings']:
        lines.append("WARNINGS:")
        for warning in validation_result['warnings']:
            lines.append(f"  {warning}")
        lines.append("")

    lines.append("=" * 80)

    return "\n".join(lines)
