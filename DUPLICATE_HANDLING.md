# 🔒 Duplicate Detection & Handling

## Overview

The Timesheet OCR system now includes **automatic duplicate detection** to prevent processing the same timesheet multiple times.

---

## 🎯 How It Works

### Built-in DynamoDB Protection

**Primary Key Structure:**
```
Partition Key: ResourceName (e.g., "Nik_Coultas")
Sort Key: DateProjectCode (e.g., "2025-09-29#PJ021931")
```

**This means:**
- Each combination of `Resource + Date + Project` is **unique**
- Uploading the same timesheet twice will **OVERWRITE** the previous entry
- **No true duplicates** can exist in the database

---

## ✅ What Happens When You Re-upload

### Scenario: Upload the same timesheet twice

**First Upload:**
```
File: timesheet_2025-10-01.png
Resource: Nik Coultas
Date Range: Sep 29 - Oct 5, 2025
Projects: PJ021931 (35 hours total)

Result: ✓ 7 entries created (7 days × 1 project)
```

**Second Upload (Same File):**
```
File: timesheet_2025-10-01.png (uploaded again)
Resource: Nik Coultas
Date Range: Sep 29 - Oct 5, 2025
Projects: PJ021931 (35 hours total)

Detection: ⚠️  Found 7 existing entries
Action: OVERWRITES previous 7 entries with new data
Result: Still 7 entries (not 14!)
```

---

## 🛡️ Duplicate Detection Features

### 1. **Automatic Detection**
Lambda automatically checks for existing entries before storing:
- Queries DynamoDB for matching Resource + Date Range
- Logs warning if duplicates found
- Shows which source images created previous entries

### 2. **CloudWatch Logs**
Every upload logs duplicate status:
```
✓ No duplicates found - new entries will be created
```
OR
```
⚠️  Duplicate detection: Found 7 existing entries from 1 source(s)
   Previous sources: timesheet_old.png
   Will overwrite 7 existing entries
```

### 3. **Response Metadata**
Lambda response includes duplicate information:
```json
{
  "duplicate_info": {
    "was_duplicate": true,
    "overwritten_entries": 7
  }
}
```

---

## 📊 What Gets Overwritten

When a duplicate is detected and overwritten:

### ✅ **Updated Fields:**
- `Hours` - New hours value
- `SourceImage` - New image filename
- `ProcessingTimestamp` - New timestamp
- `ProcessingTimeSeconds` - New processing time
- `ModelId` - Current model used
- `InputTokens` - New token count
- `OutputTokens` - New token count
- `CostEstimateUSD` - New cost estimate

### ⚠️  **Lost Information:**
- Previous `SourceImage` name
- Previous `ProcessingTimestamp`
- Previous processing metadata

---

## 🎨 UI Behavior

The Desktop UI shows duplicate warnings in the logs:

```
[12:30:15] Processing 1/1: timesheet_2025-10-01.png
[12:30:16]   ⬆️  Uploading to S3...
[12:30:18]   ✓ Uploaded
[12:30:19]   🚀 Triggering Lambda function...
[12:30:32]   ✓ Success!
[12:30:32]     Resource: Nik Coultas
[12:30:32]     Entries Stored: 7
[12:30:32]     ⚠️  Duplicate: Overwrote 7 existing entries
```

---

## 🔍 Checking for Duplicates Manually

### Via Desktop UI:
1. Click **"📊 View Data"**
2. Look for same Resource + Date + Project combinations
3. Check `SourceImage` column to see which file created each entry

### Via AWS Console:
1. Go to DynamoDB → Tables → `TimesheetOCR-dev`
2. Click **"Explore table items"**
3. Filter by ResourceName and Date to see entries

### Via CLI:
```bash
aws dynamodb query \
  --table-name TimesheetOCR-dev \
  --key-condition-expression "ResourceName = :rn AND begins_with(DateProjectCode, :date)" \
  --expression-attribute-values '{
    ":rn": {"S": "Nik_Coultas"},
    ":date": {"S": "2025-09-29"}
  }'
```

---

## 🚨 Common Scenarios

### Scenario 1: Uploading Corrected Timesheet
**Problem:** Made a mistake in original timesheet, need to upload corrected version

