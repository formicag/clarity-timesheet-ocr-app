#!/usr/bin/env python3
"""
Generate comprehensive OCR quality report based on analysis findings.
Identifies and reports on project code/name quality issues.
"""
import boto3
import sys
import os
from collections import defaultdict
import csv
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from project_code_correction import (
    validate_project_name_format,
    analyze_project_code_quality,
    extract_code_from_project_name,
    generate_code_variations
)

# AWS Configuration
DYNAMODB_TABLE = "TimesheetOCR-dev"
AWS_REGION = "us-east-1"


def scan_and_analyze_quality():
    """Scan DynamoDB and analyze project code quality."""
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)

    print("Scanning DynamoDB for quality analysis...")
    print()

    issues = []
    warnings = []
    stats = {
        'total_records': 0,
        'format_violations': 0,
        'category_label_codes': 0,
        'missing_codes_in_name': 0,
        'wrong_codes_in_name': 0,
        'suspected_ocr_errors': 0
    }

    # Scan entire table
    scan_kwargs = {
        'ProjectionExpression': 'ResourceName, #d, ProjectCode, ProjectName, SourceImage',
        'ExpressionAttributeNames': {
            '#d': 'Date'
        }
    }

    done = False
    start_key = None

    while not done:
        if start_key:
            scan_kwargs['ExclusiveStartKey'] = start_key

        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])

        for item in items:
            stats['total_records'] += 1
            resource = item.get('ResourceName', '')
            date = item.get('Date', '')  # Date is already extracted, just reference it
            code = item.get('ProjectCode', '')
            name = item.get('ProjectName', '')
            image = item.get('SourceImage', '')

            if not code or not name:
                continue

            # Analyze quality
            quality = analyze_project_code_quality(code, name)

            if not quality['valid']:
                stats['format_violations'] += 1
                for issue in quality['issues']:
                    issues.append({
                        'type': 'FORMAT_VIOLATION',
                        'resource': resource,
                        'date': date,
                        'code': code,
                        'name': name,
                        'issue': issue,
                        'image': image
                    })

                    # Categorize the issue
                    if 'category label' in issue.lower():
                        stats['category_label_codes'] += 1
                    elif 'not found' in issue.lower():
                        stats['missing_codes_in_name'] += 1
                    elif "doesn't match" in issue.lower():
                        stats['wrong_codes_in_name'] += 1

            if quality['warnings']:
                stats['suspected_ocr_errors'] += 1
                for warning in quality['warnings']:
                    warnings.append({
                        'type': 'WARNING',
                        'resource': resource,
                        'date': date,
                        'code': code,
                        'name': name,
                        'warning': warning,
                        'image': image
                    })

            # Check for leading 9 (common OCR error)
            if code.startswith('PJ9'):
                stats['suspected_ocr_errors'] += 1
                warnings.append({
                    'type': 'SUSPECTED_OCR_ERROR',
                    'resource': resource,
                    'date': date,
                    'code': code,
                    'name': name,
                    'warning': f"Starts with PJ9 (rare) - might be PJ0{code[3:]}",
                    'image': image
                })

        start_key = response.get('LastEvaluatedKey')
        done = start_key is None

        if stats['total_records'] % 100 == 0:
            print(f"Processed {stats['total_records']} records...")

    print(f"\n✅ Scan complete! Processed {stats['total_records']} records")
    print()

    return issues, warnings, stats


def generate_corrections_csv(issues):
    """Generate CSV file with corrections needed."""
    filename = f"corrections_needed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Resource Name',
            'Date',
            'Current Project Code',
            'Current Project Name',
            'Issue Type',
            'Issue Description',
            'Source Image'
        ])

        for issue in issues:
            writer.writerow([
                issue['resource'],
                issue['date'],
                issue['code'],
                issue['name'],
                issue['type'],
                issue['issue'],
                issue['image']
            ])

    return filename


def print_executive_summary(issues, warnings, stats):
    """Print executive summary of quality issues."""
    print("=" * 80)
    print("OCR DATA QUALITY REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print("SUMMARY STATISTICS")
    print("-" * 80)
    print(f"Total Records Analyzed:        {stats['total_records']:,}")
    print(f"Format Violations:             {stats['format_violations']:,} ({stats['format_violations']/stats['total_records']*100:.1f}%)")
    print(f"  - Missing codes in name:     {stats['missing_codes_in_name']:,}")
    print(f"  - Wrong codes in name:       {stats['wrong_codes_in_name']:,}")
    print(f"  - Category labels as codes:  {stats['category_label_codes']:,}")
    print(f"Suspected OCR Errors:          {stats['suspected_ocr_errors']:,}")
    print()

    if issues:
        print("=" * 80)
        print(f"FORMAT VIOLATIONS ({len(issues)} records need correction)")
        print("=" * 80)
        print()

        # Group by resource
        by_resource = defaultdict(list)
        for issue in issues:
            by_resource[issue['resource']].append(issue)

        print("Records needing correction by person:")
        for resource, resource_issues in sorted(by_resource.items(), key=lambda x: -len(x[1]))[:10]:
            print(f"  {resource}: {len(resource_issues)} records")
        print()

        # Show sample issues
        print("Sample Issues (first 10):")
        print("-" * 80)
        for i, issue in enumerate(issues[:10], 1):
            print(f"\n{i}. {issue['resource']} - {issue['date']}")
            print(f"   Code: {issue['code']}")
            print(f"   Name: {issue['name']}")
            print(f"   Issue: {issue['issue']}")

        if len(issues) > 10:
            print(f"\n... and {len(issues) - 10} more issues")

    if warnings:
        print()
        print("=" * 80)
        print(f"WARNINGS & SUSPECTED OCR ERRORS ({len(warnings)} records)")
        print("=" * 80)
        print()

        # Show sample warnings
        print("Sample Warnings (first 10):")
        print("-" * 80)
        for i, warning in enumerate(warnings[:10], 1):
            print(f"\n{i}. {warning['resource']} - {warning['date']}")
            print(f"   Code: {warning['code']}")
            print(f"   Warning: {warning['warning']}")

        if len(warnings) > 10:
            print(f"\n... and {len(warnings) - 10} more warnings")

    print()
    print("=" * 80)


def main():
    """Generate quality report."""
    print("=" * 80)
    print("GENERATING OCR QUALITY REPORT")
    print("=" * 80)
    print()

    # Scan and analyze
    issues, warnings, stats = scan_and_analyze_quality()

    # Generate corrections CSV
    if issues:
        corrections_file = generate_corrections_csv(issues)
        print(f"✅ Corrections CSV generated: {corrections_file}")
        print()

    # Print summary
    print_executive_summary(issues, warnings, stats)

    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()
    if stats['format_violations'] > 0:
        print(f"1. Fix {stats['format_violations']} format violations using corrections CSV")
        print("2. Deploy updated OCR system with enhanced validation")
        print("3. Reprocess affected timesheets to apply corrections")
    else:
        print("✅ No format violations found! Project codes are in good shape.")

    if stats['suspected_ocr_errors'] > 0:
        print(f"4. Review {stats['suspected_ocr_errors']} suspected OCR digit errors")
        print("   - Focus on PJ9* codes (likely should be PJ0*)")
        print("   - Check against master project list")

    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
