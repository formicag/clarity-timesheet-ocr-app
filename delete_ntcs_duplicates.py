#!/usr/bin/env python3
"""
Delete NTCS124690 duplicate entries for Gareth Jones.
"""
import boto3

# AWS Configuration
REGION = 'us-east-1'
TABLE_NAME = 'TimesheetOCR-dev'

# Initialize AWS client
dynamodb = boto3.client('dynamodb', region_name=REGION)

def delete_ntcs_entries():
    """Delete all NTCS124690 entries for Gareth Jones."""
    print("=" * 60)
    print("Delete NTCS124690 Duplicate Entries")
    print("=" * 60)

    # Query for Gareth_Jones entries
    print("\n🔍 Querying for Gareth_Jones entries with NTCS124690...")

    query_kwargs = {
        'TableName': TABLE_NAME,
        'KeyConditionExpression': 'ResourceName = :rn',
        'FilterExpression': 'ProjectCode = :code',
        'ExpressionAttributeValues': {
            ':rn': {'S': 'Gareth_Jones'},
            ':code': {'S': 'NTCS124690'}
        }
    }

    deleted_count = 0

    try:
        response = dynamodb.query(**query_kwargs)
        items = response.get('Items', [])

        print(f"   Found {len(items)} NTCS124690 entries to delete\n")

        for item in items:
            resource_name = item['ResourceName']['S']
            date_project_code = item['DateProjectCode']['S']
            date = item['Date']['S']
            project_code = item.get('ProjectCode', {}).get('S', 'N/A')

            print(f"   🗑️  Deleting: {date} | {project_code}")

            # Delete the item
            dynamodb.delete_item(
                TableName=TABLE_NAME,
                Key={
                    'ResourceName': {'S': resource_name},
                    'DateProjectCode': {'S': date_project_code}
                }
            )
            deleted_count += 1

        print(f"\n   ✅ Deleted {deleted_count} entries")

        # Verify
        print("\n📋 Verifying deletion...")
        response = dynamodb.query(**query_kwargs)
        remaining = len(response.get('Items', []))
        print(f"   NTCS124690 entries remaining: {remaining}")

        # Check NTC5 entries still exist
        query_kwargs['FilterExpression'] = 'ProjectCode = :code'
        query_kwargs['ExpressionAttributeValues'][':code'] = {'S': 'NTC5124690'}
        response = dynamodb.query(**query_kwargs)
        ntc5_count = len(response.get('Items', []))
        print(f"   NTC5124690 entries present: {ntc5_count}")

        if remaining == 0 and ntc5_count > 0:
            print(f"\n   ✅ SUCCESS! Duplicates removed, NTC5 entries intact")

        print("\n" + "=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        print(f"NTCS duplicates deleted: {deleted_count}")
        print(f"NTC5 correct entries: {ntc5_count}")
        print("=" * 60)

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return 0

if __name__ == '__main__':
    delete_ntcs_entries()
