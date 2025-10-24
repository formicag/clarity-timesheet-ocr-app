# Project Code/Name Management Guide

## Problem

OCR can create multiple variations of the same project due to minor errors:
- Extra spaces: `"Project Alpha"` vs `"Project  Alpha"`
- O vs 0: `"P001"` vs `"PO01"`
- Case differences: `"ALPHA"` vs `"Alpha"`
- Typos: `"Project Aplha"` vs `"Project Alpha"`

This leads to:
- Duplicate projects in database
- Confusing reports
- Data quality issues
- Difficulty tracking hours per project

## Solution

**Project Master List** - A canonical list of project codes and names that:
1. Defines the "correct" code and name for each project
2. Automatically normalizes OCR variations
3. Maps known aliases to canonical names
4. Uses fuzzy matching to catch similar variations

## Before Bulk OCR - Establish Baseline

### Step 1: Analyze Existing Data

Run the analysis script to see what projects you already have:

```bash
python3 analyze_projects.py
```

This will:
- Scan your DynamoDB table
- Find all unique project codes
- Show you name variations for each code
- Generate `project_master_suggested.json`

**Example Output:**
```
Found 15 unique project codes:

Code: P001
  Entries: 45
  Names used (2):
    - Project Alpha
    - Project  Alpha
  ⚠️  WARNING: Multiple name variations detected!
  → Suggested canonical: Project Alpha

Code: P002
  Entries: 23
  Names used (1):
    - Project Beta
```

### Step 2: Review and Edit Suggestions

Open `project_master_suggested.json` and review:

```json
{
  "projects": [
    {
      "code": "P001",
      "name": "Project Alpha",
      "aliases": {
        "codes": [],
        "names": ["Project  Alpha"]
      }
    }
  ]
}
```

Edit to set your preferred canonical names.

### Step 3: Activate Master List

Copy the reviewed file to become your active master list:

```bash
cp project_master_suggested.json project_master.json
```

## How It Works

### Normalization Rules

**For Project Codes:**
- Remove all spaces: `"P 001"` → `"P001"`
- Uppercase: `"p001"` → `"P001"`
- O vs 0 detection: `"PO01"` matches `"P001"` (95% similarity)

**For Project Names:**
- Trim whitespace: `"  Alpha  "` → `"Alpha"`
- Normalize spaces: `"Project  Alpha"` → `"Project Alpha"`
- Title case: `"project alpha"` → `"Project Alpha"`

### Matching Process

When OCR extracts a project, the system:

1. **Exact Match** - Check if code exists in master list
2. **Alias Match** - Check if it's a known alias
3. **Fuzzy Match on Code** (95% threshold)
   - Handles O vs 0, I vs 1, S vs 5
   - `"PO01"` → `"P001"` (98% match) ✓
4. **Fuzzy Match on Name** (90% threshold)
   - `"Project Aplha"` → `"Project Alpha"` (92% match) ✓
5. **New Project** - If no match, use normalized version

### Confidence Levels

- **1.0 (100%)** - Exact or alias match
- **0.95+** - Very likely same project (auto-correct)
- **0.90-0.95** - Probably same project (auto-correct with logging)
- **< 0.90** - Different project (keep as new)

## Managing Your Project List

### Add a New Project

```json
{
  "code": "P003",
  "name": "Project Gamma",
  "aliases": {
    "codes": [],
    "names": []
  }
}
```

### Add Aliases for Known Variations

If you know OCR sometimes reads "P001" as "PO01":

```json
{
  "code": "P001",
  "name": "Project Alpha",
  "aliases": {
    "codes": ["PO01", "P0O1"],
    "names": ["Project Alfa", "Proj Alpha"]
  }
}
```

### Update Normalization Rules

Edit the rules section in `project_master.json`:

