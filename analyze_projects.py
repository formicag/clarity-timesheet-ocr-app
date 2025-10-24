#!/usr/bin/env python3
"""
Analyze existing DynamoDB data to suggest project master list
Run this before bulk OCR to establish baseline projects
"""
import boto3
import json
from collections import defaultdict
from src.project_manager import ProjectManager

DYNAMODB_TABLE = "TimesheetOCR-dev"

def analyze_existing_projects():
    """Scan database and suggest project master list"""

    print("Analyzing existing timesheet data...")
    print("=" * 80)

    # Connect to DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table(DYNAMODB_TABLE)

    # Scan table
    response = table.scan()
    items = response.get('Items', [])

    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))

    print(f"✓ Found {len(items)} timesheet entries\n")

    # Extract unique projects
    projects = defaultdict(lambda: {'names': set(), 'count': 0})

    for item in items:
        code = item.get('ProjectCode', '')
        name = item.get('ProjectName', '')

        if code and name:
            projects[code]['names'].add(name)
            projects[code]['count'] += 1

    # Display findings
    print(f"Found {len(projects)} unique project codes:\n")

    suggested_projects = []

    for code in sorted(projects.keys()):
        data = projects[code]
        names = data['names']
        count = data['count']

        # Show the project
        print(f"Code: {code}")
        print(f"  Entries: {count}")
        print(f"  Names used ({len(names)}):")
        for name in sorted(names):
            print(f"    - {name}")

        # Suggest canonical name (most common or first alphabetically)
        canonical_name = sorted(names)[0]

        suggested_projects.append({
            'code': code,
            'name': canonical_name,
            'aliases': {
                'codes': [],
                'names': [n for n in sorted(names) if n != canonical_name]
            }
        })

        if len(names) > 1:
            print(f"  ⚠️  WARNING: Multiple name variations detected!")
            print(f"  → Suggested canonical: {canonical_name}")

        print()

    # Save suggestion to file
    suggestion_file = 'project_master_suggested.json'
    with open(suggestion_file, 'w') as f:
        json.dump({
            'projects': suggested_projects,
            'normalization_rules': {
                'code_patterns': {
                    'remove_spaces': True,
                    'uppercase': True,
                    'zero_vs_o': True
                },
                'name_patterns': {
                    'trim_whitespace': True,
                    'normalize_spaces': True,
                    'title_case': True
                }
            }
        }, f, indent=2)

    print("=" * 80)
    print(f"\n✓ Analysis complete!")
    print(f"\nSuggested master list saved to: {suggestion_file}")
    print(f"\nNext steps:")
    print(f"1. Review {suggestion_file}")
    print(f"2. Edit to set canonical names for projects with variations")
    print(f"3. Copy to project_master.json to use as master list")
    print(f"4. Or import via UI: Team Management → Projects tab")
    print()

    # Show summary
    multi_name_projects = [p for p in suggested_projects if p['aliases']['names']]
    if multi_name_projects:
        print(f"⚠️  {len(multi_name_projects)} projects have multiple name variations:")
        for p in multi_name_projects:
            print(f"   {p['code']}: {len(p['aliases']['names']) + 1} variations")
        print()

if __name__ == "__main__":
    try:
        analyze_existing_projects()
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure:")
        print("1. AWS credentials are configured (aws sso login)")
        print("2. DynamoDB table exists and has data")
