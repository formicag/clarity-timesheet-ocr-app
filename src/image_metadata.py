"""
Image Metadata Extraction

Extracts metadata from screenshot images to help analyze
what succeeds vs fails in OCR processing.
"""
import io
from PIL import Image
from typing import Dict, Any
from decimal import Decimal


def extract_image_metadata(image_bytes: bytes, file_size: int) -> Dict[str, Any]:
    """
    Extract comprehensive metadata from image bytes.

    Args:
        image_bytes: Raw image bytes
        file_size: File size in bytes

    Returns:
        Dictionary with image metadata
    """
    try:
        # Open image from bytes
        img = Image.open(io.BytesIO(image_bytes))

        # Basic dimensions
        width, height = img.size
        aspect_ratio = width / height if height > 0 else 0
        megapixels = (width * height) / 1_000_000

        # DPI if available
        dpi = img.info.get('dpi', (0, 0))
        if isinstance(dpi, tuple):
            dpi_x, dpi_y = dpi
        else:
            dpi_x = dpi_y = dpi

        # Calculate bytes per pixel
        bytes_per_pixel = file_size / (width * height) if (width * height) > 0 else 0

        # Determine quality category based on resolution
        if width >= 1920 and height >= 1080:
            quality = "HIGH"  # Full HD or better
        elif width >= 1280 and height >= 720:
            quality = "MEDIUM"  # HD
        else:
            quality = "LOW"  # Below HD

        # Build metadata dict
        metadata = {
            # Image dimensions
            'ImageWidth': Decimal(str(width)),
            'ImageHeight': Decimal(str(height)),
            'ImageFormat': img.format or 'UNKNOWN',
            'ImageMode': img.mode,  # RGB, RGBA, L, etc.

            # Calculated metrics
            'AspectRatio': Decimal(str(round(aspect_ratio, 3))),
            'Megapixels': Decimal(str(round(megapixels, 2))),
            'QualityCategory': quality,

            # File size
            'FileSizeBytes': Decimal(str(file_size)),
            'FileSizeKB': Decimal(str(round(file_size / 1024, 1))),
            'BytesPerPixel': Decimal(str(round(bytes_per_pixel, 2))),

            # DPI
            'DPI_X': Decimal(str(round(dpi_x, 1))) if dpi_x else Decimal('0'),
            'DPI_Y': Decimal(str(round(dpi_y, 1))) if dpi_y else Decimal('0'),

            # Resolution category for analysis
            'ResolutionCategory': _categorize_resolution(width, height),
        }

        return metadata

    except Exception as e:
        # Return minimal metadata on error
        return {
            'ImageWidth': Decimal('0'),
            'ImageHeight': Decimal('0'),
            'ImageFormat': 'ERROR',
            'ImageMode': 'UNKNOWN',
            'AspectRatio': Decimal('0'),
            'Megapixels': Decimal('0'),
            'QualityCategory': 'UNKNOWN',
            'FileSizeBytes': Decimal(str(file_size)),
            'FileSizeKB': Decimal(str(round(file_size / 1024, 1))),
            'BytesPerPixel': Decimal('0'),
            'DPI_X': Decimal('0'),
            'DPI_Y': Decimal('0'),
            'ResolutionCategory': 'UNKNOWN',
            'MetadataError': str(e)[:200]
        }


def _categorize_resolution(width: int, height: int) -> str:
    """
    Categorize resolution for easier analysis.

    Common screenshot resolutions:
    - 4K: 3840x2160
    - QHD: 2560x1440
    - Full HD: 1920x1080
    - HD: 1280x720
    - Lower
    """
    total_pixels = width * height

    if total_pixels >= 3840 * 2160 * 0.9:  # ~90% of 4K
        return "4K"
    elif total_pixels >= 2560 * 1440 * 0.9:  # ~90% of QHD
        return "QHD"
    elif total_pixels >= 1920 * 1080 * 0.9:  # ~90% of Full HD
        return "FULL_HD"
    elif total_pixels >= 1280 * 720 * 0.9:  # ~90% of HD
        return "HD"
    else:
        return "BELOW_HD"


def get_image_stats_summary(metadata: Dict[str, Any]) -> str:
    """
    Generate human-readable summary of image stats.

    Args:
        metadata: Image metadata dict

    Returns:
        Summary string
    """
    try:
        width = int(metadata.get('ImageWidth', 0))
        height = int(metadata.get('ImageHeight', 0))
        size_kb = float(metadata.get('FileSizeKB', 0))
        quality = metadata.get('QualityCategory', 'UNKNOWN')
        resolution = metadata.get('ResolutionCategory', 'UNKNOWN')

        return (
            f"{width}x{height} ({resolution}), "
            f"{size_kb:.1f}KB, "
            f"Quality: {quality}"
        )
    except:
        return "Unknown image stats"
