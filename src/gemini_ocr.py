"""
Google Gemini OCR Module

Provides OCR extraction using Google Gemini 2.0 Flash model.
23% faster and 85% cheaper than AWS Bedrock Claude.
"""
import os
import io
import json
from typing import Dict, Any
from PIL import Image
import google.generativeai as genai


def extract_metadata_with_gemini(image_data: bytes, prompt: str) -> Dict[str, Any]:
    """
    Extract timesheet metadata using Google Gemini 2.0 Flash.

    Args:
        image_data: Raw image bytes
        prompt: Extraction prompt

    Returns:
        Dictionary with extracted data and metadata
    """
    # Configure Gemini API
    api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY environment variable not set")

    genai.configure(api_key=api_key)

    # Use Gemini 2.0 Flash (fastest model)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')

    # Load image
    image = Image.open(io.BytesIO(image_data))

    # Generate response
    response = model.generate_content([prompt, image])

    # Parse JSON response
    response_text = response.text.strip()

    # Remove markdown code blocks if present
    if response_text.startswith('```json'):
        response_text = response_text[7:]
    if response_text.startswith('```'):
        response_text = response_text[3:]
    if response_text.endswith('```'):
        response_text = response_text[:-3]

    response_text = response_text.strip()

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        # Try to find JSON in the response
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end > start:
            data = json.loads(response_text[start:end])
        else:
            raise ValueError(f"Failed to parse Gemini response as JSON: {e}\nResponse: {response_text[:200]}")

    return {
        'data': data,
        'model': 'gemini-2.0-flash-exp',
        'raw_response': response_text
    }
