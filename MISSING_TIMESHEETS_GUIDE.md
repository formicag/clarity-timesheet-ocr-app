# Missing Timesheets Detection Guide

## Overview

The `find_missing_timesheets.py` script identifies which team members are missing timesheet submissions for specific weeks.

## How It Works

1. **Defines expected weeks** - Generates all Monday dates in your specified date range (weeks are Mon-Sun)
2. **Scans DynamoDB** - Finds all weeks that have been submitted (both regular and zero-hour timesheets)
3. **Compares** - For each team member, identifies which weeks are missing
4. **Reports** - Shows detailed list of missing weeks per person with summary statistics

## Usage

### Command Line
```bash
python3 find_missing_timesheets.py START_DATE END_DATE
```

**Example:**
```bash
python3 find_missing_timesheets.py 2025-09-01 2025-10-31
```

### Interactive Mode
```bash
python3 find_missing_timesheets.py
```
Then enter dates when prompted.

## Prerequisites

1. **AWS Credentials** - You must be logged in to AWS:
   ```bash
   aws sso login
   ```

2. **Team Roster** - The `team_roster.json` file must be up to date with all team members

3. **DynamoDB Access** - Script reads from `TimesheetOCR-dev` table

## Sample Output

```
================================================================================
MISSING TIMESHEET DETECTOR
================================================================================

Date Range: 2025-09-01 to 2025-10-31
Expected weeks (Mondays): 9
  - 2025-09-01 to 2025-09-07
  - 2025-09-08 to 2025-09-14
  - 2025-09-15 to 2025-09-21
  ...

Team members: 23

================================================================================
MISSING TIMESHEETS REPORT
================================================================================

📋 Barry Breden
   Submitted: 7/9 weeks
   Missing: 2 weeks
      ❌ 2025-09-01 to 2025-09-07 (Sep 01 - Sep 07, 2025)
      ❌ 2025-10-20 to 2025-10-26 (Oct 20 - Oct 26, 2025)

📋 James Matthews
   Submitted: 8/9 weeks
   Missing: 1 week
      ❌ 2025-09-08 to 2025-09-14 (Sep 08 - Sep 14, 2025)

================================================================================
SUMMARY
================================================================================
Team members: 23
Expected weeks per member: 9
Total timesheets expected: 207
Total timesheets submitted: 189
Total missing: 18
Members with missing timesheets: 8
Completion rate: 91.3%
================================================================================
```

## Key Features

✅ **Detects both regular and zero-hour timesheets** - Week is marked as "submitted" if either type exists

✅ **Week-aligned to Monday-Sunday** - Automatically finds all Monday dates in range

✅ **Full team coverage** - Checks all members from `team_roster.json`

✅ **Detailed reporting** - Shows exactly which weeks are missing for each person

✅ **Summary statistics** - Overall completion rate and totals

## Use Cases

### 1. Weekly Check
Check for missing timesheets from the past week:
```bash
python3 find_missing_timesheets.py 2025-10-20 2025-10-26
```

### 2. Monthly Report
Review full month:
```bash
python3 find_missing_timesheets.py 2025-10-01 2025-10-31
```

### 3. Quarter Review
Check entire quarter:
```bash
python3 find_missing_timesheets.py 2025-07-01 2025-09-30
```

## Understanding the Output

- **Submitted: 7/9 weeks** - Team member submitted 7 out of 9 expected weeks
- **Missing: 2 weeks** - 2 weeks have no timesheet (neither regular nor zero-hour)
- **❌ Date ranges** - Specific weeks missing (Monday to Sunday)
- **Completion rate** - Percentage of all expected timesheets that were submitted

## Notes

- Only checks team members in `team_roster.json`
- Zero-hour timesheets (annual leave, absence) count as submitted
- Weeks are always Monday (start) to Sunday (end)
- Date range is inclusive (both start and end dates included)

## Troubleshooting

**Error: "Token has expired"**
```bash
aws sso login
```

**Error: "No team members found"**
- Check that `team_roster.json` exists and has valid data

**Wrong weeks shown**
- Make sure dates are in YYYY-MM-DD format
- Verify start date is before end date
