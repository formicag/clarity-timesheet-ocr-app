#!/bin/bash
set -e

echo "================================================================================"
echo "TESTING ZERO-HOUR FIX FOR NIK COULTAS"
echo "================================================================================"
echo ""

REGION="us-east-1"
TABLE="TimesheetOCR-dev"
FUNCTION="TimesheetOCR-ocr-dev"
BUCKET="timesheetocr-input-dev-016164185850"
IMAGE="2025-10-20_16h04_51.png"

echo "1️⃣  DELETING ALL EXISTING NIK COULTAS ENTRIES"
echo "--------------------------------------------------------------------------------"
python3 delete_nik_coultas.py
echo ""

echo "2️⃣  WAITING 5 SECONDS FOR DELETION TO COMPLETE"
echo "--------------------------------------------------------------------------------"
sleep 5
echo ""

echo "3️⃣  VERIFYING DELETION (should show 0)"
echo "--------------------------------------------------------------------------------"
COUNT=$(aws dynamodb query \
  --table-name $TABLE \
  --key-condition-expression "ResourceName = :rn" \
  --expression-attribute-values '{":rn":{"S":"Nik_Coultas"}}' \
  --region $REGION | jq '.Count')
echo "   Current count: $COUNT"
echo ""

if [ "$COUNT" != "0" ]; then
    echo "   ⚠️  Warning: Still has $COUNT entries. Waiting another 5 seconds..."
    sleep 5
fi

echo "4️⃣  TRIGGERING LAMBDA FOR: $IMAGE"
echo "--------------------------------------------------------------------------------"
aws lambda invoke \
  --function-name $FUNCTION \
  --cli-binary-format raw-in-base64-out \
  --payload "{\"Records\":[{\"s3\":{\"bucket\":{\"name\":\"$BUCKET\"},\"object\":{\"key\":\"$IMAGE\"}}}]}" \
  --region $REGION \
  /tmp/test_result.json > /dev/null 2>&1

echo "   ✅ Lambda invoked successfully"
echo ""

echo "5️⃣  WAITING 30 SECONDS FOR OCR TO COMPLETE"
echo "--------------------------------------------------------------------------------"
for i in {30..1}; do
    echo -ne "   Waiting: $i seconds remaining...\r"
    sleep 1
done
echo ""
echo ""

echo "6️⃣  CHECKING DATABASE ENTRIES"
echo "--------------------------------------------------------------------------------"
COUNT=$(aws dynamodb query \
  --table-name $TABLE \
  --key-condition-expression "ResourceName = :rn" \
  --expression-attribute-values '{":rn":{"S":"Nik_Coultas"}}' \
  --region $REGION | jq '.Count')

echo "   📊 Total entries created: $COUNT"
echo ""

if [ "$COUNT" == "3" ]; then
    echo "   ✅ SUCCESS! Only 3 entries created (expected: 3 days worked)"
elif [ "$COUNT" == "21" ]; then
    echo "   ❌ FAILED! 21 entries created (bug still present: 7 days × 3 projects)"
else
    echo "   ⚠️  Unexpected count: $COUNT entries"
fi
echo ""

echo "7️⃣  LISTING ALL ENTRIES FOR NIK COULTAS"
echo "--------------------------------------------------------------------------------"
aws dynamodb query \
  --table-name $TABLE \
  --key-condition-expression "ResourceName = :rn" \
  --expression-attribute-values '{":rn":{"S":"Nik_Coultas"}}' \
  --region $REGION | jq -r '.Items[] | [.ResourceName.S, .DateProjectCode.S, .ProjectCode.S, .Hours.N] | @tsv' | \
  awk -F'\t' '{printf "   %-15s %-25s %-12s %s hours\n", $1, $2, $3, $4}'
echo ""

echo "================================================================================"
echo "TEST COMPLETE"
echo "================================================================================"
echo ""
echo "Expected Result: 3 entries"
echo "  - 2025-10-06 MoneyMap (PJ024075): 7.5 hours"
echo "  - 2025-10-09 ACE Commission (PJ024300): 7.5 hours"
echo "  - 2025-10-10 5G SA (DATA0114): 7.5 hours"
echo ""
echo "If you see more than 3 entries, the fix did not work correctly."
echo ""
