# Image Metadata Implementation

## Overview

The OCR system now captures comprehensive image metadata for every processed screenshot. This allows analysis of what image characteristics correlate with OCR success vs. failure.

## Metadata Fields Captured

For each timesheet screenshot, the following 13 metadata fields are extracted and stored in DynamoDB:

### Resolution & Quality
- **ImageWidth**: Width in pixels (e.g., 1920)
- **ImageHeight**: Height in pixels (e.g., 1080)
- **AspectRatio**: Width/height ratio (e.g., 1.778 for 16:9)
- **Megapixels**: Total pixels in millions (e.g., 2.07)
- **ResolutionCategory**: 4K, QHD, FULL_HD, HD, or BELOW_HD
- **QualityCategory**: HIGH (≥1920x1080), MEDIUM (≥1280x720), or LOW

### File Information
- **FileSizeBytes**: File size in bytes
- **FileSizeKB**: File size in kilobytes (decimal)
- **BytesPerPixel**: Compression ratio indicator
- **ImageFormat**: File format (PNG, JPEG, etc.)
- **ImageMode**: Color mode (RGB, RGBA, L, etc.)

### DPI (Dots Per Inch)
- **DPI_X**: Horizontal DPI (if available)
- **DPI_Y**: Vertical DPI (if available)

## Resolution Categories

Images are automatically categorized by resolution for easier analysis:

| Category | Threshold | Example Resolutions |
|----------|-----------|-------------------|
| **4K** | ≥90% of 3840×2160 | 3840×2160, 4096×2160 |
| **QHD** | ≥90% of 2560×1440 | 2560×1440, 2880×1620 |
| **FULL_HD** | ≥90% of 1920×1080 | 1920×1080, 2048×1152 |
| **HD** | ≥90% of 1280×720 | 1280×720, 1366×768 |
| **BELOW_HD** | <90% of 1280×720 | 1024×768, 800×600 |

## Quality Categories

Based on minimum resolution thresholds:

- **HIGH**: Width ≥1920 AND Height ≥1080 (Full HD or better)
- **MEDIUM**: Width ≥1280 AND Height ≥720 (HD)
- **LOW**: Below HD thresholds

## Where Metadata is Stored

The metadata is stored with:

1. **Successful timesheet entries** - All regular timesheet data entries
2. **Zero-hour timesheets** - Absence/leave records
3. **Failed images** - OCR failures for pattern analysis

## Implementation Files

### New Files
- **`src/image_metadata.py`**: Core metadata extraction logic
  - `extract_image_metadata()`: Extracts all 13 metadata fields
  - `_categorize_resolution()`: Categorizes by resolution
  - `get_image_stats_summary()`: Human-readable summary

### Modified Files
- **`src/lambda_function.py`** (lines 523-526, 663, 760):
  - Extracts metadata after image download
  - Passes metadata to DynamoDB handler
  - Includes metadata in failure logging

- **`src/dynamodb_handler.py`** (lines 91, 116, 188, 333):
  - Added `image_metadata` parameter to `store_timesheet_entries()`
  - Stores metadata with zero-hour timesheets
  - Stores metadata with regular timesheet entries

- **`src/failed_image_logger.py`** (lines 53, 65, 137):
  - Added `image_metadata` parameter to `log_failed_image()`
  - Stores metadata with all failed image records

## Usage Examples

### Query High-Quality Images
```python
import boto3
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('TimesheetOCR-dev')

response = table.scan(
    FilterExpression='QualityCategory = :quality AND RecordType = :type',
    ExpressionAttributeValues={
        ':quality': 'HIGH',
        ':type': 'TIMESHEET_ENTRY'
    }
)
```

### Analyze Failed Images by Resolution
```python
from src.failed_image_logger import get_all_failed_images

failed = get_all_failed_images('TimesheetOCR-dev')

# Group by resolution category
by_resolution = {}
for item in failed:
    category = item.get('ResolutionCategory', 'UNKNOWN')
    by_resolution[category] = by_resolution.get(category, 0) + 1

print(by_resolution)
# Output: {'FULL_HD': 45, 'QHD': 12, 'HD': 3, 'BELOW_HD': 1}
```

### Find Large File Sizes That Failed
```python
# Files over 1MB that failed OCR
large_failed = [
    item for item in failed
    if float(item.get('FileSizeKB', 0)) > 1024
]
```

## Analysis Queries

### Success Rate by Resolution
```sql
-- DynamoDB doesn't support SQL, but conceptually:
SELECT
    ResolutionCategory,
    COUNT(*) as Total,
    SUM(CASE WHEN RecordType = 'FAILED_IMAGE' THEN 1 ELSE 0 END) as Failures,
    (Failures / Total * 100) as FailureRate
FROM TimesheetOCR-dev
GROUP BY ResolutionCategory
```

### Optimal Image Characteristics
By analyzing the metadata, you can identify:
- **Most reliable resolution range** (likely FULL_HD: 1920×1080)
- **File size sweet spot** (too small = poor quality, too large = processing issues)
- **Format preferences** (PNG vs JPEG performance)
- **DPI thresholds** (if available in screenshots)

## Benefits

1. **Failure Pattern Analysis**: Identify if low-resolution images fail more often
2. **Quality Guidelines**: Establish minimum image quality standards
3. **Performance Optimization**: Optimize processing based on image characteristics
4. **User Feedback**: Provide specific guidance on screenshot quality
5. **Trend Detection**: Monitor if image quality degrades over time
6. **Debugging**: Correlate image properties with specific error types

## Example Metadata Record

```json
{
  "ImageWidth": 1920,
  "ImageHeight": 919,
  "ImageFormat": "PNG",
  "ImageMode": "RGB",
  "AspectRatio": 2.089,
  "Megapixels": 1.76,
  "QualityCategory": "HIGH",
  "ResolutionCategory": "FULL_HD",
  "FileSizeBytes": 56032,
  "FileSizeKB": 54.7,
  "BytesPerPixel": 0.03,
  "DPI_X": 144.0,
  "DPI_Y": 144.0
}
```

## Next Steps

1. **Deploy updated Lambda** with image metadata extraction
2. **Run bulk rescan** to capture metadata for all images
3. **Export failed images** with metadata to CSV for analysis
4. **Identify patterns** - which image characteristics correlate with failure?
5. **Update documentation** - provide users with optimal screenshot settings
6. **Add UI features** - filter/sort by image quality in the UI

## Deployment

To deploy the image metadata capture:

```bash
# Package Lambda with new metadata extraction
cd src && zip -r ../lambda_with_metadata.zip *.py ../OCR_VERSION.txt && cd ..

# Deploy to AWS
aws lambda update-function-code \
    --function-name TimesheetOCR-ocr-dev \
    --zip-file fileb://lambda_with_metadata.zip \
    --region us-east-1

# Wait for deployment
aws lambda wait function-updated \
    --function-name TimesheetOCR-ocr-dev \
    --region us-east-1
```

## Dependencies

The image metadata extraction uses the **Pillow (PIL)** library, which is already included in the Lambda layer for OCR processing. No additional dependencies required.
