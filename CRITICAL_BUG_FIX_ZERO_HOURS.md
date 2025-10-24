# CRITICAL BUG FIX: Zero-Hour Database Bloat

**Date**: October 23, 2025
**Severity**: CRITICAL
**Status**: FIXED ✅

---

## 🚨 Problem Summary

The OCR system was creating database entries for **EVERY combination** of day × project, even when hours = 0. This caused massive database bloat:

### Example 1: Image `2025-10-20_16h04_51.png`
- **Expected**: 3 entries (3 days worked)
  - Mon Oct 6: MoneyMap 7.5h
  - Thu Oct 9: ACE Commission 7.5h
  - Fri Oct 10: 5G SA 7.5h

- **Actual**: 21 entries created (7 days × 3 projects)
  - Mon: 3 entries (1 with hours, 2 with 0)
  - Tue: 3 entries (all 0 hours)
  - Wed: 3 entries (all 0 hours)
  - Thu: 3 entries (1 with hours, 2 with 0)
  - Fri: 3 entries (1 with hours, 2 with 0)
  - Sat: 3 entries (all 0 hours)
  - Sun: 3 entries (all 0 hours)

### Example 2: Image `2025-10-20_16h04_55.png`
- **Expected**: 1 entry (1 day worked)
  - Wed Sep 17: PJ022317 7.5h

- **Actual**: 11+ entries created (multiple days × multiple projects with mostly 0 hours)

---

## 🔍 Root Cause Analysis

### The Bug Location
**File**: `src/parsing.py`
**Function**: `convert_to_csv()`
**Lines**: 297-314 (original)

```python
# BUGGY CODE (BEFORE FIX):
for i, day_data in enumerate(hours_by_day):
    date_obj = week_dates[i]
    hours = parse_hours(hours_str)

    row = {
        'Resource Name': resource_name,
        'Date': format_date_for_csv(date_obj),
        'Project Name': project_name,
        'Project Code': project_code,
        'Hours': hours  # ← Could be 0!
    }
    rows.append(row)  # ← ALWAYS APPENDS, even if hours = 0!
```

### Why Validation Didn't Catch This

The validation system checked:
1. ✅ **Total hours match** (22.5h = 22.5h) - PASSED
2. ✅ **Project codes are valid** - PASSED
3. ✅ **Person name matches** - PASSED

But it **DIDN'T** check:
4. ❌ **Number of entries created should match actual work days**
5. ❌ **Entries with 0 hours shouldn't be created** (except bank holidays)

The validation passed because the **total hours were correct**, but the **structure was wrong**.

---

## ✅ The Fix

**File**: `src/parsing.py`
**Lines**: 307-311 (new)

```python
# FIXED CODE:
for i, day_data in enumerate(hours_by_day):
    date_obj = week_dates[i]
    hours = parse_hours(hours_str)

    # CRITICAL FIX: Skip entries with 0 hours to prevent database bloat
    # Only create database entries for days where actual work was logged
    # Exception: Bank holidays should still be recorded as 0 hours
    if hours == 0 and not is_bank_holiday(date_obj):
        continue  # ← SKIP this entry!

    row = {
        'Resource Name': resource_name,
        'Date': format_date_for_csv(date_obj),
        'Project Name': project_name,
        'Project Code': project_code,
        'Hours': hours
    }
    rows.append(row)
```

### What Changed

1. **Added check**: Skip rows where `hours == 0` AND it's not a bank holiday
2. **Preserves bank holidays**: Bank holidays with 0 hours are still recorded (important for compliance)
3. **Reduces bloat**: Database will only contain entries for days where work was actually logged

---

## 📊 Expected Impact

### Before Fix
- **3 days worked** → **21 database entries** (7×3 cross-product)
- **1 day worked** → **7-11+ database entries**
- Database bloated by **~600%**

### After Fix
- **3 days worked** → **3 database entries** ✅
- **1 day worked** → **1 database entry** ✅
- Correct number of entries

### Database Size Reduction
- **Before**: ~4,179 entries (estimated ~2,500 inflated)
- **After rescan**: ~1,500-1,700 entries (expected actual work days)
- **Savings**: ~60% reduction in database bloat

---

## 🚀 Deployment

### Lambda Update
```bash
# Packaged and deployed fix
cd src && zip -r ../lambda_zero_hour_fix.zip . -x "__pycache__/*"
zip lambda_zero_hour_fix.zip team_roster.json clarity_months.json
aws lambda update-function-code \
  --function-name TimesheetOCR-ocr-dev \
  --zip-file fileb://lambda_zero_hour_fix.zip \
  --region us-east-1
```

**Status**: ✅ Deployed successfully
**Code Size**: 46,541 bytes
**Runtime**: Python 3.13

---

## ⚠️ Action Required

### 1. Database Cleanup
The current database has **thousands of incorrect 0-hour entries**. You have two options:

**Option A: Flush & Rescan (Recommended)**
```bash
# Flush database
python3 flush_database.py

# Rescan all images
python3 /tmp/rescan_all.py
```

**Option B: Delete 0-Hour Entries Only**
```python
# Delete only entries with 0 hours (non-bank holidays)
# Keep existing correct entries
```

### 2. Verification
After rescan, verify correct behavior:
```bash
# Check entry count for a known timesheet
# Should match actual work days, not 7×projects
```

---

## 📚 Lessons Learned

1. **Validation Gaps**: Total hours validation isn't enough - need to check entry count
2. **Test Edge Cases**: Test with timesheets that have:
   - Only 1 day worked
   - Scattered days (Mon, Wed, Fri)
   - Multiple projects per day
3. **Database Inspection**: Regularly check database for anomalies (bloat, duplicates)
4. **Explicit Filtering**: Always filter out unwanted data before insertion

---

## 🔐 Prevention Measures

### New Validation Rule (Consider Adding)
```python
def validate_entry_count(timesheet_data, created_entries):
    """Validate that number of entries matches expected days worked."""
    total_hours = sum(entry['Hours'] for entry in created_entries)
    expected_days = total_hours / 7.5  # Assuming 7.5h per day
    actual_entries_with_hours = len([e for e in created_entries if e['Hours'] > 0])

    if abs(actual_entries_with_hours - expected_days) > 1:
        raise ValueError(
            f"Entry count mismatch: {actual_entries_with_hours} entries "
            f"but {expected_days:.1f} days expected"
        )
```

### Monitoring
- Add CloudWatch alarm for database entry rate spikes
- Weekly audit report showing entries/timesheet ratio
- Alert if any timesheet creates > 10 entries

---

## ✅ Fix Verification Checklist

- [x] Bug identified and root cause confirmed
- [x] Fix implemented in `src/parsing.py`
- [x] Lambda function updated with fix
- [ ] Database flushed (pending user action)
- [ ] All images rescanned with fixed code
- [ ] Entry counts verified for sample timesheets
- [ ] No 0-hour entries in database (except bank holidays)

---

**Status**: Fix deployed, awaiting database flush and rescan.
