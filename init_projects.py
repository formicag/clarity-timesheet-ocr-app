#!/usr/bin/env python3
"""
Initialize project master list manually
Use this BEFORE you have DynamoDB data
"""
import json

def init_project_master():
    """Create initial project master list"""

    print("=" * 80)
    print("Project Master List Initialization")
    print("=" * 80)
    print()
    print("This will create an empty project_master.json file.")
    print("You can then add your known projects manually or via the UI.")
    print()

    # Create template
    template = {
        "projects": [
            {
                "code": "EXAMPLE001",
                "name": "Example Project One",
                "aliases": {
                    "codes": ["EX001"],
                    "names": ["Example Proj One"]
                }
            }
        ],
        "normalization_rules": {
            "code_patterns": {
                "remove_spaces": True,
                "uppercase": True,
                "zero_vs_o": True
            },
            "name_patterns": {
                "trim_whitespace": True,
                "normalize_spaces": True,
                "title_case": True
            }
        }
    }

    # Save to file
    with open('project_master.json', 'w') as f:
        json.dump(template, f, indent=2)

    print("✓ Created project_master.json with example project")
    print()
    print("Next steps:")
    print()
    print("Option 1: Edit project_master.json manually")
    print("  - Open project_master.json in a text editor")
    print("  - Replace the example with your actual projects")
    print("  - Save the file")
    print()
    print("Option 2: Add projects one by one")
    print("  - Run: python3 add_project.py")
    print("  - Enter project code and name when prompted")
    print()
    print("Option 3: Start with empty list")
    print("  - Delete the example project from project_master.json")
    print("  - Let the system learn from your first OCR batch")
    print("  - Review and add aliases as you see variations")
    print()
    print("Format for adding projects:")
    print("""
{
  "code": "P001",
  "name": "Your Project Name",
  "aliases": {
    "codes": [],
    "names": []
  }
}
""")
    print()
    print("=" * 80)

if __name__ == "__main__":
    init_project_master()
