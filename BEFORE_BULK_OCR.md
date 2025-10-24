# Before Bulk OCR - Setup Guide

Since you haven't deployed/processed timesheets yet, this is the **perfect time** to set up your project master list to prevent duplicates from the start!

## Quick Start

### Step 1: Initialize Project Master List

```bash
python3 init_projects.py
```

This creates an empty `project_master.json` with example format.

### Step 2: Add Your Known Projects

You have 3 options:

#### Option A: Interactive Entry (Recommended for a few projects)

```bash
python3 add_project.py
```

Then enter projects one by one:
```
Enter project code: P001
Enter project name: Website Redesign
Confirm? (y/n): y
✓ Added P001

Enter project code: P002
Enter project name: Mobile App Development
Confirm? (y/n): y
✓ Added P002

Enter project code: done
```

#### Option B: Command Line (Quick for known projects)

```bash
python3 add_project.py P001 "Website Redesign"
python3 add_project.py P002 "Mobile App Development"
python3 add_project.py P003 "Database Migration"
```

#### Option C: Edit JSON Directly (For many projects)

Open `project_master.json` in a text editor:

```json
{
  "projects": [
    {
      "code": "P001",
      "name": "Website Redesign",
      "aliases": {
        "codes": [],
        "names": []
      }
    },
    {
      "code": "P002",
      "name": "Mobile App Development",
      "aliases": {
        "codes": [],
        "names": []
      }
    }
  ],
  "normalization_rules": {
    "code_patterns": {
      "remove_spaces": true,
      "uppercase": true,
      "zero_vs_o": true
    },
    "name_patterns": {
      "trim_whitespace": true,
      "normalize_spaces": true,
      "title_case": true
    }
  }
}
```

### Step 3: Deploy Infrastructure

```bash
./deploy.sh dev apply
```

### Step 4: Test with Sample Timesheets

Process 2-3 timesheets first:
1. Launch UI: `./launch_ui.command`
2. Upload a few test timesheets
3. Check the database to verify projects are correct

### Step 5: Review and Refine

If you see any OCR variations:
1. Note the incorrect version (e.g., "PO01" instead of "P001")
2. Add it as an alias in `project_master.json`:

```json
{
  "code": "P001",
  "name": "Website Redesign",
  "aliases": {
    "codes": ["PO01", "P0O1"],
    "names": ["Website Redesig", "Web Redesign"]
  }
}
```

### Step 6: Proceed with Bulk OCR

Now you can process timesheets with confidence!

## Don't Know Your Projects Yet?

**That's OK!** You can:

1. **Start with empty list** - Let first OCR batch populate it
2. **After first batch** - Run `python3 analyze_projects.py`
3. **Review output** - See what projects were found
4. **Set canonical names** - Create proper master list
5. **Continue OCR** - Future batches will normalize correctly

## Example: Starting from Scratch

```bash
# Initialize empty project list
python3 init_projects.py

# Edit project_master.json to remove example, leaving:
{
  "projects": [],
  "normalization_rules": { ... }
}

# Deploy infrastructure
./deploy.sh dev apply

# Process first 10 timesheets
# (via UI)

# Analyze what was found
python3 analyze_projects.py

# Review project_master_suggested.json
# Copy it to become active:
cp project_master_suggested.json project_master.json

# Continue with bulk OCR
# Projects will now normalize correctly
```

## Best Practices for Project Codes

### ✅ Good Project Codes
- `P001`, `P002`, `P003` - Padded numbers
- `WEB-2025-Q1` - Descriptive with year/quarter
- `CLIENT-PROJ-001` - Client-Project-Number
- `ALPHA`, `BETA`, `GAMMA` - Greek letters (clear)

### ❌ Avoid These
- `P1`, `P2` - No padding (sorting issues)
- `PO1`, `IO1` - Ambiguous (O vs 0, I vs 1)
- `PROJECT1` - Too long, prone to typos
- `A001`, `B001` - A vs Alpha confusion

## Best Practices for Project Names

### ✅ Good Project Names
- `Website Redesign Q1 2025` - Specific with timeline
- `Mobile App - iOS Development` - Platform specified
- `Database Migration - PostgreSQL` - Technology included
- `Acme Corp - ERP Implementation` - Client and type

### ❌ Avoid These
- `Website` - Too generic
- `Project Alpha` - Vague
- `The New System` - Ambiguous
- `Q1 Work` - Not specific

## What If I Make a Mistake?

No problem! You can always:

1. **Update master list** - Edit `project_master.json`
2. **Export database** - `📥 Export Full Data`
3. **Fix in CSV** - Find/replace incorrect codes/names
4. **Import corrections** - `📤 Import Corrections`
5. **Update aliases** - Add the mistake as an alias

## Summary

**Best approach for starting fresh:**

1. ✅ `python3 init_projects.py` - Create empty list
2. ✅ Add known projects if you have them
3. ✅ Deploy infrastructure
4. ✅ Process 5-10 test timesheets
5. ✅ Run `python3 analyze_projects.py`
6. ✅ Review and refine master list
7. ✅ Proceed with bulk OCR

**Result:** Clean, consistent project data from day one!
