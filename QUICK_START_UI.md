# 🚀 Quick Start - Desktop UI

## Launch the UI (Choose One)

### Method 1: Double-Click (Easiest) ⭐
1. Open Finder
2. Navigate to this folder
3. **Double-click `launch_ui.command`**
4. UI opens automatically!

### Method 2: Command Line
```bash
cd /Users/gianlucaformica/Projects/clarity-timesheet-ocr-app
python3 timesheet_ui.py
```

### Method 3: Create Mac App
```bash
./create_mac_app.sh
open "Timesheet OCR.app"
```

## Using the UI

### Step 1: Select Files
1. Click **"📁 Select Files..."**
2. Browse to your timesheet images
3. Select one or more files (⌘-click for multiple)
4. Click **Open**

### Step 2: Process
1. Click **"🚀 Upload & Process"**
2. Watch the progress in the log area
3. Each file shows:
   - Upload status
   - Processing status
   - Resource name extracted
   - Number of projects found
   - Processing time
   - Cost estimate

### Step 3: Download Results
1. Click **"📥 Download Results"**
2. Choose where to save CSVs
3. All processed files download
4. Folder opens automatically

## Example Session

```
[12:00:00] Ready! Select timesheet images to upload and process.
[12:00:15] Selected 2 file(s)
[12:00:20] Processing 1/2: 2025-10-15_20h43_56.png
[12:00:21]   ⬆️  Uploading to S3...
[12:00:23]   ✓ Uploaded to s3://timesheetocr-input-dev-016164185850/2025-10-15_20h43_56.png
[12:00:24]   🚀 Triggering Lambda function...
[12:00:38]   ✓ Success!
[12:00:38]     Resource: Nik Coultas
[12:00:38]     Date Range: Sep 29 2025 - Oct 5 2025
[12:00:38]     Projects: 5
[12:00:38]     Time: 13.87s
[12:00:38]     Cost: $0.018603
[12:00:39] Processing 2/2: timesheet_2.png
...
[12:01:15] Processing complete!
[12:01:15] Success: 2/2
[12:01:15] ✓ CSV files saved to: s3://timesheetocr-output-dev-016164185850/timesheets/
```

## Keyboard Shortcuts

- **⌘Q** - Quit application
- **⌘,** - Preferences (coming soon)

## Tips

1. **Process Multiple Files** - Select up to 100 at once
2. **Monitor Progress** - Scroll through logs to see details
3. **Check Costs** - Each file shows cost estimate
4. **Quick Access** - Drag `launch_ui.command` to your Dock
5. **Stay Updated** - Cost and status shown in real-time

## Troubleshooting

### UI Won't Open
```bash
# Check Python
python3 --version  # Should be 3.11+

# Check boto3
python3 -c "import boto3; print(boto3.__version__)"
```

### "AWS Credentials Not Configured"
```bash
aws sso login
```

### Permission Denied
```bash
chmod +x launch_ui.command
chmod +x timesheet_ui.py
```

## What's Happening Behind the Scenes

1. **File Selection** → Files stored in memory (not uploaded yet)
2. **Upload** → Files sent to `s3://timesheetocr-input-dev-016164185850/`
3. **Lambda Trigger** → Function `TimesheetOCR-ocr-dev` invoked
4. **Processing** → Claude 3.5 Sonnet extracts data
5. **CSV Generation** → Structured CSV created
6. **S3 Storage** → CSV saved to `s3://timesheetocr-output-dev-016164185850/timesheets/`
7. **Download** → CSVs downloaded to your Mac

## Files Created

After processing, you'll have:
- **CSV files** - One per timesheet with all extracted data
- **Audit JSON** - Detailed logs with timestamps and costs
- **CloudWatch Logs** - Lambda execution logs (in AWS Console)

## Cost Tracking

Each timesheet shows:
- **Processing cost**: ~$0.018
- **Time taken**: ~14 seconds
- **Token usage**: Shown in audit JSON

Monthly budget for 100 timesheets: **~$1.86**

## Next Steps

1. Process your timesheet backlog
2. Download all CSVs
3. Import into your system
4. Save hours of manual work!

---

**Need help? See `UI_README.md` for detailed documentation**
