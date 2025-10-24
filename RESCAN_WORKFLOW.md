# Complete Database Flush & Rescan Workflow

## Overview

This workflow will:
1. ✅ Deploy quality improvements (DONE - already deployed)
2. 🔄 Flush DynamoDB completely
3. 🔄 Rescan all timesheet images
4. 📊 Generate quality report to verify improvements

---

## Current Status

### Already Deployed ✅
- Enhanced OCR prompt with project code rules
- Project code correction module
- Bank holiday detection
- Format validation and auto-correction

### Quality Improvements Active ✅
- OCR digit confusion correction (0↔9, 0↔8, 6↔5, 2↔3, 1↔7)
- Category label detection (DESIGN, LABOUR, INFRA, DATA)
- Project name format validation
- Auto-correction with logging

---

## Step-by-Step Rescan Process

### Step 1: Flush DynamoDB

```bash
python3 flush_database.py
```

**What it does:**
- Scans all current entries
- Creates backup JSON file
- Deletes all entries from DynamoDB
- Shows progress every 100 records

**Confirmation required:**
- Type exactly: `DELETE ALL`

**Output:**
- `backup_before_flush_YYYYMMDD_HHMMSS.json`

---

### Step 2: Rescan All Images

You have two options:

#### Option A: Use Existing Reprocess Script
```bash
python3 reprocess_all.py
```

#### Option B: Trigger via S3 Notifications
The Lambda is already configured with S3 event notifications.
Simply re-upload all images to the S3 bucket (or touch them to trigger events).

#### Option C: Manual Lambda Invocation for Batch Processing
If you want to process specific batches:

```bash
# Get list of all images in S3
aws s3 ls s3://timesheetocr-input-dev-016164185850/ --region us-east-1 > images_to_process.txt

# Process them (you'd need a script for this)
```

---

### Step 3: Monitor Progress

Watch Lambda logs for quality corrections:

```bash
aws logs tail /aws/lambda/TimesheetOCR-ocr-dev \
    --follow \
    --region us-east-1
```

**Look for:**
- `🏦` = Bank holiday correction
- `📝` = Project code quality correction
- `⚠️` = Suspected OCR error flagged

**Example good output:**
```
🏦 Bank Holiday Detected: Monday Aug 25, 2025 - Summer bank holiday
   Correcting daily total from 7.5 to 0

📝 Project Code Quality Correction:
   Project: PJ032403
   - Replaced category label 'DESIGN' with project code 'PJ032403'
   Confidence: medium
```

---

### Step 4: Generate Quality Report

After rescanning all images:

```bash
python3 generate_quality_report.py
```

**Expected Results:**
```
OCR DATA QUALITY REPORT
================================================
Total Records Analyzed:        624
Format Violations:             0 (0.0%)    ← Should be 0!
  - Missing codes in name:     0           ← Down from 35+
  - Wrong codes in name:       0           ← Down from 21+
  - Category labels as codes:  0           ← Down from 7+
Suspected OCR Errors:          5-10        ← Flagged for review

✅ No format violations found!
⚠️  Review 5-10 suspected OCR digit errors (PJ9* codes)
```

---

## Performance Benchmarks

### Before Quality Improvements:
- Format violations: **63 (10%)**
- Missing codes: **35+**
- Wrong codes: **21+**
- Category labels: **7+**
- OCR digit errors: **Undetected**

### After Quality Improvements (Expected):
- Format violations: **0 (0%)**
- Missing codes: **0**
- Wrong codes: **0**
- Category labels: **0**
- OCR digit errors: **Flagged for manual review (5-10)**

### Improvement:
- **100% format compliance** (up from 90%)
- **Zero manual corrections needed** for format issues
- **OCR errors detected and flagged** for review
- **Cleaner project list** with fewer duplicates

---

## What to Watch For

### Success Indicators ✅

1. **Log Output Shows Corrections:**
   ```
   📝 Project Code Quality Correction:
      - Fixed project name format
      - Replaced category label
   ```

2. **Bank Holidays Detected:**
   ```
   🏦 Bank Holiday Detected: Monday Aug 25, 2025
   ```

3. **Quality Report Shows Zero Violations:**
   ```
   Format Violations: 0 (0.0%)
   ```

### Issues to Review ⚠️

1. **Suspected OCR Errors Flagged:**
   ```
   ⚠️  Possible OCR Error Detected:
      Code: PJ924483
      Suggestion: Might be PJ024483 (9→0 confusion)
   ```
   **Action:** Review these manually against source images

2. **Multiple Codes for Same Project:**
   - Check `project_variations_report.json`
   - Consolidate via project manager aliases

---

## Post-Rescan Actions

### 1. Review Quality Report
```bash
python3 generate_quality_report.py
```

Compare to pre-rescan baseline.

### 2. Review Flagged OCR Errors
Open `corrections_needed_*.csv` (if any issues found)

### 3. Update Master Project List
```bash
python3 build_master_project_list.py
```

This captures any new projects or variations from the rescan.

### 4. Fix Remaining Issues (if any)

For suspected OCR digit errors (PJ9* codes):
```python
from src.project_manager import ProjectManager

pm = ProjectManager()

# If PJ924483 should actually be PJ024483:
pm.add_alias('PJ024483', 'code', 'PJ924483')
pm.save_master_list()
```

Then reprocess just those affected images.

---

## Rollback (If Needed)

If the rescan has issues and you need to restore old data:

```bash
# The flush script created a backup
ls -la backup_before_flush_*.json

# Restore from backup (you'd need a restore script)
# Or manually review the backup file
```

---

## Timeline Estimate

Based on ~600 records:

- **Flush:** 1-2 minutes
- **Rescan:** 10-30 minutes (depends on method and Lambda concurrency)
- **Quality Report:** 2-3 minutes
- **Total:** ~15-35 minutes

---

## Commands Summary

```bash
# 1. Flush database (creates backup automatically)
python3 flush_database.py
# Type: DELETE ALL

# 2. Rescan all images
python3 reprocess_all.py

# 3. Monitor (optional - in another terminal)
aws logs tail /aws/lambda/TimesheetOCR-ocr-dev --follow --region us-east-1

# 4. Generate quality report
python3 generate_quality_report.py

# 5. Rebuild master list (captures new state)
python3 build_master_project_list.py
```

---

## Expected Final State

### DynamoDB
- Clean, fresh data
- All format violations corrected
- Bank holidays properly handled
- Project codes normalized

### Quality Metrics
- 100% format compliance
- Zero category label errors
- OCR digit errors flagged (not stored incorrectly)
- Consistent project naming

### Master Project List
- Updated with any new codes
- Ready for future OCR validation
- Cleaner with fewer variations

---

## Next Steps After Rescan

1. **Use the system normally** - Upload new timesheets via UI
2. **Monitor quality** - Run weekly reports
3. **Review flagged issues** - Check ⚠️ warnings in logs
4. **Update master list** - As new projects are added
5. **Track improvements** - Compare quality over time

---

**Status:** Ready to proceed
**Risk:** Low (backup created automatically)
**Benefit:** Clean slate with quality improvements active
**Estimated Time:** 15-35 minutes

Ready when you are!
