#!/usr/bin/env python3
"""
Test script to verify zero-hour timesheet detection.
This will test the prompt and parsing without the UI.
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from prompt import get_ocr_prompt
from parsing import parse_timesheet_json
from utils import validate_timesheet_totals

# Test data 1: Zero-hour timesheet
zero_hour_json = """{
  "resource_name": "Test User",
  "date_range": "Oct 20 2025 - Oct 26 2025",
  "is_zero_hour_timesheet": true,
  "zero_hour_reason": "ANNUAL_LEAVE",
  "daily_totals": [0, 0, 0, 0, 0, 0, 0],
  "weekly_total": 0,
  "projects": []
}"""

# Test data 2: Regular timesheet
regular_json = """{
  "resource_name": "Test User",
  "date_range": "Oct 20 2025 - Oct 26 2025",
  "is_zero_hour_timesheet": false,
  "zero_hour_reason": null,
  "daily_totals": [7.5, 7.5, 7.5, 7.5, 7.5, 0, 0],
  "weekly_total": 37.5,
  "projects": [
    {
      "project_name": "Test Project (PJ123456)",
      "project_code": "PJ123456",
      "hours_by_day": [
        {"day": "Monday", "hours": "7.5"},
        {"day": "Tuesday", "hours": "7.5"},
        {"day": "Wednesday", "hours": "7.5"},
        {"day": "Thursday", "hours": "7.5"},
        {"day": "Friday", "hours": "7.5"},
        {"day": "Saturday", "hours": "0"},
        {"day": "Sunday", "hours": "0"}
      ]
    }
  ]
}"""

def test_parsing_and_validation():
    print("=" * 70)
    print("TESTING ZERO-HOUR TIMESHEET DETECTION")
    print("=" * 70)
    print()

    # Test 1: Zero-hour timesheet
    print("TEST 1: Zero-hour timesheet")
    print("-" * 70)
    data1 = parse_timesheet_json(zero_hour_json)
    print(f"✓ Parsed successfully")
    print(f"  is_zero_hour_timesheet: {data1.get('is_zero_hour_timesheet')}")
    print(f"  zero_hour_reason: {data1.get('zero_hour_reason')}")
    print(f"  projects count: {len(data1.get('projects', []))}")

    validation1 = validate_timesheet_totals(data1)
    print(f"  Validation valid: {validation1['valid']}")
    print(f"  Validation errors: {validation1['errors']}")

    if data1.get('is_zero_hour_timesheet') and validation1['valid']:
        print("✅ PASS: Zero-hour timesheet correctly detected and validated")
    else:
        print("❌ FAIL: Zero-hour timesheet validation failed")
    print()

    # Test 2: Regular timesheet
    print("TEST 2: Regular timesheet")
    print("-" * 70)
    data2 = parse_timesheet_json(regular_json)
    print(f"✓ Parsed successfully")
    print(f"  is_zero_hour_timesheet: {data2.get('is_zero_hour_timesheet')}")
    print(f"  projects count: {len(data2.get('projects', []))}")

    validation2 = validate_timesheet_totals(data2)
    print(f"  Validation valid: {validation2['valid']}")
    print(f"  Validation errors: {validation2['errors']}")

    if not data2.get('is_zero_hour_timesheet') and validation2['valid']:
        print("✅ PASS: Regular timesheet correctly validated")
    else:
        print("❌ FAIL: Regular timesheet validation failed")
    print()

    # Show the prompt being used
    print("=" * 70)
    print("PROMPT CHECK")
    print("=" * 70)
    prompt = get_ocr_prompt()
    if "PROJECT TIME: 0%" in prompt:
        print("✅ Prompt contains zero-hour detection instructions")
    else:
        print("❌ Prompt MISSING zero-hour detection instructions")

    if 'is_zero_hour_timesheet' in prompt:
        print("✅ Prompt mentions is_zero_hour_timesheet field")
    else:
        print("❌ Prompt does NOT mention is_zero_hour_timesheet field")

    print()
    print("Prompt excerpt (zero-hour section):")
    print("-" * 70)
    # Find and show the zero-hour section
    lines = prompt.split('\n')
    in_zero_section = False
    for line in lines:
        if 'Zero-Hour' in line or 'zero-hour' in line or 'PROJECT TIME: 0%' in line:
            in_zero_section = True
        if in_zero_section:
            print(line)
            if line.strip().startswith('**') and 'Zero' not in line:
                break

    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

if __name__ == '__main__':
    test_parsing_and_validation()
