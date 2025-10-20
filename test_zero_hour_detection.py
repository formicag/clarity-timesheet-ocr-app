"""
Test script for zero-hour timesheet detection.
"""
import sys
sys.path.insert(0, 'src')

from prompt import get_ocr_prompt

# Test the prompt
prompt = get_ocr_prompt()

print("=== OCR PROMPT ===")
print(prompt)
print("\n=== CHECKING FOR ZERO-HOUR DETECTION ===")

# Check if prompt mentions zero-hour detection
if "is_zero_hour_timesheet" in prompt:
    print("✓ Prompt includes zero-hour timesheet detection")
else:
    print("✗ Prompt missing zero-hour timesheet detection")

if "zero_hour_reason" in prompt:
    print("✓ Prompt includes zero-hour reason field")
else:
    print("✗ Prompt missing zero-hour reason field")

if "ANNUAL_LEAVE" in prompt or "annual leave" in prompt.lower():
    print("✓ Prompt mentions annual leave")
else:
    print("✗ Prompt doesn't mention annual leave")

print("\n=== TEST COMPLETE ===")
