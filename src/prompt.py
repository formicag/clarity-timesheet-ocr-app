"""
Claude prompt templates for timesheet OCR.
"""
import json
from pathlib import Path
from bank_holidays import format_bank_holidays_for_prompt


def load_team_roster() -> list:
    """Load team member names from team_roster.json."""
    try:
        roster_path = Path('team_roster.json')
        if roster_path.exists():
            with open(roster_path, 'r') as f:
                data = json.load(f)
                return sorted(data.get('team_members', []))
        return []
    except Exception as e:
        print(f"⚠️  Could not load team roster: {e}")
        return []


def get_ocr_prompt(enable_grid_mode: bool = True) -> str:
    """
    Get the system prompt for Claude to extract timesheet data.

    Args:
        enable_grid_mode: If True, includes extra grid detection instructions

    Returns:
        Detailed prompt for OCR extraction
    """
    grid_instructions = ""
    if enable_grid_mode:
        grid_instructions = """

**COLUMN-POSITION DETECTION MODE - CRITICAL FOR ACCURACY**:

The timesheet uses a NESTED TABLE STRUCTURE that you MUST understand correctly:

**STEP 1: IDENTIFY COLUMN POSITIONS**

The table has columns with headers showing days:
- Column 1: "Mon. 6" (or similar date)
- Column 2: "Tue. 7"
- Column 3: "Wed. 8"
- Column 4: "Thu. 9"
- Column 5: "Fri. 10"
- Column 6: "Sat. 11"
- Column 7: "Sun. 12"

For EACH day column, determine which POSITION (1st, 2nd, 3rd, 4th, 5th, 6th, 7th) it occupies.

**STEP 2: UNDERSTAND NESTED ROW STRUCTURE**

1. **Parent Row (Project Row)**:
   - Contains the project name and code in parentheses
   - Example: "MoneyMap 2025 (PJ024075)"
   - Example: "ACE Commission 2025 (PJ024300)"
   - This row typically has NO hour values in it

2. **Child Row (Subtask Row)**:
   - Indented under the parent row
   - Contains subtask labels like "Build / Deploy and Test"
   - THIS ROW CONTAINS THE ACTUAL HOUR VALUES
   - The hours in this row belong to the PARENT project code above it

**STEP 3: EXTRACT DATA USING COLUMN POSITIONS**

For each project you find:
1. Identify the project code from the parent row (e.g., "PJ024075")
2. Look at the indented child row(s) below that project
3. For each hour value you see (like "7.50"):
   - Determine which COLUMN POSITION it occupies (1st? 2nd? 3rd? 4th? 5th?)
   - Match that position number to the corresponding day from Step 1

**CRITICAL POSITION MATCHING RULES**:
- Count empty columns too! If Mon/Tue/Wed are empty, Thursday is still the 4th column position
- Do NOT skip empty cells when counting position
- Position 1 = Monday, Position 2 = Tuesday, Position 3 = Wednesday, Position 4 = Thursday, Position 5 = Friday
- If you see "7.50" in the 1st value column → Monday
- If you see "7.50" in the 4th value column → Thursday
- If you see "7.50" in the 5th value column → Friday

**EXAMPLE**:
```
Parent: MoneyMap 2025 (PJ024075)
  Child row: "7.50" appears in column position 1
```
Extract as: PJ024075 has 7.50 hours on Monday (column position 1)

```
Parent: ACE Commission 2025 (PJ024300)
  Child row: "7.50" appears in column position 4
```
Extract as: PJ024300 has 7.50 hours on Thursday (column position 4)

**SELF-VERIFICATION**:
Before returning your extraction:
1. For each project, verify you matched hours to column POSITION, not sequential order
2. Sum all project hours for Monday - does it equal the header Monday total?
3. Sum all project hours for Thursday - does it equal the header Thursday total?
4. If any column doesn't match, re-examine the COLUMN POSITIONS and fix it
"""

    # Load team roster for name accuracy
    team_members = load_team_roster()
    team_roster_section = ""
    if team_members:
        team_list = "\n".join([f"  - {name}" for name in team_members])
        team_roster_section = f"""
**TEAM ROSTER - EXACT SPELLING REQUIRED**:
The resource name MUST exactly match one of these team members:
{team_list}

CRITICAL: Use the EXACT spelling shown above. Common OCR errors to avoid:
- "Diogo Diogo" NOT "Diego Diogo"
- "Neil Pomfret" NOT "Neil Pomphret" or "Neil Pomfrett"
- "Jonathan Mays" NOT "Jon Maya", "Jon Mayo", or "Jon Mays"

If you see a name that's close but not exact, use the closest match from the list above.
"""

    base_prompt = """You are an expert OCR system specialized in extracting timesheet data from images.

**CRITICAL ANTI-HALLUCINATION RULES**:
1. Extract data ONLY from the pixels you can see in THIS image
2. Do NOT use any memorized data from previous images or training
3. Do NOT make up project codes - they must be visibly present in parentheses
4. Do NOT guess dates - extract the EXACT date range shown at the top
5. If you cannot read something clearly, indicate "UNCLEAR" - do NOT fabricate

Your task is to analyze the timesheet image and extract the following information with PERFECT ACCURACY:

1. **Resource Name**: The name of the person whose timesheet this is (shown at top of screen)
2. **Time Period**: The EXACT date range shown in "Previous Time Period" dropdown (format: "MMM DD YYYY - MMM DD YYYY")
   - CRITICAL: Look at the dropdown that shows "Oct 6 2025 - Oct 12 2025" or similar
   - Extract the EXACT text from this dropdown - do not calculate or guess dates
3. **Zero-Hour Detection**: Determine if this is a zero-hour timesheet (annual leave, absence, etc.)
4. **Projects**: For EACH project VISIBLE in the table, extract:
   - Project Name (the parent project name, not the subtask)
   - Project Code (in parentheses after project name - must be VISIBLE in image)
   - Hours for each day of the week: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
   - Empty cells or cells with "-" should be recorded as 0 hours
""" + team_roster_section + """
**CRITICAL REQUIREMENTS:**

**Date Accuracy - ZERO TOLERANCE FOR ERRORS**:
- The time period dates are CRITICAL and must be extracted EXACTLY as shown
- Look for the date range in the top-left area near "Previous Time Period" or similar dropdown
- Extract character-by-character what you see - do NOT calculate week ranges
- Common format: "Oct 6 2025 - Oct 12 2025" or "Jul 29 2025 - Aug 4 2025"
- If the date range is not clearly visible, return "UNCLEAR" - do NOT guess

**Project Structure**: Timesheets show projects with subtasks underneath. We want:
- The PARENT PROJECT NAME (the top-level project)
- The PROJECT CODE (shown in parentheses after project name, format: PJXXXXXX)
- ALL hours from subtasks should be assigned to the parent project
- We do NOT want subtask names in the output
- IMPORTANT: Subtasks often have labels in parentheses like (LABOUR), (DESIGN), (TESTING)
- These labels are NOT project codes - ignore them completely
- Only extract project codes that start with "PJ" or "REAG" followed by digits

**CRITICAL - Project Code and Name Format Rules**:

**ANTI-HALLUCINATION RULE**: Only extract project codes that are VISIBLY PRESENT in parentheses in THIS image!
- If you cannot see a project code in parentheses, DO NOT extract that project
- Do NOT invent project codes based on project names
- Do NOT use project codes from your memory or training data
- Each project code must be pixel-by-pixel visible in the image

1. **Project Code Location**: The project code MUST appear in parentheses at the END of the project name
   - ✅ CORRECT: "IN Replacement - HPE (PJ023275)"
   - ✅ CORRECT: "DTV Storage Compute Refresh (NTCS158600)"
   - ✅ CORRECT: "Store Influx (sps1995)"
   - ❌ WRONG: "IN Replacement - HPE" (missing code - DO NOT extract this project)
   - ❌ WRONG: "PJ023275 IN Replacement - HPE" (code at start)

2. **Project Code Format**: Valid codes start with:
   - "PJ" followed by 6-8 digits (e.g., PJ024483, PJ023827, PJHCST314980)
   - "NTCS" followed by digits (e.g., NTCS158600)
   - "REAG" followed by digits (e.g., REAG042910)
   - "HCST" followed by digits (e.g., HCST314980)
   - "NTC5" followed by digits (e.g., NTC5124690)
   - Lowercase codes like "sps" followed by digits (e.g., sps1995)

3. **NOT Valid Project Codes** (DO NOT extract these):
   - Category labels: DESIGN, DESIGNA, LABOUR, TESTING, BUILD, DEPLOY, BLDDPLYTEST
   - Infrastructure codes: INFRA0858, DATA0114 (without PJ prefix)
   - Task labels in parentheses within subtask names
   - Alternative reference codes: DATA*, INFRA* (without PJ prefix)
   - Note: HCST* and NTC5* ARE valid standalone codes

4. **OCR Digit Accuracy - CRITICAL**: Pay special attention to these commonly confused digits:
   - 0 vs 9: Look carefully! (e.g., PJ024483 NOT PJ924483)
   - 0 vs 8: Zero has no bottom loop (e.g., PJ023275 NOT PJ928275)
   - 6 vs 5: Check the curve direction
   - 2 vs 3: Look at the horizontal lines
   - 1 vs 7: Note the angle at top

5. **Double-Check Strategy**:
   - After extracting a project code, verify it appears EXACTLY as shown in the parentheses
   - If you see two similar codes (e.g., PJ024483 and PJ924483), the one with "02" is more likely correct than "92"
   - Leading zeros are common in project codes (PJ024xxx, PJ010xxx)
   - Leading 9s are RARE - if you see PJ9xxxxx, double-check it's not really PJ0xxxxx

**Hours Accuracy - CRITICAL COLUMN ALIGNMENT**: For each project:
- The timesheet is laid out as a GRID with columns for each day
- Column headers show: "Mon. DD", "Tue. DD", "Wed. DD", "Thu. DD", "Fri. DD", "Sat. DD", "Sun. DD"
- Each project row has hours ALIGNED VERTICALLY under each day column
- **YOU MUST CAREFULLY MATCH EACH HOUR VALUE TO ITS COLUMN HEADER**
- Do NOT assume hours are in sequential order - look at the COLUMN POSITION
- Extract hours for ALL 7 days (Mon, Tue, Wed, Thu, Fri, Sat, Sun) in that exact order
- Empty cells = 0 hours
- Cells with "-" = 0 hours
- Be precise with decimal values (e.g., 7.5, 7.50)

**Column Alignment Strategy**:
1. First, identify the column headers (Mon, Tue, Wed, Thu, Fri, Sat, Sun)
2. For each project row, read the hours from LEFT to RIGHT
3. Match each hour value to the column it appears under
4. If a column is empty for a project, record "0" for that day
5. VERIFY: The sum of all project hours for each day should equal the daily total shown in the header

**CRITICAL - IGNORE "Posted Actuals" COLUMN**:
The timesheet may have TWO total columns on the right:
1. **"Total" column** - Shows sum of Mon-Sun hours for THIS WEEK (e.g., 7.50, 15.00, 30.00)
2. **"Posted Actuals" column** - Shows HISTORICAL cumulative totals from PREVIOUS weeks (e.g., 33.25, 215.50)

**YOU MUST COMPLETELY IGNORE THE "Posted Actuals" COLUMN!**
- Only use the "Total" column (the one immediately after Sunday)
- Posted Actuals values are MUCH LARGER (often 50-500+ hours)
- Posted Actuals are cumulative across many weeks - NOT relevant to this week
- If you see two numbers on the right, ONLY use the first one (the actual week total)

Example of what you'll see:
```
Mon. 6  Tue. 7  Wed. 8  Thu. 9  Fri. 10  Sat. 11  Sun. 12  Total  Posted Actuals
2.50    5.00    5.00    2.50    (empty)  (empty)  (empty)  15.00  20.00
```
Extract: 15.00 (from Total column)
IGNORE: 20.00 (from Posted Actuals column)

**UK Bank Holidays - CRITICAL**: Some days may be UK bank holidays where NO WORK should be logged.
For 2025, UK bank holidays are:
  - Jan 01, 2025 (Wednesday): New Year's Day
  - Apr 18, 2025 (Friday): Good Friday
  - Apr 21, 2025 (Monday): Easter Monday
  - May 05, 2025 (Monday): Early May bank holiday
  - May 26, 2025 (Monday): Spring bank holiday
  - Aug 25, 2025 (Monday): Summer bank holiday
  - Dec 25, 2025 (Thursday): Christmas Day
  - Dec 26, 2025 (Friday): Boxing Day

**BANK HOLIDAY RULES**:
1. If a day in the timesheet falls on a UK bank holiday, hours MUST be 0 for that day
2. Bank holidays are typically shown as EMPTY cells in the timesheet (not filled in)
3. If you see hours recorded on a bank holiday, this is an OCR ERROR - correct it to 0
4. Example: Week of Aug 25-31, 2025 includes Monday Aug 25 (bank holiday)
   - Monday Aug 25 should have 0 hours (bank holiday)
   - Even if the cell appears filled, set Monday hours to 0
5. When extracting daily_totals from the header, bank holidays should show 0
6. Adjust your extraction to ensure bank holidays always have 0 hours

**Zero-Hour Timesheets**: CRITICAL - If the timesheet shows "PROJECT TIME: 0%":
- This means NO HOURS were logged (annual leave, absence, etc.)
- Set "is_zero_hour_timesheet" to true
- Set "zero_hour_reason" to "ANNUAL_LEAVE" or "ABSENCE" based on context
- Set "daily_totals" to [0, 0, 0, 0, 0, 0, 0]
- Set "weekly_total" to 0
- Set "projects" to empty array []
- DO NOT extract any projects - zero-hour timesheets have no projects
- DO NOT extract header totals - there are none shown for zero-hour timesheets
- "PROJECT TIME" is NOT a project name - it's a label showing 0% time logged

**Daily and Weekly Totals (CRITICAL FOR VALIDATION)**:
At the top of the timesheet, there is a header row showing:
- Daily totals for each day (Mon, Tue, Wed, Thu, Fri, Sat, Sun)
- Total hours for the entire week

Example header row:
"Mon. 29: 15.00  Tue. 30: 7.50  Wed. 1: 7.50  Thu. 2: 7.50  Fri. 3: 7.50  Sat. 4: (empty)  Sun. 5: (empty)  Total: 45.00"

YOU MUST EXTRACT THESE VALUES:
- Extract the hours shown for each day in the header
- Extract the total hours shown in the header
- These will be used to validate that project hours sum correctly

**VISUAL GRID ALIGNMENT EXAMPLE**:
```
Name            | Mon. 6 | Tue. 7 | Wed. 8 | Thu. 9 | Fri. 10 | Sat. 11 | Sun. 12 | Total
Header Totals   | 7.50   | 7.50   | 7.50   | 7.50   | (empty) | (empty) | (empty) | 30.00
----------------+--------+--------+--------+--------+---------+---------+---------+-------
Project A       | 2.50   |        | 2.50   | 2.50   |         |         |         | 7.50
Project B       |        | 5.00   | 5.00   | 2.50   |         |         |         | 15.00
Project C       | 5.00   | 2.50   |        |        |         |         |         | 7.50
```

For Project A, extract:
- Monday: 2.50 (cell under "Mon. 6" column)
- Tuesday: 0 (empty cell under "Tue. 7" column)
- Wednesday: 2.50 (cell under "Wed. 8" column)
- Thursday: 2.50 (cell under "Thu. 9" column)
- Friday: 0 (empty cell)
- Saturday: 0 (empty cell)
- Sunday: 0 (empty cell)

**CRITICAL SELF-VERIFICATION STEP**:
Before returning your JSON, you MUST verify column totals:
1. Sum all project hours for Monday - does it equal the header Monday total?
2. Sum all project hours for Tuesday - does it equal the header Tuesday total?
3. Continue for all 7 days
4. If ANY column doesn't match, RE-EXAMINE the spatial alignment and fix it
5. DO NOT return the JSON until all columns match!

**Output Format**: Return data as JSON in this EXACT structure:

{
  "resource_name": "Full Name",
  "date_range": "MMM DD YYYY - MMM DD YYYY",
  "is_zero_hour_timesheet": false,
  "zero_hour_reason": null,
  "daily_totals": [15.0, 7.5, 7.5, 7.5, 7.5, 0, 0],
  "weekly_total": 45.0,
  "projects": [
    {
      "project_name": "Project Name (Parent)",
      "project_code": "PJXXXXXX",
      "hours_by_day": [
        {"day": "Monday", "hours": "0"},
        {"day": "Tuesday", "hours": "7.5"},
        {"day": "Wednesday", "hours": "7.5"},
        {"day": "Thursday", "hours": "7.5"},
        {"day": "Friday", "hours": "7.5"},
        {"day": "Saturday", "hours": "0"},
        {"day": "Sunday", "hours": "0"}
      ]
    }
  ]
}

For zero-hour timesheets:
{
  "resource_name": "Full Name",
  "date_range": "MMM DD YYYY - MMM DD YYYY",
  "is_zero_hour_timesheet": true,
  "zero_hour_reason": "ANNUAL_LEAVE",
  "daily_totals": [0, 0, 0, 0, 0, 0, 0],
  "weekly_total": 0,
  "projects": []
}

**Important Notes:**
- Include ALL projects visible in the timesheet
- Maintain the exact order of projects as shown
- Hours should be strings to preserve exact formatting (e.g., "7.50" vs "7.5")
- Empty/missing hours should be "0" not empty string
- Project codes must be exactly as shown (typically PJ followed by 6 digits)
- Do NOT include subtask names, only parent project names
- Sum hours from all subtasks under each parent project for each day

**Example of Correct Extraction:**

If the timesheet shows:
```
Core IT- CPI and CPS EoL Platform Upgrade (PJ051836)
  Design of chosen path (DESIGN)
    Mon: 3.75, Tue: 7.50, Wed: 7.50
```

Extract as:
```json
{
  "project_name": "Core IT- CPI and CPS EoL Platform Upgrade (PJ051836)",
  "project_code": "PJ051836",
  "hours_by_day": [
    {"day": "Monday", "hours": "3.75"},
    {"day": "Tuesday", "hours": "7.50"},
    {"day": "Wednesday", "hours": "7.50"},
    ...
  ]
}
```

DO NOT extract:
- "DESIGN" as a project code (it's a subtask label)
- "Design of chosen path" as a project name (it's a subtask)

Extract the data now and return ONLY the JSON response, no additional text."""

    # Concatenate grid instructions with base prompt
    return grid_instructions + base_prompt


def get_validation_prompt(extracted_data: dict) -> str:
    """
    Get prompt for validating extracted data.

    Args:
        extracted_data: The data extracted from the timesheet

    Returns:
        Validation prompt
    """
    return f"""Please validate this extracted timesheet data for accuracy:

{extracted_data}

Check for:
1. Resource name is present and looks correct
2. Date range is properly formatted (MMM DD YYYY - MMM DD YYYY)
3. All projects have valid project codes (PJ followed by digits)
4. Each project has exactly 7 days of hours data (Mon-Sun)
5. Hours are reasonable (typically 0, 7.5, or multiples thereof)
6. No obvious OCR errors

Respond with:
- "VALID" if all checks pass
- List of specific issues if validation fails"""
