"""
Field Validators for OCR Accuracy Improvement

Auto-corrects common OCR errors in hours, project codes, and other fields.
Designed to work with reference dictionaries extracted from high-quality data.
"""
import re
from typing import Tuple, Optional, Set, Dict


class FieldValidator:
    """Validates and auto-corrects OCR-extracted timesheet fields."""

    def __init__(self, project_code_dictionary: Set[str] = None):
        """
        Initialize validator with reference dictionaries.

        Args:
            project_code_dictionary: Set of known valid project codes
        """
        self.known_codes = project_code_dictionary or set()

    def validate_hours(self, value: any) -> Tuple[Optional[float], Optional[str]]:
        """
        Validate and auto-correct hours field.

        Common OCR errors corrected:
        - Missing decimal: 75 → 7.5, 80 → 8.0
        - Comma as decimal: 7,5 → 7.5
        - Double entry: 15.0 → 7.5 (when 2x duplication)
        - Precision issues: 7.49999 → 7.5

        Args:
            value: Raw hours value (string, int, or float)

        Returns:
            Tuple of (corrected_hours, error_code)
            error_code is None if validation passed
        """
        if value is None or value == '':
            return None, "EMPTY"

        try:
            # Handle different input types
            hours_str = str(value).strip()

            # Handle common formats
            hours_str = hours_str.replace(',', '.')  # European decimal format
            hours_str = hours_str.replace('O', '0')  # Letter O → Zero
            hours_str = hours_str.replace('o', '0')  # Lowercase o → Zero

            hours = float(hours_str)

            # Fix missing decimal point (75 → 7.5, 80 → 8.0, 85 → 8.5)
            if 70 <= hours <= 85:
                if hours % 10 == 5 or hours % 10 == 0:
                    original = hours
                    hours = hours / 10
                    print(f"   🔧 Auto-corrected hours: {original} → {hours} (missing decimal)")

            # Fix double entry pattern (15.0 when should be 7.5, 16.0 → 8.0)
            if hours >= 14.0 and hours % 7.5 == 0:
                if hours == 15.0 or hours == 16.0:
                    original = hours
                    hours = hours / 2
                    print(f"   🔧 Auto-corrected hours: {original} → {hours} (double entry)")

            # Round to 2 decimal places for precision (Clarity allows any decimal value)
            # This fixes floating point precision issues like 7.499999 → 7.50
            hours = round(hours, 2)

            # Validate range (0-24 hours per day)
            if hours < 0:
                return None, f"NEGATIVE_{hours}"

            if hours > 24:
                return None, f"EXCESSIVE_{hours}"

            # Success
            return hours, None

        except (ValueError, TypeError) as e:
            return None, f"PARSE_ERROR_{str(e)}"

    def validate_project_code(self, value: str) -> Tuple[str, Optional[str]]:
        """
        Validate and auto-correct project codes.

        Common OCR errors corrected:
        - Letter/number substitutions: P1023268 → PI023268 (1→I)
        - Letter O → Number 0 in numeric portion
        - Edit distance = 1 (single character errors)
        - Transpositions: PJ021391 → PJ021931

        Args:
            value: Raw project code string

        Returns:
            Tuple of (corrected_code, error_code)
            error_code is None if validation passed
        """
        if not value:
            return value, "EMPTY"

        # Normalize
        code = value.upper().strip()
        original_code = code

        # Pattern: PJ023268, PI023268, PL023268, etc.
        # Format: 2 letters + 6 digits
        match = re.match(r'^([A-Z]{2})(\d{6})$', code)

        if match:
            prefix, number = match.groups()

            # Apply OCR corrections to number portion only
            corrections = {
                'O': '0',  # Letter O → Zero
                'I': '1',  # Letter I → One (rare in numbers)
                'Z': '2',  # Letter Z → Two
                'S': '5',  # Letter S → Five
                'B': '8',  # Letter B → Eight
            }

            for old, new in corrections.items():
                number = number.replace(old, new)

            code = prefix + number

        # Check if code changed
        if code != original_code:
            print(f"   🔧 Auto-corrected project code: {original_code} → {code}")

        # Check against dictionary
        if self.known_codes:
            if code in self.known_codes:
                return code, None

            # Check for 1-character edit distance (typo correction)
            for known_code in self.known_codes:
                if self._edit_distance_1(code, known_code):
                    print(f"   🔧 Dictionary match (edit distance=1): {code} → {known_code}")
                    return known_code, "AUTO_CORRECTED"

            # Check for transposed characters (common OCR error)
            for known_code in self.known_codes:
                if self._is_transposition(code, known_code):
                    print(f"   🔧 Dictionary match (transposition): {code} → {known_code}")
                    return known_code, "TRANSPOSED"

            # Code not in dictionary
            return code, "UNKNOWN_CODE"

        # No dictionary available - return corrected code
        return code, None

    def _edit_distance_1(self, s1: str, s2: str) -> bool:
        """Check if strings differ by exactly 1 character (same length only)."""
        if len(s1) != len(s2):
            return False

        diff_count = sum(c1 != c2 for c1, c2 in zip(s1, s2))
        return diff_count == 1

    def _is_transposition(self, s1: str, s2: str) -> bool:
        """Check if strings differ by one adjacent character transposition."""
        if len(s1) != len(s2) or len(s1) < 2:
            return False

        diffs = [(i, c1, c2) for i, (c1, c2) in enumerate(zip(s1, s2)) if c1 != c2]

        # Must have exactly 2 differences
        if len(diffs) != 2:
            return False

        i1, c1a, c2a = diffs[0]
        i2, c1b, c2b = diffs[1]

        # Check if adjacent and swapped
        return (i2 == i1 + 1) and (c1a == c2b) and (c1b == c2a)


def validate_timesheet_data_fields(timesheet_data: dict, validator: FieldValidator, log_func=print) -> dict:
    """
    Apply field validation to all fields in timesheet data.

    Args:
        timesheet_data: Parsed timesheet dictionary
        validator: FieldValidator instance with loaded dictionaries
        log_func: Logging function

    Returns:
        Modified timesheet_data with corrected fields
    """
    corrections_made = 0

    for project in timesheet_data.get('projects', []):
        # Validate project code
        original_code = project.get('project_code', '')
        corrected_code, error = validator.validate_project_code(original_code)

        if corrected_code != original_code:
            project['project_code'] = corrected_code
            corrections_made += 1

        if error == "UNKNOWN_CODE":
            log_func(f"⚠️  Warning: Unknown project code '{corrected_code}' (not in dictionary)")

        # Validate hours for each day
        for day_index, day_data in enumerate(project.get('hours_by_day', [])):
            original_hours = day_data.get('hours', '0')
            corrected_hours, error = validator.validate_hours(original_hours)

            if corrected_hours is None:
                log_func(f"❌ Invalid hours on day {day_index}: {original_hours} ({error})")
                day_data['hours'] = '0'  # Set to zero if invalid
            elif corrected_hours != float(str(original_hours).replace(',', '.')):
                day_data['hours'] = str(corrected_hours)
                corrections_made += 1
            else:
                day_data['hours'] = str(corrected_hours)

    if corrections_made > 0:
        log_func(f"✅ Made {corrections_made} field corrections")

    return timesheet_data
