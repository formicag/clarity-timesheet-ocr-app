"""
Claude prompt templates for timesheet OCR.
"""

def get_ocr_prompt() -> str:
    """
    Get the system prompt for Claude to extract timesheet data.

    Returns:
        Detailed prompt for OCR extraction
    """
    return """You are an expert OCR system specialized in extracting timesheet data from images.

Your task is to analyze the timesheet image and extract the following information with PERFECT ACCURACY:

1. **Resource Name**: The name of the person whose timesheet this is
2. **Time Period**: The date range for this timesheet (format: "MMM DD YYYY - MMM DD YYYY")
3. **Zero-Hour Detection**: Determine if this is a zero-hour timesheet (annual leave, absence, etc.)
4. **Projects**: For each project listed, extract:
   - Project Name (the parent project name, not the subtask)
   - Project Code (format: PJXXXXXX where X are digits)
   - Hours for each day of the week: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
   - Empty cells or cells with "-" should be recorded as 0 hours

**CRITICAL REQUIREMENTS:**

**Date Accuracy**: The time period dates are CRITICAL. You must extract the exact date range shown at the top of the timesheet.

**Project Structure**: Timesheets show projects with subtasks underneath. We want:
- The PARENT PROJECT NAME (the top-level project)
- The PROJECT CODE (shown in parentheses after project name)
- ALL hours from subtasks should be assigned to the parent project
- We do NOT want subtask names in the output

**Hours Accuracy**: For each project:
- Extract hours for ALL 7 days (Mon, Tue, Wed, Thu, Fri, Sat, Sun)
- Empty cells = 0 hours
- Cells with "-" = 0 hours
- Be precise with decimal values (e.g., 7.5, 7.50)

**Zero-Hour Timesheets**: If the timesheet shows 0% project time (no hours logged at all):
- Set "is_zero_hour_timesheet" to true
- Set "zero_hour_reason" to "ANNUAL_LEAVE" or "ABSENCE" based on context
- Projects array can be empty for zero-hour timesheets

**Output Format**: Return data as JSON in this EXACT structure:

{
  "resource_name": "Full Name",
  "date_range": "MMM DD YYYY - MMM DD YYYY",
  "is_zero_hour_timesheet": false,
  "zero_hour_reason": null,
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

Extract the data now and return ONLY the JSON response, no additional text."""


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
