#!/usr/bin/env python3
"""
Interactive tool to add projects to master list
"""
import json
import sys
from pathlib import Path

def load_master_list():
    """Load existing master list"""
    if Path('project_master.json').exists():
        with open('project_master.json', 'r') as f:
            return json.load(f)
    else:
        return {
            'projects': [],
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
        }

def save_master_list(data):
    """Save master list"""
    with open('project_master.json', 'w') as f:
        json.dump(data, f, indent=2)

def add_project_interactive():
    """Interactive project addition"""
    print("=" * 80)
    print("Add Project to Master List")
    print("=" * 80)
    print()

    # Load existing data
    data = load_master_list()
    existing_codes = {p['code'] for p in data['projects']}

    print(f"Current master list has {len(data['projects'])} projects")
    print()

    while True:
        # Get project code
        code = input("Enter project code (or 'done' to finish): ").strip()

        if code.lower() == 'done':
            break

        if not code:
            print("❌ Project code cannot be empty")
            continue

        # Normalize code
        code = code.replace(' ', '').upper()

        if code in existing_codes:
            print(f"❌ Project {code} already exists")
            print()
            continue

        # Get project name
        name = input("Enter project name: ").strip()

        if not name:
            print("❌ Project name cannot be empty")
            continue

        # Confirm
        print()
        print(f"Adding project:")
        print(f"  Code: {code}")
        print(f"  Name: {name}")
        confirm = input("Confirm? (y/n): ").strip().lower()

        if confirm == 'y':
            data['projects'].append({
                'code': code,
                'name': name,
                'aliases': {
                    'codes': [],
                    'names': []
                }
            })
            existing_codes.add(code)
            print(f"✓ Added {code}")
        else:
            print("❌ Cancelled")

        print()

    # Sort projects by code
    data['projects'].sort(key=lambda x: x['code'])

    # Save
    save_master_list(data)

    print()
    print("=" * 80)
    print(f"✓ Project master list updated!")
    print(f"  Total projects: {len(data['projects'])}")
    print()
    print("Projects in master list:")
    for p in data['projects']:
        print(f"  {p['code']}: {p['name']}")
    print()

def add_project_from_args():
    """Add project from command line arguments"""
    if len(sys.argv) < 3:
        print("Usage: python3 add_project.py <code> <name>")
        print("   or: python3 add_project.py  (for interactive mode)")
        sys.exit(1)

    code = sys.argv[1].strip().replace(' ', '').upper()
    name = ' '.join(sys.argv[2:]).strip()

    data = load_master_list()
    existing_codes = {p['code'] for p in data['projects']}

    if code in existing_codes:
        print(f"❌ Project {code} already exists")
        sys.exit(1)

    data['projects'].append({
        'code': code,
        'name': name,
        'aliases': {
            'codes': [],
            'names': []
        }
    })

    data['projects'].sort(key=lambda x: x['code'])
    save_master_list(data)

    print(f"✓ Added {code}: {name}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        add_project_from_args()
    else:
        add_project_interactive()