**Solution:** Just upload the corrected timesheet
- ✅ Old entries will be overwritten with correct hours
- ✅ Database stays clean (no duplicates)
- ✅ Latest data is always used

### Scenario 2: Multiple People Same Week
**Problem:** Processing multiple timesheets for same week

**Solution:** No conflicts!
- ✅ Different ResourceName = Different partition key
- ✅ Each person's data is isolated
- ✅ Safe to upload all timesheets for same week

### Scenario 3: Same Person, Different Projects
**Problem:** Person has multiple projects in same week

**Solution:** Works perfectly!
- ✅ Different ProjectCode = Different sort key
- ✅ Each project tracked separately
- ✅ All hours calculated correctly in reports

### Scenario 4: Accidentally Upload Same File Twice
**Problem:** Clicked upload twice on same file

**Solution:** No problem!
- ✅ Second upload overwrites first
- ✅ No duplicate entries created
- ✅ Cost: Only 2× processing cost (minimal)

---

## 💡 Best Practices

### ✅ **DO:**
1. **Upload corrected timesheets** - Old data is safely overwritten
2. **Process all timesheets weekly** - Each person/week is isolated
3. **Re-upload if hours change** - Database stays current
4. **Check CloudWatch logs** - See duplicate warnings if concerned

### ❌ **DON'T:**
1. **Worry about duplicates** - System handles it automatically
2. **Manually delete entries** - Just re-upload with correct data
3. **Skip uploads due to duplicate fears** - Overwrites are safe and intentional

---

## 📈 Reporting Impact

### Download Report Button
The "📥 Download Report" button **automatically handles duplicates**:
- ✅ Groups by Resource + Project
- ✅ Sums hours across all dates
- ✅ Uses latest data (if overwrites occurred)
- ✅ No duplicate rows in report

**Example Report Output:**
```csv
Resource Name,Project Code,Project Name,Total Hours
Nik Coultas,PJ021931,(NDA) Fixed Transformation,105.00
```
If same timesheet uploaded 3 times, report still shows `105.00` (not `315.00`)

---

## 🔧 Technical Details

### DynamoDB PutItem Behavior
```python
# This code OVERWRITES if key exists:
table.put_item(Item={
    'ResourceName': 'Nik_Coultas',
    'DateProjectCode': '2025-09-29#PJ021931',
    'Hours': 7.5
})
```

**NOT:**
- ❌ Creates duplicate entry
- ❌ Adds to existing hours
- ❌ Keeps both old and new

**INSTEAD:**
- ✅ Replaces entire item
- ✅ Updates all attributes
- ✅ Maintains single entry

### Source Image Tracking
Each entry stores:
```json
{
  "SourceImage": "timesheet_2025-10-01.png",
  "ProcessingTimestamp": "2025-10-16T12:30:32Z"
}
```

**Limitation:** If you overwrite, you lose track of the original source image.

**Workaround (if needed):** Check CloudWatch Logs for historical processing records.

---

## 📊 Monitoring Duplicates

### CloudWatch Logs Query
```
filter @message like /Duplicate detection/
| fields @timestamp, @message
| sort @timestamp desc
| limit 20
```

This shows all duplicate detections in the last processing runs.

### DynamoDB Item History
DynamoDB doesn't keep version history by default. If you need audit trail:

**Option 1:** Enable DynamoDB Streams + Lambda to log changes
**Option 2:** Check CloudWatch Logs for processing history
**Option 3:** Keep source images in S3 with timestamps

---

## 🎯 Summary

### Current Behavior:
✅ **Duplicates are automatically prevented** by DynamoDB key structure
✅ **Re-uploads overwrite old data** with new values
✅ **Detection logs warnings** to CloudWatch
✅ **UI shows duplicate info** in processing logs
✅ **Reports handle duplicates correctly** through aggregation

### Future Enhancements (Optional):
- [ ] Add DynamoDB Streams to track all changes
- [ ] Create separate audit table for processing history
- [ ] Add UI confirmation dialog before overwriting
- [ ] Store multiple source images per entry (array)
- [ ] Add "revert to previous version" feature

---

**The duplicate handling system is production-ready and requires no user action!** 🎉
