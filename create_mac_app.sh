#!/bin/bash
# Create a Mac Application Bundle for Timesheet OCR UI

APP_NAME="Timesheet OCR"
APP_DIR="$APP_NAME.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

echo "Creating Mac Application Bundle..."

# Create directory structure
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# Create Info.plist
cat > "$CONTENTS_DIR/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>timesheet_ocr</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.timesheetocr.app</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Timesheet OCR</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# Create launcher script
cat > "$MACOS_DIR/timesheet_ocr" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/../Resources"
/usr/bin/python3 timesheet_ui.py
EOF

chmod +x "$MACOS_DIR/timesheet_ocr"

# Copy Python script
cp timesheet_ui.py "$RESOURCES_DIR/"

echo "✓ Application bundle created: $APP_DIR"
echo ""
echo "To use:"
echo "  1. Double-click '$APP_DIR' to launch"
echo "  2. Or drag it to your Applications folder"
echo "  3. Or run: open '$APP_DIR'"
echo ""
