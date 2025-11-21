"""
Project code correction and validation for OCR quality improvement.

This module handles:
1. OCR digit confusion (0↔9, 0↔8, 6↔5, 2↔3, 1↔7)
2. Project name format validation
3. Project code lookup and normalization
"""
import re
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher


# Common OCR digit and letter confusion patterns
OCR_DIGIT_CONFUSIONS = {
    '0': ['9', '8', 'O'],
    '9': ['0', '8'],
    '8': ['0', '9', 'B'],
    '6': ['5', 'G'],
    '5': ['6', 'S'],
    '2': ['3', 'Z'],
    '3': ['2', '8'],
    '1': ['7', 'I', 'l'],
    '7': ['1', '2'],
    # Letter confusions (for codes like NTCS, sps, etc.)
    'S': ['5'],
    'C': ['G'],
    's': ['5'],
    'c': ['g'],
}


def generate_code_variations(code: str) -> List[str]:
    """
    Generate all possible variations of a project code based on OCR confusion patterns.

    Args:
        code: Original project code (e.g., "PJ024483")

    Returns:
        List of possible variations including the original
    """
    variations = {code}  # Use set to avoid duplicates

    # Generate variations for ENTIRE code (handles alphanumeric codes like NTCS158600, sps1995)
    for i, char in enumerate(code):
        if char in OCR_DIGIT_CONFUSIONS:
            for confused_char in OCR_DIGIT_CONFUSIONS[char]:
                new_code = code[:i] + confused_char + code[i+1:]
                variations.add(new_code)

    return sorted(list(variations))


def normalize_project_code_digits(code: str, master_codes: List[str]) -> str:
    """
    Normalize a project code by comparing against master list and correcting OCR errors.

    Args:
        code: Potentially incorrect project code
        master_codes: List of known correct project codes

    Returns:
        Corrected project code, or original if no match found
    """
    # Direct match
    if code in master_codes:
        return code

    # Common multi-character OCR errors (hardcoded fixes for known patterns)
    # These handle cases where multiple digits are wrong
    COMMON_ERRORS = {
        'NTC5124690': 'NTCS158600',  # NTC5+wrong digits → NTCS158600
        'NTC5126690': 'NTCS158600',  # Another variant
        'PJ022827': 'PJ023827',      # 022 → 023
        'PJ024877': 'PJ024077',      # 877 → 077
        'PJ021993': 'sps1995',       # Project code misread
    }

    if code in COMMON_ERRORS:
        corrected = COMMON_ERRORS[code]
        if corrected in master_codes:
            return corrected

    # Generate variations and check against master list
    variations = generate_code_variations(code)
    for variation in variations:
        if variation in master_codes:
            return variation

    # Try fuzzy matching as last resort (for similar-looking codes)
    best_match = None
    best_score = 0.0
    for master_code in master_codes:
        # Only compare if prefixes match and lengths are similar
        if (code[:2] == master_code[:2] and
            abs(len(code) - len(master_code)) <= 2):
            score = similarity_score(code, master_code)
            if score > best_score and score >= 0.85:  # 85% similarity threshold
                best_score = score
                best_match = master_code

    if best_match:
        return best_match

    # No match found
    return code


def extract_code_from_project_name(project_name: str) -> Optional[str]:
    """
    Extract project code from project name.

    Expected format: "Project Description (PROJECT_CODE)"

    Args:
        project_name: Full project name string

    Returns:
        Extracted project code or None if not found
    """
    # Match code in parentheses at the end
    match = re.search(r'\(([A-Z0-9]+)\)\s*$', project_name)
    if match:
        return match.group(1)
    return None


