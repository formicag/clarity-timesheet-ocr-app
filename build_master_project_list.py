#!/usr/bin/env python3
"""
Build master project list from existing DynamoDB data.
This helps establish the authoritative project codes for validation.
"""
import boto3
import sys
import os
from collections import defaultdict
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from project_manager import ProjectManager

# AWS Configuration
DYNAMODB_TABLE = "TimesheetOCR-dev"
AWS_REGION = "us-east-1"


def scan_all_projects():
    """Scan DynamoDB for all unique project codes and names."""
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)

    print("Scanning DynamoDB for all projects...")
    print("This may take a few minutes...")
    print()

    # Track project codes with their variations
    project_data = defaultdict(lambda: {
        'names': defaultdict(int),  # name -> count
        'total_entries': 0
    })

    # Scan entire table
    scan_kwargs = {
        'ProjectionExpression': 'ProjectCode, ProjectName'
    }

    done = False
    start_key = None
    item_count = 0

    while not done:
        if start_key:
            scan_kwargs['ExclusiveStartKey'] = start_key

        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])

        for item in items:
            code = item.get('ProjectCode')
            name = item.get('ProjectName')

            if code and name:
                project_data[code]['names'][name] += 1
                project_data[code]['total_entries'] += 1
                item_count += 1

        start_key = response.get('LastEvaluatedKey')
        done = start_key is None

        # Progress update
        if item_count % 100 == 0:
            print(f"Processed {item_count} entries, found {len(project_data)} unique codes...")

    print(f"\n✅ Scan complete!")
    print(f"Total entries scanned: {item_count}")
    print(f"Unique project codes found: {len(project_data)}")
    print()

    return project_data


def analyze_and_select_canonical(project_data):
    """
    Analyze project data and select the canonical name for each code.
    """
    canonical_projects = []
    variations_detected = []

    for code, data in sorted(project_data.items()):
        names = data['names']

        # Select most common name as canonical
        canonical_name = max(names.items(), key=lambda x: x[1])[0]

        canonical_projects.append({
            'code': code,
            'name': canonical_name,
            'aliases': {
                'codes': [],  # Will be populated by OCR variation detection
                'names': [name for name in names.keys() if name != canonical_name]
            },
            'usage_count': data['total_entries']
        })

        # Report variations
        if len(names) > 1:
            variations_detected.append({
                'code': code,
                'canonical_name': canonical_name,
                'variations': [
                    {'name': name, 'count': count}
                    for name, count in sorted(names.items(), key=lambda x: -x[1])
                ]
            })

    return canonical_projects, variations_detected


def main():
    """Build master project list from DynamoDB."""
    print("=" * 80)
    print("BUILDING MASTER PROJECT LIST FROM DYNAMODB")
    print("=" * 80)
    print()

    # Scan database
    project_data = scan_all_projects()

    # Analyze and select canonical names
    canonical_projects, variations = analyze_and_select_canonical(project_data)

    # Save to project manager
    pm = ProjectManager()
    pm.projects = canonical_projects
    pm.save_master_list()

    print(f"✅ Master project list saved: {pm.master_file}")
    print(f"   Total projects: {len(canonical_projects)}")
    print()

    # Report name variations
    if variations:
        print("=" * 80)
        print(f"NAME VARIATIONS DETECTED ({len(variations)} projects)")
        print("=" * 80)
        print()
        print("The following projects have multiple name variations in the database.")
        print("The most common name has been selected as canonical.")
        print()

        for var in variations[:20]:  # Show first 20
            print(f"Project Code: {var['code']}")
            print(f"Canonical Name: {var['canonical_name']}")
            print(f"Variations found:")
            for v in var['variations']:
                marker = "✓" if v['name'] == var['canonical_name'] else " "
                print(f"  {marker} {v['name']} ({v['count']} entries)")
            print()

        if len(variations) > 20:
            print(f"... and {len(variations) - 20} more projects with variations")
            print()

    # Save detailed report
    report_file = "project_variations_report.json"
    with open(report_file, 'w') as f:
        json.dump({
            'total_projects': len(canonical_projects),
            'projects_with_variations': len(variations),
            'variations': variations
        }, f, indent=2)

    print(f"📊 Detailed report saved: {report_file}")
    print()

    # Summary statistics
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print()

    # Count projects by prefix
    pj_count = sum(1 for p in canonical_projects if p['code'].startswith('PJ'))
    reag_count = sum(1 for p in canonical_projects if p['code'].startswith('REAG'))
    other_count = len(canonical_projects) - pj_count - reag_count

    print(f"Projects by code prefix:")
    print(f"  PJ*:    {pj_count}")
    print(f"  REAG*:  {reag_count}")
    print(f"  Other:  {other_count}")
    print()

    # Most used projects
    top_projects = sorted(canonical_projects, key=lambda x: x['usage_count'], reverse=True)[:10]
    print("Top 10 most used projects:")
    for i, p in enumerate(top_projects, 1):
        print(f"  {i}. {p['code']}: {p['name'][:60]}... ({p['usage_count']} entries)")
    print()

    print("=" * 80)
    print("✅ MASTER PROJECT LIST BUILD COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Review project_master.json for accuracy")
    print("2. Review project_variations_report.json for name inconsistencies")
    print("3. Update the OCR system will now use this as the authoritative list")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
