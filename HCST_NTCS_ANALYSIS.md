# HCST/NTCS Project Code Analysis

## Summary

Found 2 source images with alternative project code prefixes (HCST/NTCS) that the system flagged as "invalid" but appear to be legitimate project codes.

---

## Images to Review

### Image 1: `2025-10-21_17h24_57.png`
**Location:** `s3://timesheetocr-input-dev-016164185850/2025-10-21_17h24_57.png`

**Person:** Gareth Jones
**Week:** Aug 18-24, 2025
**Project Code:** `HCST314980`
**Project Name:** DIY Storage Compute Refresh (HCST314980)

**Affected Records:** 7 (one per day Mon-Sun)

**System says:**
> 'HCST314980' appears to be an alternative reference code, not a valid project code (should start with PJ)

**Question:** Is `HCST314980` a valid standalone project code, or should it be `PJHCST314980`?

---

### Image 2: `2025-10-15_20h40_56.png`
**Location:** `s3://timesheetocr-input-dev-016164185850/2025-10-15_20h40_56.png`

**Person:** Gareth Jones
**Week:** Sep 29 - Oct 5, 2025
**Project Code:** `NTCS124690`
**Project Name:** DTV Storage Compute Refresh (NTCS124690)

**Affected Records:** 7 (one per day Mon-Sun)

**System says:**
> 'NTCS124690' appears to be an alternative reference code, not a valid project code (should start with PJ)

**Question:** Is `NTCS124690` a valid standalone project code, or should it be `PJ124690`?

---

## Analysis

### Pattern Observed

Both cases are from **Gareth Jones** and both are **Storage/Compute Refresh projects**.

**HCST** might stand for: "Host/Hardware/Compute Storage"
**NTCS** might stand for: "Network/Technology/Compute Storage"

### Comparison with Previous Data

From your original analysis, you mentioned:
- Gareth Jones had `HCST314980` (without PJ prefix) when code was `PJHCST314980`

This suggests:
- **`PJHCST314980`** = Full project code (with PJ prefix)
- **`HCST314980`** = Abbreviated version shown in timesheet

### Current Behavior

**What OCR extracted:**
- Project Code field: `HCST314980`
- Project Name: `DIY Storage Compute Refresh (HCST314980)`

**What the system expected:**
- Codes should start with `PJ` or `REAG`
- `HCST314980` doesn't match this pattern → flagged

**What likely happened in the image:**
- The timesheet shows `(HCST314980)` in the project name
- OCR correctly extracted this
- But it might be missing the `PJ` prefix that exists elsewhere

---

## Recommendations

### Option 1: These are valid codes (HCST/NTCS are approved prefixes)
**Action:** Whitelist HCST and NTCS prefixes
```python
# In src/project_code_correction.py
# Update line ~220:
if code and not code.startswith(('PJ', 'REAG', 'HCST', 'NTCS')):
    warnings.append(f"Unusual project code prefix: {code}")
```

### Option 2: These should have PJ prefix (OCR missed it)
**Action:** Add correction rule
```python
# In src/project_code_correction.py
# Add normalization:
if code.startswith('HCST') and not code.startswith('PJHCST'):
    corrected_code = 'PJ' + code
    corrections['changes_made'].append(
        f"Added PJ prefix to HCST code: {code} → {corrected_code}"
    )
```

### Option 3: Check the actual images to confirm
**Action:** Review the source images to see what's actually printed

---

## How to Review Images

### Download from S3:
```bash
# Download HCST image
aws s3 cp s3://timesheetocr-input-dev-016164185850/2025-10-21_17h24_57.png . --region us-east-1

# Download NTCS image
aws s3 cp s3://timesheetocr-input-dev-016164185850/2025-10-15_20h40_56.png . --region us-east-1

# Open to view
open 2025-10-21_17h24_57.png
open 2025-10-15_20h40_56.png
```

### What to Look For:

1. **In the project name line, what's in the parentheses?**
   - `(HCST314980)` → Then HCST is correct
   - `(PJHCST314980)` → Then we need to add PJ

2. **Is there a project code column?**
   - Sometimes the full code appears in a separate column

3. **Pattern consistency:**
   - Are other projects shown as `(PJ123456)` or just `(123456)`?

---

## Impact Assessment

**Current Status:**
- 14 records flagged out of 2,464 total = 0.6%
- All 14 are for Gareth Jones
- All data is stored correctly (no corruption)
- Just flagged as "suspicious" by validation

**Risk:** LOW
- Data is accurate
- Projects are identifiable
- Just a validation warning, not a data error

**If we whitelist HCST/NTCS:**
- These 14 warnings disappear
- Format violation rate drops to ~4.8%
- No data changes, just stops flagging

---

## Decision Matrix

| What You Find in Images | Recommended Action |
|-------------------------|-------------------|
| Shows `(HCST314980)` | Whitelist HCST/NTCS prefixes (Option 1) |
| Shows `(PJHCST314980)` | Add PJ prefix correction (Option 2) |
| Shows both variants | Keep current system, add to master list with aliases |
| Unclear/varies | Mark as "needs manual review" category |

---

## Files for Reference

**Images:**
- `2025-10-21_17h24_57.png` (HCST)
- `2025-10-15_20h40_56.png` (NTCS)

**Database entries:**
```bash
# Query to see full records
aws dynamodb query \
  --table-name TimesheetOCR-dev \
  --key-condition-expression "ResourceName = :rn" \
  --filter-expression "ProjectCode = :pc" \
  --expression-attribute-values '{":rn":{"S":"Gareth_Jones"},":pc":{"S":"HCST314980"}}' \
  --region us-east-1

aws dynamodb query \
  --table-name TimesheetOCR-dev \
  --key-condition-expression "ResourceName = :rn" \
  --filter-expression "ProjectCode = :pc" \
  --expression-attribute-values '{":rn":{"S":"Gareth_Jones"},":pc":{"S":"NTCS124690"}}' \
  --region us-east-1
```

---

**Next Step:** Review the actual timesheet images to determine the correct format.