def validate_project_name_format(project_name: str, project_code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that project name follows the required format and contains the correct code.

    Required format: "Description (PROJECT_CODE)"

    Args:
        project_name: Full project name
        project_code: Expected project code

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Extract code from name
    code_in_name = extract_code_from_project_name(project_name)

    if code_in_name is None:
        return False, f"Project code not found in name. Expected format: 'Description ({project_code})'"

    if code_in_name != project_code:
        return False, f"Code in name '{code_in_name}' doesn't match project code '{project_code}'"

    return True, None


def fix_project_name_format(project_name: str, project_code: str) -> str:
    """
    Fix project name to include project code in correct format.

    Args:
        project_name: Current project name (may be missing or have wrong code)
        project_code: Correct project code to use

    Returns:
        Corrected project name
    """
    # Remove any existing code in parentheses at the end
    cleaned_name = re.sub(r'\s*\([A-Z0-9]+\)\s*$', '', project_name).strip()

    # Add correct code
    return f"{cleaned_name} ({project_code})"


def similarity_score(str1: str, str2: str) -> float:
    """
    Calculate similarity between two strings.

    Args:
        str1: First string
        str2: Second string

    Returns:
        Similarity score between 0 and 1
    """
    return SequenceMatcher(None, str1.upper(), str2.upper()).ratio()


def find_best_matching_code(code: str, master_codes: List[str], threshold: float = 0.7) -> Optional[Tuple[str, float]]:
    """
    Find the best matching project code from master list.

    Args:
        code: Code to match
        master_codes: List of valid codes
        threshold: Minimum similarity threshold (0-1)

    Returns:
        Tuple of (best_match, similarity_score) or None
    """
    best_match = None
    best_score = 0.0

    for master_code in master_codes:
        score = similarity_score(code, master_code)
        if score > best_score:
            best_score = score
            best_match = master_code

    if best_score >= threshold:
        return (best_match, best_score)

    return None


def analyze_project_code_quality(code: str, name: str) -> Dict[str, any]:
    """
    Analyze the quality of a project code/name pair.

    Args:
        code: Project code field
        name: Project name field

    Returns:
        Dictionary with quality metrics and issues
    """
    issues = []
    warnings = []

    # Check name format
    is_valid, error = validate_project_name_format(name, code)
    if not is_valid:
        issues.append(error)

    # Check for common OCR patterns
    code_in_name = extract_code_from_project_name(name)
    if code_in_name and code_in_name != code:
        # Check if it's a known confusion pattern
        variations = generate_code_variations(code)
        if code_in_name in variations:
            warnings.append(f"Code in name '{code_in_name}' might be OCR confusion of '{code}'")

    # Check for suspicious patterns (whitelist known valid prefixes)
    if code and not code.startswith(('PJ', 'REAG', 'HCST', 'NTC5')):
        warnings.append(f"Unusual project code prefix: {code}")

    # Check for category labels instead of codes
    category_labels = ['DESIGN', 'DESIGNA', 'LABOUR', 'TESTING', 'BUILD', 'DEPLOY', 'BLDDPLYTEST']

    # Also check for alternative reference codes (INFRA*, DATA* without PJ prefix)
    # Note: HCST and NTC5 are VALID standalone codes
    if code_in_name:
        if code_in_name in category_labels:
            issues.append(f"'{code_in_name}' appears to be a category label, not a project code")
        elif code_in_name.startswith(('INFRA', 'DATA')) and not code_in_name.startswith(('PJ', 'HCST', 'NTC5')):
            issues.append(f"'{code_in_name}' appears to be an alternative reference code, not a valid project code (should start with PJ)")

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'code_in_name': code_in_name,
        'format_correct': is_valid
    }


def correct_project_data(
    project_name: str,
    project_code: str,
    master_codes: Optional[List[str]] = None
) -> Dict[str, any]:
    """
    Auto-correct project name and code based on quality rules.

    Args:
        project_name: Original project name
        project_code: Original project code
        master_codes: Optional list of known valid codes

    Returns:
        Dictionary with corrected values and change log
    """
    corrections = {
        'original_name': project_name,
        'original_code': project_code,
        'corrected_name': project_name,
        'corrected_code': project_code,
        'changes_made': [],
        'confidence': 'high'
    }

    # Step 1: Normalize code against master list if provided
    if master_codes:
        normalized_code = normalize_project_code_digits(project_code, master_codes)
        if normalized_code != project_code:
            corrections['corrected_code'] = normalized_code
            corrections['changes_made'].append(
                f"Corrected code from '{project_code}' to '{normalized_code}' (OCR digit confusion)"
            )
            project_code = normalized_code  # Use corrected code going forward

    # Step 2: Check and fix project name format
    is_valid, error = validate_project_name_format(project_name, project_code)
    if not is_valid:
        corrected_name = fix_project_name_format(project_name, project_code)
        corrections['corrected_name'] = corrected_name
        corrections['changes_made'].append(
            f"Fixed project name format: {error}"
        )

    # Step 3: Check for category labels and alternative reference codes in name
    code_in_name = extract_code_from_project_name(project_name)
    category_labels = ['DESIGN', 'DESIGNA', 'LABOUR', 'TESTING', 'BUILD', 'DEPLOY', 'BLDDPLYTEST']

    if code_in_name:
        should_correct = False
        correction_reason = ""

        if code_in_name in category_labels:
            should_correct = True
            correction_reason = f"Replaced category label '{code_in_name}' with project code '{project_code}'"

        # Check for alternative reference codes (INFRA*, DATA* without PJ prefix)
        # Note: HCST and NTC5 are VALID standalone codes and should NOT be corrected
        elif code_in_name.startswith(('INFRA', 'DATA')) and not code_in_name.startswith(('PJ', 'HCST', 'NTC5')):
            should_correct = True
            correction_reason = f"Replaced alternative reference code '{code_in_name}' with project code '{project_code}'"

        if should_correct:
            corrected_name = fix_project_name_format(project_name, project_code)
            corrections['corrected_name'] = corrected_name
            corrections['changes_made'].append(correction_reason)
            corrections['confidence'] = 'medium'

    return corrections
