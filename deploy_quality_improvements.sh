#!/bin/bash
# Deploy OCR quality improvements to Lambda

set -e  # Exit on error

echo "========================================"
echo "Deploying OCR Quality Improvements"
echo "========================================"
echo ""

LAMBDA_FUNCTION="TimesheetOCR-ocr-dev"
ZIP_FILE="lambda_quality_improvements.zip"
REGION="us-east-1"

# Create a temporary directory for the deployment package
TEMP_DIR=$(mktemp -d)
echo "Creating deployment package in: $TEMP_DIR"
echo ""

# Copy all source files
echo "Copying source files..."
cp -r src/* "$TEMP_DIR/"

# Copy team roster for name normalization
echo "Copying team_roster.json..."
cp team_roster.json "$TEMP_DIR/"

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
echo "Package includes:"
echo "  ✓ Enhanced OCR prompt with project code rules"
echo "  ✓ Project code correction module (OCR digit normalization)"
echo "  ✓ Automatic format validation and correction"
echo "  ✓ Bank holiday detection"
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
echo "=" * 80
echo "NEW FEATURES DEPLOYED:"
echo "=" * 80
echo ""
echo "1. Project Code Format Validation"
echo "   - Auto-fixes missing project codes in names"
echo "   - Ensures format: 'Description (PROJECT_CODE)'"
echo ""
echo "2. Category Label Detection"
echo "   - Replaces DESIGN, LABOUR, INFRA, DATA labels"
echo "   - With actual project codes"
echo ""
echo "3. OCR Digit Confusion Correction"
echo "   - 0 ↔ 9 (most common)"
echo "   - 0 ↔ 8, 6 ↔ 5, 2 ↔ 3, 1 ↔ 7"
echo "   - Auto-corrects against master list"
echo ""
echo "4. Enhanced OCR Prompt"
echo "   - Explicit format rules"
echo "   - Digit confusion awareness"
echo "   - Leading 9 vs 0 guidance"
echo ""
echo "=" * 80
echo "NEXT STEPS:"
echo "=" * 80
echo ""
echo "1. Build master project list (if not done yet):"
echo "   python3 build_master_project_list.py"
echo ""
echo "2. Generate quality report to see current state:"
echo "   python3 generate_quality_report.py"
echo ""
echo "3. Test with known problem cases:"
echo "   - Jon Maya timesheet (DESIGN label)"
echo "   - Barry Breden timesheet (missing code)"
echo "   - Gareth Jones timesheet (HCST vs PJHCST)"
echo ""
echo "4. Monitor logs for corrections:"
echo "   📝 = Format correction applied"
echo "   ⚠️  = Suspected OCR error flagged"
echo ""
echo "5. Reprocess the 63 records with format violations"
echo ""
