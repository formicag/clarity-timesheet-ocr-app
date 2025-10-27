"""
OCR Solution Version Tracking

Tracks the version of the OCR solution to enable:
- Identifying stale data that needs reprocessing
- Comparing results between versions
- Automatic data refresh when version changes
"""
import os
from pathlib import Path


def get_ocr_version():
    """
    Read the current OCR solution version from OCR_VERSION.txt

    Returns:
        dict with version info:
        {
            'version': '2.0.0',
            'build_date': '2025-10-25',
            'description': 'Amazon Nova Lite + Coverage Tracking',
            'full_version': '2.0.0-2025-10-25'
        }
    """
    # Try to find OCR_VERSION.txt
    # First try relative to this file
    version_file = Path(__file__).parent.parent / 'OCR_VERSION.txt'

    if not version_file.exists():
        # Fallback to hardcoded version
        return {
            'version': '2.0.0',
            'build_date': '2025-10-25',
            'description': 'Amazon Nova Lite + Coverage Tracking',
            'full_version': '2.0.0-2025-10-25'
        }

    try:
        with open(version_file, 'r') as f:
            lines = f.readlines()

        version_info = {}
        for line in lines:
            line = line.strip()
            if line.startswith('VERSION='):
                version_info['version'] = line.split('=', 1)[1]
            elif line.startswith('BUILD_DATE='):
                version_info['build_date'] = line.split('=', 1)[1]
            elif line.startswith('DESCRIPTION='):
                version_info['description'] = line.split('=', 1)[1]

        # Create full version string
        version_info['full_version'] = f"{version_info.get('version', 'unknown')}-{version_info.get('build_date', 'unknown')}"

        return version_info

    except Exception as e:
        print(f"⚠️  Could not read OCR_VERSION.txt: {e}")
        # Return fallback
        return {
            'version': '2.0.0',
            'build_date': '2025-10-25',
            'description': 'Amazon Nova Lite + Coverage Tracking',
            'full_version': '2.0.0-2025-10-25'
        }


def is_version_newer(version_a: str, version_b: str) -> bool:
    """
    Compare two version strings to determine if A is newer than B.

    Args:
        version_a: Version string (e.g., "2.0.0")
        version_b: Version string (e.g., "1.5.0")

    Returns:
        True if version_a is newer than version_b
    """
    try:
        # Parse versions
        parts_a = [int(x) for x in version_a.split('.')]
        parts_b = [int(x) for x in version_b.split('.')]

        # Pad to same length
        while len(parts_a) < len(parts_b):
            parts_a.append(0)
        while len(parts_b) < len(parts_a):
            parts_b.append(0)

        # Compare
        for a, b in zip(parts_a, parts_b):
            if a > b:
                return True
            elif a < b:
                return False

        return False  # Equal versions

    except:
        # If parsing fails, compare as strings
        return version_a > version_b


def should_reprocess_entry(entry_version: str, current_version: str = None) -> bool:
    """
    Determine if a database entry should be reprocessed based on its OCR version.

    Args:
        entry_version: The OCR version that created this entry
        current_version: Current OCR version (auto-detected if not provided)

    Returns:
        True if entry should be reprocessed with current OCR
    """
    if current_version is None:
        current_version = get_ocr_version()['version']

    # If entry has no version, it's old data - should reprocess
    if not entry_version:
        return True

    # If current version is newer, should reprocess
    return is_version_newer(current_version, entry_version)


# Get version on module load for easy access
OCR_VERSION = get_ocr_version()
