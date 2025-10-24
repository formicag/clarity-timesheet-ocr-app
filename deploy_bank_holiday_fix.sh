#!/bin/bash
# Deploy bank holiday fix to Lambda

set -e  # Exit on error

echo "========================================"
echo "Deploying Bank Holiday Fix to Lambda"
echo "========================================"
echo ""

LAMBDA_FUNCTION="TimesheetOCR-ocr-dev"
ZIP_FILE="lambda_bank_holiday_fix.zip"
REGION="us-east-1"

# Create a temporary directory for the deployment package
TEMP_DIR=$(mktemp -d)
echo "Creating deployment package in: $TEMP_DIR"
echo ""

# Copy all source files
echo "Copying source files..."
cp -r src/* "$TEMP_DIR/"

# Create the zip file
echo "Creating zip archive..."
cd "$TEMP_DIR"
zip -r "$ZIP_FILE" .
mv "$ZIP_FILE" "$OLDPWD/"
cd "$OLDPWD"

# Clean up temp directory
rm -rf "$TEMP_DIR"

echo ""
echo "Deployment package created: $ZIP_FILE"
echo "Size: $(ls -lh $ZIP_FILE | awk '{print $5}')"
echo ""

# Update Lambda function
echo "Updating Lambda function: $LAMBDA_FUNCTION"
echo "Region: $REGION"
echo ""

aws lambda update-function-code \
    --function-name "$LAMBDA_FUNCTION" \
    --zip-file "fileb://$ZIP_FILE" \
    --region "$REGION" \
    > /dev/null

echo "✅ Lambda function updated successfully!"
echo ""
echo "Waiting for function to be ready..."
aws lambda wait function-updated \
    --function-name "$LAMBDA_FUNCTION" \
    --region "$REGION"

echo "✅ Function is ready!"
echo ""
echo "New features:"
echo "  - UK Bank Holidays 2025 detection"
echo "  - Automatic zero hours enforcement on bank holidays"
echo "  - Aug 25, 2025 (Summer bank holiday) will now be handled correctly"
echo ""
echo "To test the fix, run:"
echo "  python3 test_bank_holiday.py"
echo ""
