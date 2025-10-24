"""
UK Bank Holidays for 2025 and validation utilities.
"""
from datetime import datetime
from typing import List, Set

# UK Bank Holidays for 2025
# Source: https://www.gov.uk/bank-holidays
UK_BANK_HOLIDAYS_2025 = [
    "2025-01-01",  # New Year's Day
    "2025-04-18",  # Good Friday
    "2025-04-21",  # Easter Monday
    "2025-05-05",  # Early May bank holiday
    "2025-05-26",  # Spring bank holiday
    "2025-08-25",  # Summer bank holiday (Late Summer bank holiday)
    "2025-12-25",  # Christmas Day
    "2025-12-26",  # Boxing Day
]


def get_bank_holidays_2025() -> List[datetime]:
    """
    Get list of UK bank holidays for 2025 as datetime objects.

    Returns:
        List of datetime objects representing bank holidays
    """
    return [datetime.strptime(date, "%Y-%m-%d") for date in UK_BANK_HOLIDAYS_2025]


def get_bank_holidays_2025_set() -> Set[str]:
    """
    Get set of UK bank holidays for 2025 as date strings (YYYY-MM-DD format).

    Returns:
        Set of date strings in YYYY-MM-DD format
    """
    return set(UK_BANK_HOLIDAYS_2025)


def is_bank_holiday(date_obj: datetime) -> bool:
    """
    Check if a given date is a UK bank holiday in 2025.

    Args:
        date_obj: Date to check as datetime object

    Returns:
        True if the date is a bank holiday, False otherwise
    """
    date_str = date_obj.strftime("%Y-%m-%d")
    return date_str in UK_BANK_HOLIDAYS_2025


def get_bank_holiday_name(date_obj: datetime) -> str:
    """
    Get the name of the bank holiday for a given date.

    Args:
        date_obj: Date to check as datetime object

    Returns:
        Name of the bank holiday, or None if not a bank holiday
    """
    date_str = date_obj.strftime("%Y-%m-%d")

    holiday_names = {
        "2025-01-01": "New Year's Day",
        "2025-04-18": "Good Friday",
        "2025-04-21": "Easter Monday",
        "2025-05-05": "Early May bank holiday",
        "2025-05-26": "Spring bank holiday",
        "2025-08-25": "Summer bank holiday",
        "2025-12-25": "Christmas Day",
        "2025-12-26": "Boxing Day",
    }

    return holiday_names.get(date_str)


def format_bank_holidays_for_prompt() -> str:
    """
    Format bank holidays list for inclusion in OCR prompt.

    Returns:
        Formatted string listing all UK bank holidays for 2025
    """
    holidays = get_bank_holidays_2025()
    lines = ["UK Bank Holidays 2025:"]

    for holiday in holidays:
        name = get_bank_holiday_name(holiday)
        date_str = holiday.strftime("%b %d, %Y")  # e.g., "Aug 25, 2025"
        day_name = holiday.strftime("%A")  # e.g., "Monday"
        lines.append(f"  - {date_str} ({day_name}): {name}")

    return "\n".join(lines)


def validate_week_for_bank_holidays(week_dates: List[datetime]) -> List[tuple]:
    """
    Check which days in a week are bank holidays.

    Args:
        week_dates: List of datetime objects for the week (Mon-Sun)

    Returns:
        List of tuples: (day_index, date_obj, holiday_name) for each bank holiday in the week
    """
    bank_holidays_in_week = []

    for i, date_obj in enumerate(week_dates):
        if is_bank_holiday(date_obj):
            holiday_name = get_bank_holiday_name(date_obj)
            bank_holidays_in_week.append((i, date_obj, holiday_name))

    return bank_holidays_in_week
