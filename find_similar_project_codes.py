#!/usr/bin/env python3
"""
Find similar project codes that might be OCR errors.

Examples:
- PJ024542 vs PJ024642 (5 misread as 6)
- PJ023275 vs PJ928275 (0 misread as 9)

Strategy:
- For each person/date combination, find all project codes
- Check if any two codes are "similar" (Levenshtein distance <= 2)
- These are likely OCR errors of the same project
"""
import boto3
from collections import defaultdict
from difflib import SequenceMatcher

# AWS Configuration
REGION = 'us-east-1'
TABLE_NAME = 'TimesheetOCR-dev'

# Initialize AWS clients
dynamodb = boto3.client('dynamodb', region_name=REGION)


def levenshtein_distance(s1, s2):
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def get_all_resources():
    """Get all unique ResourceName values."""
    print("📋 Scanning for all unique resources...")

    resources = set()
    scan_kwargs = {
        'TableName': TABLE_NAME,
        'ProjectionExpression': 'ResourceName'
    }

    while True:
        response = dynamodb.scan(**scan_kwargs)
        for item in response.get('Items', []):
            resources.add(item['ResourceName']['S'])

        if 'LastEvaluatedKey' not in response:
            break
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    return sorted(resources)


def get_all_entries_for_resource(resource_name):
    """Get all entries for a specific resource."""
    query_kwargs = {
        'TableName': TABLE_NAME,
        'KeyConditionExpression': 'ResourceName = :rn',
        'ExpressionAttributeValues': {
            ':rn': {'S': resource_name}
        }
    }

    entries = []
    while True:
        response = dynamodb.query(**query_kwargs)
        entries.extend(response.get('Items', []))

        if 'LastEvaluatedKey' not in response:
            break
        query_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    return entries


def find_similar_codes_for_resource(resource_name):
    """
    Find dates where similar project codes exist.

    Returns:
        List of (date, code1, code2, details1, details2) tuples
    """
    entries = get_all_entries_for_resource(resource_name)

    # Group by date
    by_date = defaultdict(list)

    for entry in entries:
        # Skip zero-hour timesheets
        date_project_code = entry.get('DateProjectCode', {}).get('S', '')
        if date_project_code.startswith('WEEK#'):
            continue

        # Extract date and project code
        if '#' not in date_project_code:
            continue

        parts = date_project_code.split('#')
        if len(parts) != 2:
            continue

        date_str = parts[0]
        project_code = parts[1]

        by_date[date_str].append((project_code, entry))

    # Find similar codes on same date
    similar_pairs = []

    for date_str, projects in by_date.items():
        # Compare all pairs of project codes for this date
        for i in range(len(projects)):
            for j in range(i + 1, len(projects)):
                code1, entry1 = projects[i]
                code2, entry2 = projects[j]

                # Skip if codes are identical (handled by other script)
                if code1 == code2:
                    continue

                # Check if codes are similar (Levenshtein distance <= 2)
                distance = levenshtein_distance(code1, code2)

                if distance <= 2:
                    # NEW: Check if project names are also similar
                    # This reduces false positives from legitimate different projects
                    project_name1 = entry1.get('ProjectName', {}).get('S', '')
                    project_name2 = entry2.get('ProjectName', {}).get('S', '')

                    # Extract base project names (remove code in parentheses)
                    base_name1 = project_name1.split('(')[0].strip().lower() if '(' in project_name1 else project_name1.lower()
                    base_name2 = project_name2.split('(')[0].strip().lower() if '(' in project_name2 else project_name2.lower()

                    # Calculate name similarity (simple approach: check if one contains the other or significant overlap)
                    name_similarity = SequenceMatcher(None, base_name1, base_name2).ratio()

                    # Only flag if BOTH codes are similar AND names are very similar (>70%)
                    # This catches: "Roaming Bar" vs "Roaming Bar" ✓
                    # This skips: "ICT platform upgrade" vs "Test Environment" ✗
                    if name_similarity < 0.7:
                        continue  # Skip - these are legitimately different projects
                    # Found similar codes!
                    details1 = {
                        'code': code1,
                        'hours': entry1.get('Hours', {}).get('N', '0'),
                        'source': entry1.get('SourceImage', {}).get('S', 'unknown'),
                        'timestamp': entry1.get('ProcessingTimestamp', {}).get('S', ''),
                        'project_name': entry1.get('ProjectName', {}).get('S', ''),
                        'name_similarity': name_similarity
                    }

                    details2 = {
                        'code': code2,
                        'hours': entry2.get('Hours', {}).get('N', '0'),
                        'source': entry2.get('SourceImage', {}).get('S', 'unknown'),
                        'timestamp': entry2.get('ProcessingTimestamp', {}).get('S', ''),
                        'project_name': entry2.get('ProjectName', {}).get('S', ''),
                        'name_similarity': name_similarity
                    }

                    similar_pairs.append((date_str, distance, details1, details2))

    return similar_pairs


