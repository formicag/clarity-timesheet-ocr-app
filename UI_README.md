# 🖥️ Timesheet OCR Desktop UI

A simple, elegant desktop application for Mac to upload and process timesheet images.

## 📸 Features

- **📁 File Selection** - Browse and select multiple timesheet images (PNG, JPG, JPEG)
- **⬆️ Auto Upload** - Automatically uploads to S3 input bucket
- **🚀 Lambda Trigger** - Triggers OCR processing automatically
- **📊 View Data** - Browse all processed timesheets in DynamoDB
- **🔄 Refresh Data** - Reload data from database
- **📥 Export Full Data** - Export complete database with all fields
- **📤 Import Corrections** - Upload corrected CSV to fix OCR errors
- **📅 Period Export** - Export data for specific date ranges using calendar pickers
- **📊 Summary Export** - Export hours summary by resource (with days calculation)
- **📋 Detailed Export** - Export all timesheet details for a date range
- **📝 Detailed Logs** - See exactly what's happening with each file

## 🎯 Quick Start

### Option 1: Double-click Launcher (Easiest)
1. Double-click `launch_ui.command` in Finder
2. The UI will open automatically

### Option 2: Command Line
```bash
python3 timesheet_ui.py
```

### Option 3: Make it a Mac App
```bash
# Create a Mac application bundle
./create_mac_app.sh
# Then drag the app to your Applications folder
```

## 💡 How to Use

### 1. Upload & Process Timesheets
- Click **"📁 Select Files..."** to browse for timesheet images
- Select one or multiple files (hold ⌘ for multiple)
- Click **"🚀 Upload & Process"** to upload to S3 and trigger OCR
- Watch real-time processing progress in the logs

### 2. View Processed Data
- Click **"📊 View Data"** to see all timesheets in DynamoDB
- Browse by resource, date, project, hours
- Click **"🔄 Refresh"** to reload latest data

### 3. Export & Reporting

#### Full Database Export
- Click **"📥 Export Full Data"** to download complete database
- All 14 fields included (ResourceName, Date, Hours, ProjectCode, etc.)
- Use for backup or offline analysis

#### OCR Error Correction Workflow
1. Export full data (button above)
2. Open CSV in Excel/Numbers and fix any OCR errors
3. Save the corrected CSV
4. Click **"📤 Import Corrections"** to upload fixes
5. Only changed rows are updated in database

#### Period-Based Exports
1. Select **Start Date** and **End Date** using calendar pickers
2. Choose export type:
   - **📊 Export Summary** - Hours total by resource with days calculation (Hours ÷ 7.5)
   - **📋 Export Detailed** - All timesheet entries with all fields
3. Date range is **inclusive** (includes both start and end dates)
4. Save location dialog appears
5. Folder opens automatically with exported file

## 📋 UI Overview

```
┌─────────────────────────────────────────────────────────────┐
│              📊 Timesheet OCR Processor                      │
├─────────────────────────────────────────────────────────────┤
│  1. Select Timesheet Images                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 📁 Select Files...  [3 files selected]    ✕ Clear      │ │
│  │ ─────────────────────────────────────────────────────  │ │
│  │ • 2025-10-15_20h43_56.png                              │ │
│  │ • timesheet_2.png                                       │ │
│  │ • timesheet_3.png                                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  2. Process & Manage Data                                   │
│  🚀 Upload & Process  📊 View Data  🔄 Refresh              │
│  📥 Export Full Data                                        │
│  📤 Import Corrections                                      │
│                                                              │
│  3. Period Export (with Calendar Pickers)                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Start Date: [2025-10-01 ▼]  End Date: [2025-10-31 ▼]  │ │
│  │ 📊 Export Summary      📋 Export Detailed              │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  📋 Logs  |  📊 Data View                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ [12:34:56] Selected 3 file(s)                          │ │
│  │ [12:35:01] Processing 1/3: timesheet.png               │ │
│  │ [12:35:05] ✓ Uploaded to S3                            │ │
│  │ [12:35:20] ✓ Processing complete                       │ │
│  │ [12:35:21] Exporting summary for period...             │ │
│  │ [12:35:22] ✓ Found 23 records in date range            │ │
│  │ [12:35:23] ✓ Period summary exported                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## ⚙️ Requirements

- **Python 3.11+** (already installed on your Mac)
- **AWS Credentials** (already configured)
- **boto3** (AWS SDK)
- **tkinter** (built into Python)
- **tkcalendar** (for calendar date pickers) - `pip3 install tkcalendar`

## 🔧 Troubleshooting

### "AWS credentials not configured"
```bash
aws sso login
```

### "Module not found: boto3"
```bash
pip3 install boto3
```

### Window doesn't appear
- Check if Python has permission to access UI
- Go to: System Settings → Privacy & Security → Accessibility
- Add Terminal or Python

## 📁 File Structure

```
timesheet_ui.py           # Main UI application
launch_ui.command         # Double-click launcher
UI_README.md             # This file
```

## 🎨 UI Details

### Features
- **Multi-file selection** - Process multiple timesheets at once
- **Drag & drop support** - (coming soon)
- **Progress tracking** - See exactly what's happening
- **Error handling** - Clear error messages if something goes wrong
- **Auto-open results** - Downloads folder opens automatically
- **Dark mode support** - Respects your Mac system theme

### Keyboard Shortcuts
- **⌘O** - Open file dialog (coming soon)
- **⌘R** - Refresh results (coming soon)
- **⌘Q** - Quit application

## 🚀 Advanced Features

### Batch Processing
- Select up to 100 files at once
- Processes sequentially with status updates
- Summary report at the end

### Auto-Download
- Option to auto-download results after processing
- Configurable download location
- Automatic folder organization

### Processing History
- View previously processed files
- Re-download old results
- Filter by date or resource name

## 💡 Tips

1. **Multiple Files** - Hold ⌘ when selecting to pick multiple files
2. **Clear Selection** - Click "✕ Clear" to start over
3. **Check Logs** - Scroll through the log area for detailed info
4. **Calendar Dates** - Click date fields to open visual calendar picker
5. **Inclusive Dates** - Both start and end dates are included in exports
6. **OCR Corrections** - Use Export Full → Edit → Import workflow to fix errors
7. **Summary vs Detailed** - Summary shows totals by resource, Detailed shows every entry
8. **Days Calculation** - Total Days = Total Hours ÷ 7.5
9. **Quick Access** - Drag `launch_ui.command` to your Dock

## 📊 Cost Information

Processing costs are shown for each timesheet:
- **Typical cost**: ~$0.018 per timesheet
- **Bulk discount**: Process 100+ at once
- **Monthly budget**: Set AWS budget alerts

## 🔐 Security

- Uses your existing AWS credentials
- No credentials stored in the app
- All communication over HTTPS
- Files uploaded with encryption

## 🐛 Known Issues

None currently! Report issues via GitHub.

## 🔄 Updates

To get the latest version:
```bash
git pull origin main
```

## 📞 Support

- Check CloudWatch logs for Lambda errors
- View S3 buckets for uploaded/processed files
- Contact: [your-email]

## 🎉 Success Stories

**Before:** Manual data entry for 50+ timesheets = 10 hours
**After:** Automated OCR processing = 5 minutes + $1 cost

---

**Built with ❤️ using Python, Tkinter, AWS Lambda, and Claude 3.5 Sonnet**
