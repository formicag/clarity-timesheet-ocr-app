#!/usr/bin/env python3
"""
Export DynamoDB data to S3 in a format QuickSight can read.
This creates a CSV file that Athena can query.
"""
import boto3
import csv
import json
from datetime import datetime
from decimal import Decimal

# Configuration
DYNAMODB_TABLE = 'TimesheetOCR-dev'
S3_BUCKET = 'timesheetocr-input-dev-016164185850'  # Reusing existing bucket
S3_KEY_PREFIX = 'quicksight-data/'
AWS_REGION = 'us-east-1'

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
s3_client = boto3.client('s3', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE)


def decimal_to_float(obj):
    """Convert Decimal to float for JSON/CSV compatibility."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj


def export_dynamodb_to_csv():
    """Export all DynamoDB data to CSV file."""
    print(f"📊 Exporting DynamoDB table: {DYNAMODB_TABLE}")

    # Scan DynamoDB table
    response = table.scan()
    items = response.get('Items', [])

    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))

    print(f"✓ Found {len(items)} entries")

    if not items:
        print("❌ No data found in DynamoDB table")
        return

    # Convert Decimals to floats
    items = [decimal_to_float(item) for item in items]

    # Define CSV columns (QuickSight-friendly format)
    csv_columns = [
        'ResourceName',
        'ResourceNameDisplay',
        'Date',
        'YearMonth',
        'ProjectCode',
        'ProjectName',
        'Hours',
        'WeekStartDate',
        'WeekEndDate',
        'SourceImage',
        'ProcessingTimestamp',
        'ProcessingTimeSeconds',
        'ModelId',
        'InputTokens',
        'OutputTokens',
        'CostEstimateUSD'
    ]

    # Create CSV in memory
    csv_filename = f'timesheet_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    local_path = f'/tmp/{csv_filename}'

    with open(local_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_columns, extrasaction='ignore')
        writer.writeheader()

        for item in items:
            # Write row (missing fields will be empty)
            writer.writerow(item)

    print(f"✓ Created CSV file: {local_path}")

    # Upload to S3
    s3_key = f"{S3_KEY_PREFIX}{csv_filename}"
    print(f"📤 Uploading to S3: s3://{S3_BUCKET}/{s3_key}")

    s3_client.upload_file(
        local_path,
        S3_BUCKET,
        s3_key,
        ExtraArgs={'ContentType': 'text/csv'}
    )

    print(f"✅ Successfully exported to S3!")
    print(f"\n📍 S3 Location: s3://{S3_BUCKET}/{s3_key}")
    print(f"\n🎯 Next Steps:")
    print(f"1. In QuickSight, click 'Create dataset'")
    print(f"2. Choose 'Amazon S3'")
    print(f"3. Create a manifest file (see instructions below)")
    print(f"4. Or use Amazon Athena to query this CSV")

    return s3_key


def create_athena_table():
    """Create Athena table DDL statement."""
    s3_location = f"s3://{S3_BUCKET}/{S3_KEY_PREFIX}"

    ddl = f"""
-- Run this in Amazon Athena to create a queryable table

CREATE EXTERNAL TABLE IF NOT EXISTS timesheet_data (
    ResourceName STRING,
    ResourceNameDisplay STRING,
    Date DATE,
    YearMonth STRING,
    ProjectCode STRING,
    ProjectName STRING,
    Hours DOUBLE,
    WeekStartDate DATE,
    WeekEndDate DATE,
    SourceImage STRING,
    ProcessingTimestamp TIMESTAMP,
    ProcessingTimeSeconds DOUBLE,
    ModelId STRING,
    InputTokens INT,
    OutputTokens INT,
    CostEstimateUSD DOUBLE
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '{s3_location}'
TBLPROPERTIES ('skip.header.line.count'='1');
"""

    athena_file = '/tmp/create_athena_table.sql'
    with open(athena_file, 'w') as f:
        f.write(ddl)

    print(f"\n📝 Athena DDL saved to: {athena_file}")
    print(f"\n{ddl}")

    return ddl


if __name__ == "__main__":
    print("="*60)
    print("DynamoDB → S3 Export for QuickSight")
    print("="*60)

    try:
        # Export to CSV
        s3_key = export_dynamodb_to_csv()

        # Create Athena table DDL
        create_athena_table()

        print("\n" + "="*60)
        print("✅ EXPORT COMPLETE!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