```json
{
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

## Best Practices

### 1. Establish Baseline Before Bulk OCR

- Run `analyze_projects.py` on your existing data
- Review and clean up any existing variations
- Create your master list
- **Then** start bulk OCR

### 2. Be Consistent with Project Codes

- Use a format: `P001`, `P002`, etc.
- Avoid ambiguous characters: Use 0 (zero) not O (letter)
- Pad with zeros: `P001` not `P1`

### 3. Standardize Project Names

- Decide on a format: Title Case, ALL CAPS, etc.
- Be specific: "Website Redesign Q1 2025" not "Website"
- Avoid special characters that OCR might misread

### 4. Review OCR Output Regularly

- Check for new projects appearing
- Add them to master list if legitimate
- Add aliases if they're variations

### 5. Use Export/Import for Cleanup

If you already have duplicates:

1. Export full database
2. Find/replace project codes/names in CSV
3. Import corrections
4. Add aliases to prevent recurrence

## Finding Duplicates

### Method 1: Analysis Script

```bash
python3 analyze_projects.py
```

Shows all projects with variations.

### Method 2: Export and Review

1. Click "📥 Export Full Data"
2. Open in Excel
3. Sort by ProjectCode column
4. Look for similar codes
5. Sort by ProjectName column
6. Look for similar names

### Method 3: SQL-like Query (Future)

```sql
SELECT ProjectCode, ProjectName, COUNT(*)
FROM timesheets
GROUP BY ProjectCode, ProjectName
HAVING COUNT(*) > 5
ORDER BY ProjectCode
```

## Examples

### Example 1: Similar Project Codes

**Problem:** OCR reads both `"P001"` and `"PO01"`

**Solution:**
```json
{
  "code": "P001",
  "name": "Project Alpha",
  "aliases": {
    "codes": ["PO01"]
  }
}
```

**Result:** Both map to `P001`

### Example 2: Name Variations

**Problem:** OCR reads:
- `"Project Alpha"`
- `"Project  Alpha"` (extra space)
- `"Project Aplha"` (typo)

**Solution:**
```json
{
  "code": "P001",
  "name": "Project Alpha",
  "aliases": {
    "names": ["Project Aplha"]
  }
}
```

**Result:**
- `"Project Alpha"` → exact match
- `"Project  Alpha"` → normalized (extra space removed)
- `"Project Aplha"` → alias match

### Example 3: Multiple Projects with Similar Names

**Problem:**
- `"Website Redesign Q1"`
- `"Website Redesign Q2"`

**Solution:** Use clear codes

```json
[
  {
    "code": "WEB-Q1-2025",
    "name": "Website Redesign Q1 2025"
  },
  {
    "code": "WEB-Q2-2025",
    "name": "Website Redesign Q2 2025"
  }
]
```

## Integration with OCR Processing

The project normalization happens automatically during OCR:

1. Claude extracts project code and name from timesheet
2. `ProjectManager.match_project(code, name)` is called
3. Returns canonical code and name
4. Canonical values are stored in DynamoDB

**No action needed** - it just works!

## Monitoring & Maintenance

### Weekly Review

1. Run `analyze_projects.py`
2. Check for new projects
3. Verify they're legitimate
4. Add to master list if needed

### Monthly Cleanup

1. Export full database
2. Review ProjectCode and ProjectName columns
3. Look for patterns indicating OCR issues
4. Update master list and aliases

### Before Major OCR Batches

1. Ensure master list is current
2. Review normalization rules
3. Test with a few timesheets first
4. Check database for correct normalization
5. Proceed with bulk OCR

## Troubleshooting

### Q: OCR is still creating duplicates

**A:** Check confidence thresholds in `project_manager.py`:
- Code fuzzy match: 95% (line ~180)
- Name fuzzy match: 90% (line ~185)

Lower if too strict, raise if too lenient.

### Q: Legitimate different projects being merged

**A:** The projects are too similar. Use more distinctive:
- Project codes: `ALPHA-001` vs `BETA-001` not `A001` vs `B001`
- Project names: Include client/phase/year

### Q: How to undo a bad merge?

**A:**
1. Export full database
2. Find affected rows in CSV
3. Correct ProjectCode and ProjectName
4. Import corrections
5. Update master list to prevent recurrence

## Future Enhancements

- UI tab for project management (similar to Team Management)
- Auto-learning: suggest aliases based on patterns
- Bulk project rename tool
- Project grouping/categories
- Client → Project hierarchy

## Summary

**Before bulk OCR:**
1. Run `analyze_projects.py`
2. Review `project_master_suggested.json`
3. Edit and save as `project_master.json`
4. Run test OCR batch
5. Verify normalization working
6. Proceed with bulk OCR

**Result:** Clean, consistent project data with no duplicates!
