"""
Unit tests for utils module.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from datetime import datetime
from utils import (
    parse_date_range,
    generate_week_dates,
    normalize_project_code,
    parse_hours,
    sanitize_filename,
    format_date_for_csv,
    validate_timesheet_data
)


class TestParseDateRange:
    def test_valid_date_range(self):
        start, end = parse_date_range("Sep 29 2025 - Oct 5 2025")
        assert start == datetime(2025, 9, 29)
        assert end == datetime(2025, 10, 5)

    def test_different_months(self):
        start, end = parse_date_range("Dec 30 2024 - Jan 5 2025")
        assert start == datetime(2024, 12, 30)
        assert end == datetime(2025, 1, 5)

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            parse_date_range("Invalid date")


class TestGenerateWeekDates:
    def test_full_week(self):
        start = datetime(2025, 9, 29)  # Monday
        end = datetime(2025, 10, 5)    # Sunday
        dates = generate_week_dates(start, end)

        assert len(dates) == 7
        assert dates[0].weekday() == 0  # Monday
        assert dates[6].weekday() == 6  # Sunday

    def test_wrong_length(self):
        start = datetime(2025, 9, 29)
        end = datetime(2025, 10, 1)  # Only 3 days
        with pytest.raises(ValueError, match="exactly 7 days"):
            generate_week_dates(start, end)

    def test_not_starting_monday(self):
        start = datetime(2025, 9, 30)  # Tuesday
        end = datetime(2025, 10, 6)
        with pytest.raises(ValueError, match="must start on Monday"):
            generate_week_dates(start, end)


class TestNormalizeProjectCode:
    def test_valid_code(self):
        assert normalize_project_code("PJ021931") == "PJ021931"

    def test_ocr_error_O_to_0(self):
        assert normalize_project_code("PJO21931") == "PJ021931"
        assert normalize_project_code("PJ021931") == "PJ021931"

    def test_ocr_error_I_to_1(self):
        assert normalize_project_code("PJ02I931") == "PJ021931"

    def test_ocr_error_L_to_1(self):
        assert normalize_project_code("PJ02L931") == "PJ021931"

    def test_lowercase(self):
        assert normalize_project_code("pj021931") == "PJ021931"

    def test_empty_string(self):
        assert normalize_project_code("") == ""


class TestParseHours:
    def test_valid_hours(self):
        assert parse_hours("7.5") == 7.5
        assert parse_hours("7.50") == 7.5
        assert parse_hours("0") == 0.0

    def test_empty_string(self):
        assert parse_hours("") == 0.0
        assert parse_hours("   ") == 0.0

    def test_dash(self):
        assert parse_hours("-") == 0.0

    def test_invalid(self):
        assert parse_hours("invalid") == 0.0


class TestSanitizeFilename:
    def test_valid_filename(self):
        assert sanitize_filename("test_file.csv") == "test_file.csv"

    def test_spaces(self):
        assert sanitize_filename("test file.csv") == "test_file.csv"

    def test_special_chars(self):
        result = sanitize_filename("test/file:name.csv")
        assert "/" not in result
        assert ":" not in result


class TestFormatDateForCsv:
    def test_format(self):
        date = datetime(2025, 9, 29)
        assert format_date_for_csv(date) == "2025-09-29"

    def test_single_digit_month(self):
        date = datetime(2025, 1, 5)
        assert format_date_for_csv(date) == "2025-01-05"


class TestValidateTimesheetData:
    def test_valid_data(self):
        data = {
            "resource_name": "John Doe",
            "date_range": "Sep 29 2025 - Oct 5 2025",
            "projects": [
                {
                    "project_name": "Project A",
                    "project_code": "PJ021931",
                    "hours_by_day": [{"day": "Monday", "hours": "7.5"}] * 7
                }
            ]
        }
        warnings = validate_timesheet_data(data)
        assert len(warnings) == 0

    def test_missing_resource_name(self):
        data = {"date_range": "Sep 29 2025 - Oct 5 2025", "projects": []}
        warnings = validate_timesheet_data(data)
        assert any("resource name" in w.lower() for w in warnings)

    def test_missing_projects(self):
        data = {"resource_name": "John Doe", "date_range": "Sep 29 2025 - Oct 5 2025", "projects": []}
        warnings = validate_timesheet_data(data)
        assert any("no projects" in w.lower() for w in warnings)

    def test_missing_project_code(self):
        data = {
            "resource_name": "John Doe",
            "date_range": "Sep 29 2025 - Oct 5 2025",
            "projects": [
                {
                    "project_name": "Project A",
                    "hours_by_day": [{"day": "Monday", "hours": "7.5"}] * 7
                }
            ]
        }
        warnings = validate_timesheet_data(data)
        assert any("project code" in w.lower() for w in warnings)

    def test_wrong_number_of_days(self):
        data = {
            "resource_name": "John Doe",
            "date_range": "Sep 29 2025 - Oct 5 2025",
            "projects": [
                {
                    "project_name": "Project A",
                    "project_code": "PJ021931",
                    "hours_by_day": [{"day": "Monday", "hours": "7.5"}] * 5  # Only 5 days
                }
            ]
        }
        warnings = validate_timesheet_data(data)
        assert any("7 days" in w for w in warnings)
