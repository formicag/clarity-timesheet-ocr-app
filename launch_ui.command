#!/bin/bash
# Timesheet OCR UI Launcher for Mac
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the UI
python3 timesheet_ui.py
