# 📋 Next Session TODO

**Date Created**: 2025-11-22

---

## 🎯 Primary Task

**Validate Labour Hours Report Against Independent Data Source**

### Objective
Compare the "Month Total (Days)" column from the Labour Hours Report against an independent data source to identify any discrepancies and investigate data quality issues.

### Steps to Follow

1. **Generate Labour Hours Report**
   - Select a Clarity month (e.g., Nov-25)
   - Download report from web interface
   - Extract "Month Total (Days)" values for all team members

2. **Compare Against Independent Source**
   - Obtain independent data source (provide this to Claude)
   - Compare values side-by-side
   - Identify discrepancies

3. **Investigate Discrepancies**
   - For each mismatch, investigate:
     - Is data missing in DynamoDB?
     - Are there duplicate entries?
     - Are zero-hour timesheets correctly detected?
     - Are there data entry errors in the source images?

4. **Root Cause Analysis**
   - Determine why discrepancies exist
   - Check database entries for affected team members
   - Review Lambda logs for processing errors
   - Verify OCR extraction accuracy

5. **Fix Any Issues Found**
   - Update data if needed
   - Fix any bugs in calculation logic
   - Re-run reports to verify fixes

---

## 📊 What to Bring to Next Session

- Independent data source file (Excel, CSV, or manual data)
- Specific Clarity month to validate (e.g., "Nov-25")
- Any known issues or concerns with specific team members

---

## 🔧 Recent Changes (Context)

**Labour Hours Report Just Implemented**:
- Shows hours worked per week + monthly totals in hours AND days
- Days calculated as: `hours ÷ 7.5`
- Zero-hour timesheets (absence/leave) now shown as "0.0" in orange
- Missing timesheets shown as "-" in gray

**Files Modified**:
- `src/labour_hours_report.py` (NEW)
- `web_app.py` (added `/api/labour-hours` endpoint)
- `templates/dashboard.html` (added button & JavaScript)

**Current Status**:
- ✅ Feature working correctly
- ✅ Zero-hour detection functional
- ✅ Web interface ready
- ⏳ Awaiting validation against independent source

---

**Reminder**: Start next session with: *"I want to compare the Labour Hours Report (days column) against my independent data source to check for discrepancies."*
