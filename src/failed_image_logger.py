"""
Failed Image Logger

Tracks all OCR failures with comprehensive diagnostic information for pattern analysis.

DynamoDB Schema:
  Partition Key: ImageKey (S) - The S3 image filename
  Sort Key: FailureTimestamp (S) - ISO timestamp of failure

  Attributes:
    - FailureType: Type of failure (OCR_ERROR, PARSING_ERROR, VALIDATION_ERROR, etc.)
    - ErrorMessage: Full error message/traceback
    - ErrorCode: Specific error code if available
    - OCRVersion: OCR solution version at time of failure
    - OCRBuildDate: OCR build date
    - ModelId: AI model used
    - ProcessingTimeSeconds: How long before failure
    - InputTokens: Tokens used (if available)
    - OutputTokens: Tokens generated (if available)
    - RawOCROutput: The raw OCR text output (if parsing failed)
    - ValidationErrors: Validation error details (if validation failed)
    - S3Bucket: Source bucket
    - S3Region: Source region
    - ImageSize: Image file size in bytes
    - AttemptNumber: How many times this image has failed
    - LastSuccessfulOCR: Timestamp of last successful OCR (if any)
    - StackTrace: Full Python stack trace
    - CloudWatchLogStream: Log stream for detailed debugging
"""
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')


