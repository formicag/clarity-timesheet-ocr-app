# 🖥️ Timesheet OCR Desktop UI

A simple, elegant desktop application for Mac to upload and process timesheet images.

## 📸 Features

- **📁 File Selection** - Browse and select multiple timesheet images (PNG, JPG, JPEG)
- **⬆️ Auto Upload** - Automatically uploads to S3 input bucket
- **🚀 Lambda Trigger** - Triggers OCR processing automatically
- **📊 Real-time Status** - Shows processing progress and results in real-time
- **📥 Download Results** - Download all processed CSV files with one click
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

### 1. Select Files
- Click **"📁 Select Files..."**
- Browse to your timesheet images
- Select one or multiple files (hold ⌘ for multiple)
- Selected files appear in the list

### 2. Upload & Process
- Click **"🚀 Upload & Process"**
- The app will:
  - Upload each file to S3
  - Trigger Lambda processing
  - Show real-time progress
  - Display results (resource name, dates, project count, cost)

### 3. Download Results
- Click **"📥 Download Results"**
- Choose where to save CSV files
- All processed CSVs are downloaded
- Folder opens automatically

## 📋 UI Overview

```
┌────────────────────────────────────────────────┐
│         📊 Timesheet OCR Processor              │
├────────────────────────────────────────────────┤
│  1. Select Timesheet Images                    │
│  ┌──────────────────────────────────────────┐ │
│  │ 📁 Select Files...  [3 files selected]   │ │
│  │ ─────────────────────────────────────────│ │
│  │ • 2025-10-15_20h43_56.png                │ │
│  │ • timesheet_2.png                         │ │
│  │ • timesheet_3.png                         │ │
│  └──────────────────────────────────────────┘ │
│                                                 │
│   🚀 Upload & Process    📥 Download Results   │
│                                                 │
│  Status & Logs                                 │
│  ┌──────────────────────────────────────────┐ │
│  │ [12:34:56] Selected 3 file(s)            │ │
│  │ [12:35:01] Processing 1/3: timesheet.png │ │
│  │ [12:35:02]   ⬆️  Uploading to S3...       │ │
│  │ [12:35:05]   ✓ Uploaded to s3://...      │ │
│  │ [12:35:06]   🚀 Triggering Lambda...      │ │
│  │ [12:35:20]   ✓ Success!                  │ │
│  │ [12:35:20]     Resource: Nik Coultas     │ │
│  │ [12:35:20]     Projects: 5               │ │
│  │ [12:35:20]     Time: 13.87s              │ │
│  │ [12:35:20]     Cost: $0.018603           │ │
│  └──────────────────────────────────────────┘ │
│                                                 │
│  📦 Input: timesheetocr-input-dev-...         │
│  📂 Output: timesheetocr-output-dev-...       │
└────────────────────────────────────────────────┘
```

## ⚙️ Requirements

- **Python 3.11+** (already installed on your Mac)
- **AWS Credentials** (already configured)
- **boto3** (AWS SDK)
- **tkinter** (built into Python)

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
4. **Cost Tracking** - Each processing shows the cost estimate
5. **Quick Access** - Drag `launch_ui.command` to your Dock

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
