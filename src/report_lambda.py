"""
AWS Lambda function for generating timesheet reports.
"""
import json
import os
from typing import Dict, Any
from reporting import (
    get_all_resources,
    generate_resource_calendar_report
)
from report_html import generate_html_calendar_report


# Environment variables
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', '')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for generating timesheet reports.

    Routes:
    - GET /resources - List all resources
    - GET /report/{resource_name} - Get calendar report for resource
    - GET /report/{resource_name}/html - Get HTML calendar report

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        # Extract path and query parameters
        path = event.get('path', '')
        http_method = event.get('httpMethod', 'GET')
        query_params = event.get('queryStringParameters', {}) or {}

        print(f"Processing {http_method} {path}")

        # Route: List all resources
        if path == '/resources' and http_method == 'GET':
            resources = get_all_resources(DYNAMODB_TABLE)
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'resources': resources,
                    'count': len(resources)
                })
            }

        # Route: Get calendar report for resource
        if path.startswith('/report/'):
            # Extract resource name from path
            path_parts = path.split('/')
            if len(path_parts) < 3:
                return error_response(400, 'Invalid path format')

            resource_name = path_parts[2].replace('_', ' ')
            is_html = len(path_parts) > 3 and path_parts[3] == 'html'

            # Get optional date range from query parameters
            start_date = query_params.get('start_date')
            end_date = query_params.get('end_date')

            print(f"Generating report for: {resource_name}")
            if start_date:
                print(f"  Start date: {start_date}")
            if end_date:
                print(f"  End date: {end_date}")

            # Generate report
            report = generate_resource_calendar_report(
                resource_name=resource_name,
                table_name=DYNAMODB_TABLE,
                start_date=start_date,
                end_date=end_date
            )

            # Return HTML or JSON
            if is_html:
                html = generate_html_calendar_report(report)
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'text/html',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': html
                }
            else:
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps(report, default=str)
                }

        # Route not found
        return error_response(404, 'Route not found')

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f'Internal server error: {str(e)}')


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Generate error response.

    Args:
        status_code: HTTP status code
        message: Error message

    Returns:
        API Gateway error response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': message
        })
    }


# For local testing
if __name__ == "__main__":
    # Test listing resources
    test_event = {
        'path': '/resources',
        'httpMethod': 'GET',
        'queryStringParameters': None
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