def convert_float_to_decimal(value):
    """Convert float to Decimal for DynamoDB."""
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def log_failed_image(
    table_name: str,
    image_key: str,
    failure_type: str,
    error_message: str,
    ocr_version: Dict[str, str],
    error_details: Optional[Dict[str, Any]] = None,
    image_metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Log a failed OCR attempt with comprehensive diagnostic information.

    Args:
        table_name: DynamoDB table name
        image_key: S3 image key
        failure_type: Type of failure (OCR_ERROR, PARSING_ERROR, VALIDATION_ERROR, etc.)
        error_message: Error message
        ocr_version: OCR version dict from ocr_version module
        error_details: Additional error context
        image_metadata: Optional image metadata (resolution, format, size, etc.)

    Returns:
        True if logged successfully, False otherwise
    """
    table = dynamodb.Table(table_name)

    # Get current timestamp
    failure_timestamp = datetime.utcnow().isoformat() + 'Z'

    # Build failure record
    failure_record = {
        # Primary keys
        'ImageKey': image_key,
        'FailureTimestamp': failure_timestamp,

        # Failure classification
        'FailureType': failure_type,
        'ErrorMessage': error_message[:5000],  # Limit to 5000 chars
        'RecordType': 'FAILED_IMAGE',

        # OCR system version
        'OCRVersion': ocr_version.get('version', 'unknown'),
        'OCRBuildDate': ocr_version.get('build_date', 'unknown'),
        'OCRDescription': ocr_version.get('description', 'unknown'),
        'OCRFullVersion': ocr_version.get('full_version', 'unknown'),
    }

    # Add optional error details if provided
    if error_details:
        if 'error_code' in error_details:
            failure_record['ErrorCode'] = error_details['error_code']

        if 'model_id' in error_details:
            failure_record['ModelId'] = error_details['model_id']

        if 'processing_time' in error_details:
            failure_record['ProcessingTimeSeconds'] = convert_float_to_decimal(error_details['processing_time'])

        if 'input_tokens' in error_details:
            failure_record['InputTokens'] = error_details['input_tokens']

        if 'output_tokens' in error_details:
            failure_record['OutputTokens'] = error_details['output_tokens']

        if 'raw_ocr_output' in error_details:
            # Store first 10000 chars of raw output for analysis
            failure_record['RawOCROutput'] = str(error_details['raw_ocr_output'])[:10000]

        if 'validation_errors' in error_details:
            failure_record['ValidationErrors'] = str(error_details['validation_errors'])[:2000]

        if 's3_bucket' in error_details:
            failure_record['S3Bucket'] = error_details['s3_bucket']

        if 's3_region' in error_details:
            failure_record['S3Region'] = error_details['s3_region']

        if 'image_size' in error_details:
            failure_record['ImageSize'] = error_details['image_size']

        if 'stack_trace' in error_details:
            failure_record['StackTrace'] = error_details['stack_trace'][:5000]

        if 'cloudwatch_log_stream' in error_details:
            failure_record['CloudWatchLogStream'] = error_details['cloudwatch_log_stream']

        if 'attempt_number' in error_details:
            failure_record['AttemptNumber'] = error_details['attempt_number']

    # Add image metadata if available
    if image_metadata:
        failure_record.update(image_metadata)

    try:
        # Write to DynamoDB
        table.put_item(Item=failure_record)

        print(f"📝 Logged failure for {image_key}: {failure_type}")
        return True

    except Exception as e:
        print(f"⚠️  Failed to log failure for {image_key}: {e}")
        return False


def get_attempt_count(table_name: str, image_key: str) -> int:
    """
    Get the number of times this image has failed OCR.

    Args:
        table_name: DynamoDB table name
        image_key: S3 image key

    Returns:
        Number of previous failure attempts
    """
    table = dynamodb.Table(table_name)

    try:
        response = table.query(
            KeyConditionExpression='ImageKey = :key',
            ExpressionAttributeValues={':key': image_key},
            Select='COUNT'
        )
        return response.get('Count', 0)
    except Exception as e:
        print(f"⚠️  Could not get attempt count for {image_key}: {e}")
        return 0


def get_all_failed_images(table_name: str) -> list:
    """
    Get all failed images with their failure details.

    Returns:
        List of failed image records sorted by most recent failure
    """
    table = dynamodb.Table(table_name)

    try:
        # Scan for all FAILED_IMAGE records
        response = table.scan(
            FilterExpression='RecordType = :type',
            ExpressionAttributeValues={':type': 'FAILED_IMAGE'}
        )

        failed_images = response.get('Items', [])

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression='RecordType = :type',
                ExpressionAttributeValues={':type': 'FAILED_IMAGE'},
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            failed_images.extend(response.get('Items', []))

        # Sort by most recent failure
        failed_images.sort(key=lambda x: x.get('FailureTimestamp', ''), reverse=True)

        return failed_images

    except Exception as e:
        print(f"⚠️  Failed to get failed images: {e}")
        return []


def export_failed_images_csv(table_name: str, output_file: str) -> int:
    """
    Export all failed images to a CSV file.

    Args:
        table_name: DynamoDB table name
        output_file: Path to output CSV file

    Returns:
        Number of records exported
    """
    import csv

    failed_images = get_all_failed_images(table_name)

    if not failed_images:
        print("No failed images to export")
        return 0

    # Define CSV columns
    columns = [
        'ImageKey',
        'FailureTimestamp',
        'FailureType',
        'ErrorMessage',
        'ErrorCode',
        'OCRVersion',
        'OCRBuildDate',
        'OCRFullVersion',
        'ModelId',
        'ProcessingTimeSeconds',
        'InputTokens',
        'OutputTokens',
        'ValidationErrors',
        'S3Bucket',
        'ImageSize',
        'AttemptNumber',
        'CloudWatchLogStream',
        'RawOCROutput',
        'StackTrace'
    ]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()

        for item in failed_images:
            # Convert Decimal to float for CSV
            row = {}
            for col in columns:
                value = item.get(col, '')
                if isinstance(value, Decimal):
                    row[col] = float(value)
                else:
                    row[col] = value
            writer.writerow(row)

    print(f"✅ Exported {len(failed_images)} failed images to {output_file}")
    return len(failed_images)


def get_failure_statistics(table_name: str) -> Dict[str, Any]:
    """
    Get statistics about failures for analysis.

    Returns:
        Dictionary with failure statistics
    """
    failed_images = get_all_failed_images(table_name)

    if not failed_images:
        return {
            'total_failures': 0,
            'unique_images': 0,
            'failure_types': {},
            'ocr_versions': {},
            'recent_failures_24h': 0
        }

    # Count failure types
    failure_types = {}
    ocr_versions = {}
    unique_images = set()
    recent_failures = 0

    now = datetime.utcnow()

    for item in failed_images:
        # Count failure types
        ftype = item.get('FailureType', 'UNKNOWN')
        failure_types[ftype] = failure_types.get(ftype, 0) + 1

        # Count OCR versions
        version = item.get('OCRFullVersion', 'unknown')
        ocr_versions[version] = ocr_versions.get(version, 0) + 1

        # Track unique images
        unique_images.add(item.get('ImageKey', ''))

        # Count recent failures (last 24 hours)
        timestamp_str = item.get('FailureTimestamp', '')
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            age_hours = (now - timestamp.replace(tzinfo=None)).total_seconds() / 3600
            if age_hours < 24:
                recent_failures += 1
        except:
            pass

    return {
        'total_failures': len(failed_images),
        'unique_images': len(unique_images),
        'failure_types': failure_types,
        'ocr_versions': ocr_versions,
        'recent_failures_24h': recent_failures
    }
