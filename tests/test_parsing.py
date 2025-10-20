"""
Unit tests for parsing module.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
import json
from parsing import (
    parse_timesheet_json,
    convert_to_csv,
    generate_output_filename,
    calculate_cost_estimate
)


class TestParseTimesheetJson:
    def test_valid_json(self):
        json_str = '''
        {
            "resource_name": "John Doe",
            "date_range": "Sep 29 2025 - Oct 5 2025",
            "projects": []
        }
        '''
        data = parse_timesheet_json(json_str)
        assert data["resource_name"] == "John Doe"

    def test_json_with_markdown(self):
        json_str = '''
        ```json
        {
            "resource_name": "John Doe",
            "date_range": "Sep 29 2025 - Oct 5 2025",
            "projects": []
        }
        ```
        '''
        data = parse_timesheet_json(json_str)
        assert data["resource_name"] == "John Doe"

    def test_invalid_json(self):
        with pytest.raises(ValueError):
            parse_timesheet_json("not valid json")


class TestConvertToCsv:
    def test_basic_conversion(self):
        data = {
            "resource_name": "John Doe",
            "date_range": "Sep 29 2025 - Oct 5 2025",
            "projects": [
                {
                    "project_name": "Project A",
                    "project_code": "PJ021931",
                    "hours_by_day": [
                        {"day": "Monday", "hours": "7.5"},
                        {"day": "Tuesday", "hours": "0"},
                        {"day": "Wednesday", "hours": "7.5"},
                        {"day": "Thursday", "hours": "7.5"},
                        {"day": "Friday", "hours": "7.5"},
                        {"day": "Saturday", "hours": "0"},
                        {"day": "Sunday", "hours": "0"}
                    ]
                }
            ]
        }
        csv = convert_to_csv(data)

        assert "Resource Name,Date,Project Name,Project Code,Hours" in csv
        assert "John Doe" in csv
        assert "Project A" in csv
        assert "PJ021931" in csv
        assert "2025-09-29" in csv  # First date
        assert "2025-10-05" in csv  # Last date

        # Check we have 7 rows (plus header)
        lines = csv.strip().split('\n')
        assert len(lines) == 8  # 1 header + 7 data rows

    def test_multiple_projects(self):
        data = {
            "resource_name": "Jane Smith",
            "date_range": "Sep 29 2025 - Oct 5 2025",
            "projects": [
                {
                    "project_name": "Project A",
                    "project_code": "PJ021931",
                    "hours_by_day": [{"day": f"Day{i}", "hours": "7.5"} for i in range(7)]
                },
                {
                    "project_name": "Project B",
                    "project_code": "PJ024300",
                    "hours_by_day": [{"day": f"Day{i}", "hours": "0"} for i in range(7)]
                }
            ]
        }
        csv = convert_to_csv(data)

        lines = csv.strip().split('\n')
        assert len(lines) == 15  # 1 header + 7*2 data rows

        assert "Project A" in csv
        assert "Project B" in csv

    def test_project_code_normalization(self):
        data = {
            "resource_name": "John Doe",
            "date_range": "Sep 29 2025 - Oct 5 2025",
            "projects": [
                {
                    "project_name": "Project A",
                    "project_code": "PJO2I931",  # Has O and I instead of 0 and 1
                    "hours_by_day": [{"day": f"Day{i}", "hours": "0"} for i in range(7)]
                }
            ]
        }
        csv = convert_to_csv(data)

        assert "PJ021931" in csv  # Should be normalized


class TestGenerateOutputFilename:
    def test_filename_generation(self):
        data = {
            "resource_name": "John Doe",
            "date_range": "Sep 29 2025 - Oct 5 2025"
        }
        filename = generate_output_filename(data, 'csv')

        assert filename.startswith("2025-09-29")
        assert "John_Doe" in filename
        assert filename.endswith("_timesheet.csv")

    def test_special_chars_removed(self):
        data = {
            "resource_name": "John (Doe) & Co.",
            "date_range": "Sep 29 2025 - Oct 5 2025"
        }
        filename = generate_output_filename(data, 'csv')

        assert "(" not in filename
        assert ")" not in filename
        assert "&" not in filename


class TestCalculateCostEstimate:
    def test_sonnet_pricing(self):
        cost = calculate_cost_estimate(1000, 500, "claude-sonnet-4-5")

        assert cost["input_tokens"] == 1000
        assert cost["output_tokens"] == 500
        assert cost["input_cost_usd"] == 0.003  # $3/1M
        assert cost["output_cost_usd"] == 0.0075  # $15/1M
        assert cost["total_cost_usd"] == 0.0105

    def test_opus_pricing(self):
        cost = calculate_cost_estimate(1000, 500, "claude-opus-4")

        assert cost["input_cost_usd"] == 0.015  # $15/1M
        assert cost["output_cost_usd"] == 0.0375  # $75/1M
        assert cost["total_cost_usd"] == 0.0525