def highlight_difference(s1, s2):
    """Highlight the character differences between two strings."""
    result1 = []
    result2 = []

    matcher = SequenceMatcher(None, s1, s2)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            result1.append(s1[i1:i2])
            result2.append(s2[j1:j2])
        elif tag == 'replace':
            result1.append(f"[{s1[i1:i2]}]")
            result2.append(f"[{s2[j1:j2]}]")
        elif tag == 'delete':
            result1.append(f"[{s1[i1:i2]}]")
        elif tag == 'insert':
            result2.append(f"[{s2[j1:j2]}]")

    return ''.join(result1), ''.join(result2)


def main():
    """Main execution."""
    print("=" * 80)
    print("         FIND SIMILAR PROJECT CODES (OCR ERRORS)")
    print("=" * 80)
    print()
    print("This script finds cases where similar project codes exist for")
    print("the same person on the same date, which likely indicates OCR errors.")
    print()
    print("🔍 FILTERING: Only flags codes with:")
    print("   • Levenshtein distance ≤ 2 (similar codes)")
    print("   • Project name similarity ≥ 70% (same/similar project)")
    print()
    print("This reduces false positives from legitimately different projects.")
    print()
    print("Example DETECTED: PJ024542 vs PJ024642 both 'Roaming Bar' (5 misread as 6)")
    print("Example SKIPPED: PJ922377 'ICT platform' vs PJ924077 'Test Environment'")
    print()

    # Get all resources
    resources = get_all_resources()
    print(f"✅ Found {len(resources)} unique resources\n")

    print("=" * 80)
    print("SCANNING FOR SIMILAR PROJECT CODES")
    print("=" * 80)
    print()

    total_similar = 0
    all_similar_pairs = []

    for resource in resources:
        similar_pairs = find_similar_codes_for_resource(resource)

        if len(similar_pairs) > 0:
            display_name = resource.replace('_', ' ')
            print(f"\n👤 {display_name}")
            print(f"   Found {len(similar_pairs)} similar code pairs")

            for date_str, distance, details1, details2 in similar_pairs:
                print(f"\n   📅 {date_str}")

                # Highlight differences
                highlighted1, highlighted2 = highlight_difference(details1['code'], details2['code'])

                print(f"      Code 1: {highlighted1}")
                print(f"         Hours: {details1['hours']}h")
                print(f"         Source: {details1['source']}")
                print(f"         Project: {details1['project_name']}")
                print(f"         Timestamp: {details1['timestamp']}")

                print(f"      Code 2: {highlighted2}")
                print(f"         Hours: {details2['hours']}h")
                print(f"         Source: {details2['source']}")
                print(f"         Project: {details2['project_name']}")
                print(f"         Timestamp: {details2['timestamp']}")

                print(f"      Levenshtein distance: {distance}")

                total_similar += 1

            all_similar_pairs.append((resource, similar_pairs))

    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Resources with similar codes: {len(all_similar_pairs)}")
    print(f"Total similar code pairs found: {total_similar}")

    if total_similar == 0:
        print("\n✅ No similar project codes found!")
    else:
        print("\n⚠️  These similar codes may indicate OCR errors.")
        print("   Review the source images to determine the correct project code.")
        print("   Then delete the incorrect entries manually or update the images.")


if __name__ == '__main__':
    main()
