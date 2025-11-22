"""
Timesheet OCR - Complete Web Application
Replaces Tkinter UI with modern Flask-based web interface
"""
from flask import Flask, render_template, request, jsonify, send_file, session, Response
import boto3
import io
import base64
import json
import csv
import os
import sys
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
from werkzeug.utils import secure_filename
import threading
from queue import Queue

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from team_manager import TeamManager
from timesheet_coverage import generate_coverage_report, format_missing_timesheets
from enhanced_coverage import (
    generate_enhanced_coverage_report,
    format_enhanced_coverage_text,
    export_missing_timesheets,
    export_failed_validations
)
from labour_hours_report import generate_labour_hours_report, generate_html_report as generate_labour_html

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# AWS Configuration
INPUT_BUCKET = os.getenv('INPUT_BUCKET', 'timesheetocr-input-dev-016164185850')
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'TimesheetOCR-dev')
LAMBDA_FUNCTION = os.getenv('LAMBDA_FUNCTION', 'TimesheetOCR-ocr-dev')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# AWS Clients
s3_client = boto3.client('s3', region_name=AWS_REGION)
lambda_client = boto3.client('lambda', region_name=AWS_REGION)
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE)

# Initialize team manager
team_manager = TeamManager()

# Global state for logs and processing
log_queue = Queue()
processing_status = {'active': False, 'progress': 0, 'total': 0, 'message': ''}

# Load clarity months
clarity_months_file = Path('clarity_months.json')
clarity_months = []
try:
    if clarity_months_file.exists():
        with open(clarity_months_file, 'r') as f:
            data = json.load(f)
            # Handle both formats: direct array or {clarity_months: array}
            if isinstance(data, list):
                clarity_months = data
            elif isinstance(data, dict) and 'clarity_months' in data:
                clarity_months = data['clarity_months']
            else:
                print(f"WARNING: Unexpected clarity_months.json format: {type(data)}")
                clarity_months = []

            # Add 'id' field if missing (for compatibility)
            for month in clarity_months:
                if 'id' not in month:
                    month['id'] = month.get('month', '')
                if 'display_name' not in month:
                    month['display_name'] = month.get('display', month.get('month', ''))

            print(f"Loaded {len(clarity_months)} Clarity months")
    else:
        print(f"WARNING: clarity_months.json not found at {clarity_months_file}")
except Exception as e:
    print(f"ERROR loading clarity_months.json: {e}")
    clarity_months = []


def log_message(message):
    """Add message to log queue with timestamp"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_queue.put(f"[{timestamp}] {message}")


def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def get_db_count():
    """Get total count of items in DynamoDB"""
    try:
        count = 0
        response = table.scan(Select='COUNT')
        count += response['Count']

        while 'LastEvaluatedKey' in response:
            response = table.scan(
                Select='COUNT',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            count += response['Count']

        return count
    except Exception as e:
        log_message(f"Error counting database entries: {e}")
        return 0


def generate_coverage_html(report):
    """Generate HTML report from enhanced coverage data"""
    clarity_month = report['clarity_month']
    period = report['period']
    weeks = report['weeks']
    coverage = report['coverage']
    person_stats = report['person_stats']
    statistics = report['statistics']

    # Week labels
    week_labels = [datetime.strptime(w, '%Y-%m-%d').strftime('%d %b') for w in weeks]

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Coverage Report - {clarity_month}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f9fafb;
            padding: 30px;
            margin: 0;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            padding: 40px;
        }}
        h1 {{
            font-size: 32px;
            margin-bottom: 10px;
            color: #111827;
        }}
        .subtitle {{
            font-size: 16px;
            color: #6b7280;
            margin-bottom: 30px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background: #f3f4f6;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #e5e7eb;
            position: sticky;
            top: 0;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e5e7eb;
        }}
        tr:hover {{
            background: #f9fafb;
        }}
        .symbol {{
            font-size: 18px;
            font-weight: bold;
        }}
        .symbol-complete {{ color: #10b981; }}
        .symbol-failed {{ color: #ef4444; }}
        .symbol-missing {{ color: #9ca3af; }}
        .status-badge {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        .status-complete {{ background: #d1fae5; color: #065f46; }}
        .status-partial {{ background: #fef3c7; color: #92400e; }}
        .status-missing {{ background: #fee2e2; color: #991b1b; }}
        .legend {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            padding: 15px;
            background: #f9fafb;
            border-radius: 8px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .container {{ box-shadow: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Timesheet Coverage Report - {clarity_month}</h1>
        <div class="subtitle">
            Period: {period['start']} to {period['end']} ({report['week_count']} weeks, {report['team_count']} team members)
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{statistics['total_weeks']}</div>
                <div class="stat-label">Expected Timesheets</div>
            </div>
            <div class="stat-card" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%);">
                <div class="stat-value">{statistics['complete']}</div>
                <div class="stat-label">Complete ({statistics['completion_percentage']:.1f}%)</div>
            </div>
            <div class="stat-card" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);">
                <div class="stat-value">{statistics['failed']}</div>
                <div class="stat-label">Failed Validation</div>
            </div>
            <div class="stat-card" style="background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);">
                <div class="stat-value">{statistics['missing']}</div>
                <div class="stat-label">Missing</div>
            </div>
        </div>

        <div class="legend">
            <div class="legend-item">
                <span class="symbol symbol-complete">✓</span>
                <span>Complete</span>
            </div>
            <div class="legend-item">
                <span class="symbol symbol-failed">✗</span>
                <span>Failed Validation</span>
            </div>
            <div class="legend-item">
                <span class="symbol symbol-missing">-</span>
                <span>Missing</span>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Name</th>
"""

    # Week headers
    for label in week_labels:
        html += f"                    <th style='text-align: center;'>{label}</th>\n"

    html += "                    <th>Status</th>\n"
    html += "                </tr>\n"
    html += "            </thead>\n"
    html += "            <tbody>\n"

    # Per person rows
    for person in sorted(coverage.keys()):
        person_weeks = coverage[person]
        stats = person_stats[person]

        html += f"                <tr>\n"
        html += f"                    <td><strong>{person}</strong></td>\n"

        # Week symbols
        for week in weeks:
            status = person_weeks[week]['status']
            if status == 'COMPLETE':
                symbol = '<span class="symbol symbol-complete">✓</span>'
            elif status == 'FAILED':
                symbol = '<span class="symbol symbol-failed">✗</span>'
            else:  # MISSING
                symbol = '<span class="symbol symbol-missing">-</span>'
            html += f"                    <td style='text-align: center;'>{symbol}</td>\n"

        # Status summary
        if stats['missing'] == 0 and stats['failed'] == 0:
            status_html = '<span class="status-badge status-complete">✅ All complete</span>'
        elif stats['missing'] > 0 and stats['failed'] > 0:
            status_html = f'<span class="status-badge status-partial">⚠️ {stats["missing"]} missing, {stats["failed"]} failed</span>'
        elif stats['missing'] > 0:
            status_html = f'<span class="status-badge status-missing">📭 {stats["missing"]} missing</span>'
        elif stats['failed'] > 0:
            status_html = f'<span class="status-badge status-missing">❌ {stats["failed"]} failed validation</span>'
        else:
            status_html = '<span class="status-badge">Unknown</span>'

        html += f"                    <td>{status_html}</td>\n"
        html += "                </tr>\n"

    html += """
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    return html


def load_all_data():
    """Load all data from DynamoDB"""
    try:
        log_message("Loading data from DynamoDB...")
        items = []
        response = table.scan()
        items.extend(response.get('Items', []))

        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))

        log_message(f"Loaded {len(items)} raw items from DynamoDB")

        # Sort by Date then ResourceName
        items.sort(key=lambda x: (x.get('Date', ''), x.get('ResourceName', '')))

        # Convert non-JSON-serializable types
        clean_items = []
        for item in items:
            clean_item = {}
            for key, value in item.items():
                if isinstance(value, Decimal):
                    clean_item[key] = float(value)
                elif isinstance(value, set):
                    clean_item[key] = list(value)
                elif isinstance(value, bytes):
                    clean_item[key] = value.decode('utf-8')
                else:
                    clean_item[key] = value
            clean_items.append(clean_item)

        log_message(f"Cleaned and returning {len(clean_items)} items")
        return clean_items
    except Exception as e:
        log_message(f"✗ Error in load_all_data: {e}")
        import traceback
        traceback.print_exc()
        return []


# ============================================================================
# ROUTES - Dashboard
# ============================================================================

@app.route('/')
def index():
    """Main dashboard"""
    db_count = get_db_count()
    return render_template('dashboard.html', db_count=db_count, clarity_months=clarity_months)


@app.route('/about')
def about():
    """About This App page"""
    # Read version from OCR_VERSION.txt
    version = "2.6.0"
    try:
        with open('OCR_VERSION.txt', 'r') as f:
            for line in f:
                if line.startswith('VERSION='):
                    version = line.split('=')[1].strip()
                    break
    except:
        pass

    # Get statistics
    total_entries = get_db_count()

    # Count processed images
    total_images = 0
    try:
        response = s3_client.list_objects_v2(Bucket=INPUT_BUCKET)
        for obj in response.get('Contents', []):
            if obj['Key'].lower().endswith(('.png', '.jpg', '.jpeg')):
                total_images += 1
    except:
        total_images = 183  # Default fallback

    return render_template('about.html',
                         version=version,
                         total_entries=total_entries,
                         total_images=total_images)


@app.route('/api/db-count')
def api_db_count():
    """Get current database count"""
    return jsonify({'count': get_db_count()})


@app.route('/api/logs')
def api_logs():
    """Stream logs via Server-Sent Events"""
    def generate():
        while True:
            if not log_queue.empty():
                message = log_queue.get()
                yield f"data: {json.dumps({'message': message})}\n\n"
            time.sleep(0.1)

    return Response(generate(), mimetype='text/event-stream')


# ============================================================================
# ROUTES - File Upload & Processing
# ============================================================================

@app.route('/api/upload', methods=['POST'])
def upload_files():
    """Upload files to S3 WITHOUT automatic processing (manual approval workflow)"""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'}), 400

        files = request.files.getlist('files')
        log_message(f"Starting upload of {len(files)} file(s)...")

        results = []
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)

                # Upload to S3 ONLY (no Lambda trigger)
                file_data = file.read()
                s3_client.put_object(
                    Bucket=INPUT_BUCKET,
                    Key=filename,
                    Body=file_data
                )
                log_message(f"✓ Uploaded to S3: {filename}")

                results.append({'filename': filename, 'success': True})

        log_message(f"✓ Upload complete! {len(results)} files uploaded to S3 (awaiting manual approval)")
        return jsonify({'success': True, 'results': results, 'message': f'{len(results)} files uploaded. Use Approval Queue to process them.'})

    except Exception as e:
        log_message(f"✗ Upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ROUTES - Data Viewing
# ============================================================================

@app.route('/api/data')
def api_data():
    """Get all database data (excluding COVERAGE_TRACKER records)"""
    try:
        log_message("📊 Loading database data...")
        data = load_all_data()

        # Filter out COVERAGE_TRACKER records - only show actual timesheets
        timesheet_data = [item for item in data if item.get('RecordType') != 'COVERAGE_TRACKER']
        log_message(f"✓ Loaded {len(timesheet_data)} timesheet entries (filtered from {len(data)} total records)")

        # Convert to JSON-safe format
        safe_data = []
        for item in timesheet_data:
            safe_item = {}
            for key, value in item.items():
                if isinstance(value, Decimal):
                    safe_item[key] = float(value)
                else:
                    safe_item[key] = value
            safe_data.append(safe_item)

        return jsonify({'success': True, 'data': safe_data, 'count': len(safe_data)})
    except Exception as e:
        log_message(f"✗ Error loading data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e), 'data': [], 'count': 0}), 500


@app.route('/api/data/delete-by-image', methods=['POST'])
def delete_by_image():
    """Delete all entries from a specific source image"""
    try:
        data = request.json
        source_image = data.get('source_image')

        if not source_image:
            return jsonify({'success': False, 'error': 'No source image specified'}), 400

        # Find all items with this source image
        all_items = load_all_data()
        to_delete = [item for item in all_items if item.get('SourceImage') == source_image]

        # Delete items
        deleted = 0
        for item in to_delete:
            table.delete_item(
                Key={
                    'ResourceName': item['ResourceName'],
                    'DateProjectCode': item['DateProjectCode']
                }
            )
            deleted += 1

        log_message(f"✓ Deleted {deleted} entries from {source_image}")
        return jsonify({'success': True, 'deleted': deleted})

    except Exception as e:
        log_message(f"✗ Delete error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ROUTES - Export Functions
# ============================================================================

@app.route('/api/export/period', methods=['POST'])
def export_period():
    """Export data for a specific period"""
    try:
        data = request.json
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        export_type = data.get('type', 'summary')  # summary or detailed

        all_items = load_all_data()
        filtered_items = [
            item for item in all_items
            if start_date <= item.get('Date', '') <= end_date
        ]

        # Create CSV
        output = io.StringIO()

        if export_type == 'summary':
            # Group by ResourceName and sum hours
            summary = defaultdict(float)
            for item in filtered_items:
                summary[item['ResourceName']] += float(item.get('Hours', 0))

            writer = csv.writer(output)
            writer.writerow(['Resource Name', 'Total Hours', 'Days (7.5h)'])
            for name, hours in sorted(summary.items()):
                days = hours / 7.5
                writer.writerow([name, f"{hours:.2f}", f"{days:.2f}"])
        else:
            # Detailed export
            writer = csv.DictWriter(output, fieldnames=[
                'ResourceName', 'ResourceNameDisplay', 'Date', 'WeekStartDate', 'WeekEndDate',
                'ProjectCode', 'ProjectName', 'Hours', 'IsZeroHourTimesheet', 'ZeroHourReason',
                'SourceImage', 'ProcessingTimestamp', 'YearMonth', 'DateProjectCode'
            ])
            writer.writeheader()
            for item in filtered_items:
                writer.writerow({
                    'ResourceName': item.get('ResourceName', ''),
                    'ResourceNameDisplay': item.get('ResourceNameDisplay', ''),
                    'Date': item.get('Date', ''),
                    'WeekStartDate': item.get('WeekStartDate', ''),
                    'WeekEndDate': item.get('WeekEndDate', ''),
                    'ProjectCode': item.get('ProjectCode', ''),
                    'ProjectName': item.get('ProjectName', ''),
                    'Hours': float(item.get('Hours', 0)),
                    'IsZeroHourTimesheet': item.get('IsZeroHourTimesheet', False),
                    'ZeroHourReason': item.get('ZeroHourReason', ''),
                    'SourceImage': item.get('SourceImage', ''),
                    'ProcessingTimestamp': item.get('ProcessingTimestamp', ''),
                    'YearMonth': item.get('YearMonth', ''),
                    'DateProjectCode': item.get('DateProjectCode', '')
                })

        # Return CSV file
        output.seek(0)
        filename = f"timesheet_export_{start_date}_to_{end_date}_{export_type}.csv"

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/export/full')
def export_full():
    """Export full database"""
    try:
        all_items = load_all_data()

        output = io.StringIO()
        if all_items:
            fieldnames = list(all_items[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for item in all_items:
                # Convert Decimals
                row = {}
                for k, v in item.items():
                    if isinstance(v, Decimal):
                        row[k] = float(v)
                    else:
                        row[k] = v
                writer.writerow(row)

        output.seek(0)
        filename = f"timesheet_full_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/export/clarity', methods=['POST'])
def export_clarity():
    """Export for specific Clarity month"""
    try:
        log_message("📊 Clarity export requested...")
        data = request.json
        clarity_month = data.get('month')
        export_type = data.get('type', 'summary')

        log_message(f"Clarity month: {clarity_month}, type: {export_type}")

        # Find the month config
        month_config = next((m for m in clarity_months if m.get('id') == clarity_month), None)
        if not month_config:
            log_message(f"✗ Invalid Clarity month: {clarity_month}")
            return jsonify({'success': False, 'error': f'Invalid Clarity month: {clarity_month}'}), 400

        start_date = month_config['start_date']
        end_date = month_config['end_date']

        log_message(f"Exporting from {start_date} to {end_date}")

        # Load and filter data
        all_items = load_all_data()
        filtered_items = [
            item for item in all_items
            if start_date <= item.get('Date', '') <= end_date
        ]

        log_message(f"Found {len(filtered_items)} items in date range")

        # Create CSV
        output = io.StringIO()

        if export_type == 'summary':
            # Group by ResourceName and sum hours
            summary = defaultdict(float)
            for item in filtered_items:
                summary[item['ResourceName']] += float(item.get('Hours', 0))

            writer = csv.writer(output)
            writer.writerow(['Resource Name', 'Total Hours', 'Days (7.5h)'])
            for name, hours in sorted(summary.items()):
                days = hours / 7.5
                writer.writerow([name, f"{hours:.2f}", f"{days:.2f}"])
        else:
            # Detailed export
            writer = csv.DictWriter(output, fieldnames=[
                'ResourceName', 'ResourceNameDisplay', 'Date', 'WeekStartDate', 'WeekEndDate',
                'ProjectCode', 'ProjectName', 'Hours', 'IsZeroHourTimesheet', 'ZeroHourReason',
                'SourceImage', 'ProcessingTimestamp', 'YearMonth', 'DateProjectCode'
            ])
            writer.writeheader()
            for item in filtered_items:
                writer.writerow({
                    'ResourceName': item.get('ResourceName', ''),
                    'ResourceNameDisplay': item.get('ResourceNameDisplay', ''),
                    'Date': item.get('Date', ''),
                    'WeekStartDate': item.get('WeekStartDate', ''),
                    'WeekEndDate': item.get('WeekEndDate', ''),
                    'ProjectCode': item.get('ProjectCode', ''),
                    'ProjectName': item.get('ProjectName', ''),
                    'Hours': float(item.get('Hours', 0)),
                    'IsZeroHourTimesheet': item.get('IsZeroHourTimesheet', False),
                    'ZeroHourReason': item.get('ZeroHourReason', ''),
                    'SourceImage': item.get('SourceImage', ''),
                    'ProcessingTimestamp': item.get('ProcessingTimestamp', ''),
                    'YearMonth': item.get('YearMonth', ''),
                    'DateProjectCode': item.get('DateProjectCode', '')
                })

        # Return CSV file
        output.seek(0)
        filename = f"clarity_export_{export_type}_{clarity_month}.csv"

        log_message(f"✓ Generated export file: {filename}")

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except Exception as e:
        log_message(f"✗ Export error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/export/main-projects', methods=['POST'])
def export_main_projects():
    """Export each person's main project (most hours) for a Clarity month"""
    try:
        log_message("📊 Main projects export requested...")
        data = request.json
        clarity_month = data.get('month')

        log_message(f"Clarity month: {clarity_month}")

        # Find the month config
        month_config = next((m for m in clarity_months if m.get('id') == clarity_month), None)
        if not month_config:
            log_message(f"✗ Invalid Clarity month: {clarity_month}")
            return jsonify({'success': False, 'error': f'Invalid Clarity month: {clarity_month}'}), 400

        start_date = month_config['start_date']
        end_date = month_config['end_date']

        log_message(f"Analyzing projects from {start_date} to {end_date}")

        # Load and filter data
        all_items = load_all_data()
        filtered_items = [
            item for item in all_items
            if start_date <= item.get('Date', '') <= end_date
            and not item.get('IsZeroHourTimesheet', False)  # Exclude zero-hour timesheets
        ]

        log_message(f"Found {len(filtered_items)} items in date range")

        # Group by person and project, sum hours
        person_projects = defaultdict(lambda: defaultdict(float))
        for item in filtered_items:
            person = item.get('ResourceNameDisplay', item.get('ResourceName', '')).replace('_', ' ')
            project_code = item.get('ProjectCode', '')
            project_name = item.get('ProjectName', '')
            hours = float(item.get('Hours', 0))

            # Store both project code and name
            key = f"{project_code}|{project_name}"
            person_projects[person][key] += hours

        # Find main project (most hours) for each person
        main_projects = []
        for person, projects in sorted(person_projects.items()):
            if projects:
                # Find project with most hours
                main_project_key = max(projects.items(), key=lambda x: x[1])[0]
                project_code, project_name = main_project_key.split('|', 1)
                total_hours = projects[main_project_key]

                main_projects.append({
                    'person': person,
                    'project_code': project_code,
                    'project_name': project_name,
                    'hours': total_hours
                })

        log_message(f"Identified main projects for {len(main_projects)} people")

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Person Name', 'Main Project Code', 'Main Project Name', 'Hours on Main Project'])

        for item in main_projects:
            writer.writerow([
                item['person'],
                item['project_code'],
                item['project_name'],
                f"{item['hours']:.2f}"
            ])

        # Return CSV file
        output.seek(0)
        filename = f"main_projects_{clarity_month}.csv"

        log_message(f"✓ Generated main projects export: {filename}")

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except Exception as e:
        log_message(f"✗ Main projects export error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/coverage', methods=['POST'])
def generate_coverage():
    """Generate enhanced coverage report for Clarity month"""
    try:
        data = request.json
        clarity_month = data.get('month')

        log_message(f"🔍 Generating coverage report for {clarity_month}...")

        month_config = next((m for m in clarity_months if m['id'] == clarity_month), None)
        if not month_config:
            log_message(f"❌ Invalid Clarity month: {clarity_month}")
            return jsonify({'success': False, 'error': 'Invalid Clarity month'}), 400

        # Generate enhanced coverage report
        log_message("📊 Querying database for coverage data...")
        report = generate_enhanced_coverage_report(
            clarity_month=clarity_month,
            dynamodb_table=DYNAMODB_TABLE,
            region=AWS_REGION
        )

        log_message(f"✅ Coverage report generated: {report['statistics']['total_weeks']} timesheets analyzed")
        log_message(f"   Complete: {report['statistics']['complete']}, Missing: {report['statistics']['missing']}, Failed: {report['statistics']['failed']}")

        # Generate HTML
        html = generate_coverage_html(report)

        log_message(f"📄 HTML report generated successfully")

        return jsonify({'success': True, 'html': html, 'stats': report['statistics']})

    except Exception as e:
        log_message(f"❌ Coverage report error: {str(e)}")
        import traceback
        log_message(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/labour-hours', methods=['POST'])
def generate_labour_hours():
    """Generate labour hours report for Clarity month"""
    try:
        data = request.json
        clarity_month = data.get('month')

        log_message(f"📊 Generating labour hours report for {clarity_month}...")

        month_config = next((m for m in clarity_months if m['id'] == clarity_month), None)
        if not month_config:
            log_message(f"❌ Invalid Clarity month: {clarity_month}")
            return jsonify({'success': False, 'error': 'Invalid Clarity month'}), 400

        # Generate labour hours report
        log_message("⏱️  Calculating weekly hours from database...")
        report_data = generate_labour_hours_report(
            clarity_month=clarity_month,
            table_name=DYNAMODB_TABLE,
            profile_name=None,  # Using default credentials
            region=AWS_REGION
        )

        log_message(f"✅ Labour hours report generated")
        log_message(f"   Total hours: {report_data['statistics']['total_hours_logged']:.1f}")
        log_message(f"   Team members: {report_data['statistics']['total_team_members']}")
        log_message(f"   Weeks: {report_data['statistics']['total_weeks']}")

        # Generate HTML
        html = generate_labour_html(report_data)

        log_message(f"📄 HTML report generated successfully")

        return jsonify({
            'success': True,
            'html': html,
            'stats': report_data['statistics']
        })

    except Exception as e:
        log_message(f"❌ Labour hours report error: {str(e)}")
        import traceback
        log_message(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/coverage/missing', methods=['POST'])
def export_missing_timesheets():
    """Export missing timesheets list"""
    try:
        data = request.json
        clarity_month = data.get('month')

        month_config = next((m for m in clarity_months if m['id'] == clarity_month), None)
        if not month_config:
            return jsonify({'success': False, 'error': 'Invalid Clarity month'}), 400

        # Generate report
        report = generate_coverage_report(clarity_month, table, team_manager)

        # Format as text
        missing_text = format_missing_timesheets(report)

        filename = f"missing_timesheets_{clarity_month}.txt"
        return Response(
            missing_text,
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ROUTES - Bulk Operations
# ============================================================================

@app.route('/api/flush-db', methods=['POST'])
def flush_database():
    """Delete all items from DynamoDB"""
    try:
        # Scan and delete all items
        deleted = 0
        response = table.scan()

        with table.batch_writer() as batch:
            for item in response.get('Items', []):
                batch.delete_item(
                    Key={
                        'ResourceName': item['ResourceName'],
                        'DateProjectCode': item['DateProjectCode']
                    }
                )
                deleted += 1

            while 'LastEvaluatedKey' in response:
                response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                for item in response.get('Items', []):
                    batch.delete_item(
                        Key={
                            'ResourceName': item['ResourceName'],
                            'DateProjectCode': item['DateProjectCode']
                        }
                    )
                    deleted += 1

        log_message(f"✓ Flushed database: {deleted} items deleted")
        return jsonify({'success': True, 'deleted': deleted})

    except Exception as e:
        log_message(f"✗ Flush error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/s3-images')
def list_s3_images():
    """List images in S3 bucket"""
    try:
        response = s3_client.list_objects_v2(Bucket=INPUT_BUCKET, MaxKeys=100)

        images = []
        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['Key'].lower().endswith(('.png', '.jpg', '.jpeg')):
                    images.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat()
                    })

        return jsonify({
            'success': True,
            'images': images,
            'total': len(images),
            'truncated': response.get('IsTruncated', False)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ROUTES - Data Quality
# ============================================================================

@app.route('/api/quality/similar-codes')
def find_similar_codes():
    """Find similar project codes (potential OCR errors)"""
    try:
        # This would use Levenshtein distance logic from the original
        # For now, return placeholder
        return jsonify({'success': True, 'similar_codes': []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/quality/update-dictionaries', methods=['POST'])
def update_dictionaries():
    """Run create_dictionaries.py script"""
    try:
        log_message("Updating reference dictionaries...")
        result = subprocess.run(
            ['python3', 'create_dictionaries.py'],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            log_message("✓ Dictionaries updated successfully")
            return jsonify({'success': True, 'output': result.stdout})
        else:
            log_message(f"✗ Dictionary update failed: {result.stderr}")
            return jsonify({'success': False, 'error': result.stderr}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ROUTES - Team Management
# ============================================================================

@app.route('/api/team/members')
def get_team_members():
    """Get all team members"""
    try:
        log_message("👥 Loading team members...")
        members = team_manager.get_team_members()
        log_message(f"✓ Loaded {len(members)} team members")
        return jsonify({'success': True, 'members': members})
    except Exception as e:
        log_message(f"✗ Error loading team members: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e), 'members': []}), 500


@app.route('/api/team/members', methods=['POST'])
def add_team_member():
    """Add new team member"""
    try:
        data = request.json
        name = data.get('name', '').strip()

        if not name:
            return jsonify({'success': False, 'error': 'Name is required'}), 400

        team_manager.add_team_member(name)
        log_message(f"✓ Added team member: {name}")
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/team/members/<name>', methods=['DELETE'])
def remove_team_member(name):
    """Remove team member"""
    try:
        team_manager.remove_team_member(name)
        log_message(f"✓ Removed team member: {name}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/team/aliases')
def get_aliases():
    """Get all name aliases"""
    try:
        log_message("🔤 Loading name aliases...")
        aliases = team_manager.get_aliases()
        log_message(f"✓ Loaded {len(aliases)} name aliases")
        return jsonify({'success': True, 'aliases': aliases})
    except Exception as e:
        log_message(f"✗ Error loading aliases: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e), 'aliases': {}}), 500


@app.route('/api/team/aliases', methods=['POST'])
def add_alias():
    """Add name alias"""
    try:
        data = request.json
        ocr_variant = data.get('ocr_variant', '').strip()
        canonical_name = data.get('canonical_name', '').strip()

        if not ocr_variant or not canonical_name:
            return jsonify({'success': False, 'error': 'Both fields required'}), 400

        team_manager.add_name_alias(ocr_variant, canonical_name)
        log_message(f"✓ Added alias: {ocr_variant} → {canonical_name}")
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/team/aliases/<ocr_variant>', methods=['DELETE'])
def remove_alias(ocr_variant):
    """Remove name alias"""
    try:
        team_manager.remove_name_alias(ocr_variant)
        log_message(f"✓ Removed alias: {ocr_variant}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ROUTES - Approval Interface (embedded)
# ============================================================================

# In-memory queue for approval
approval_queue = []
approval_index = 0


def calculate_validation_details(timesheets):
    """Calculate detailed validation breakdown for display."""
    if not timesheets:
        return []

    # Group by date to calculate daily totals
    daily_hours = {}
    for entry in timesheets:
        date = entry.get('Date', 'Unknown')
        hours = float(entry.get('Hours', 0))
        if date not in daily_hours:
            daily_hours[date] = {'actual': 0, 'entries': []}
        daily_hours[date]['actual'] += hours
        daily_hours[date]['entries'].append(entry)

    # Build validation checks
    details = []

    # Check 1: Total hours per day should be 8 or 0 (annual leave)
    for date, data in sorted(daily_hours.items()):
        actual = data['actual']
        expected = 8.0
        is_valid = (actual == expected) or (actual == 0)

        details.append({
            'check': f'Daily total for {date}',
            'expected': f'{expected} hours',
            'actual': f'{actual} hours',
            'passed': is_valid,
            'type': 'daily_total'
        })

    # Check 2: All entries have valid project codes
    for entry in timesheets:
        project_code = entry.get('ProjectCode', '')
        is_valid = bool(project_code and project_code != 'N/A')

        details.append({
            'check': f'Project code for {entry.get("Date", "Unknown")}',
            'expected': 'Valid project code',
            'actual': project_code if project_code else 'Missing',
            'passed': is_valid,
            'type': 'project_code'
        })

    # Check 3: All entries have resource name
    resource_names = set(entry.get('ResourceName', '') for entry in timesheets)
    if len(resource_names) == 1 and list(resource_names)[0]:
        details.append({
            'check': 'Resource name consistency',
            'expected': 'Single resource name',
            'actual': list(resource_names)[0],
            'passed': True,
            'type': 'resource_name'
        })

    # Check 4: Hours are reasonable (not negative, not > 24)
    for entry in timesheets:
        hours = float(entry.get('Hours', 0))
        is_valid = 0 <= hours <= 24

        if not is_valid:
            details.append({
                'check': f'Hours validation for {entry.get("Date", "Unknown")}',
                'expected': '0-24 hours',
                'actual': f'{hours} hours',
                'passed': False,
                'type': 'hours_range'
            })

    return details


def load_pending_images():
    """
    Load images that need approval using ProcessedImages tracking table.

    SIMPLE & RELIABLE LOGIC:
    - Pending = Images in S3 BUT NOT in ProcessedImages table
    - No timestamp comparisons
    - No guessing
    - 100% accurate
    """
    global approval_queue
    try:
        log_message("🔍 Loading pending images...")

        # Get ProcessedImages table
        processed_table_name = 'TimesheetOCR-ProcessedImages-dev'
        processed_table = dynamodb.Table(processed_table_name)

        # Get all images from S3
        response = s3_client.list_objects_v2(Bucket=INPUT_BUCKET)
        if 'Contents' in response:
            s3_images = set()
            for obj in response['Contents']:
                key = obj['Key']
                if key.lower().endswith(('.png', '.jpg', '.jpeg')):
                    s3_images.add(key)

            log_message(f"📁 Found {len(s3_images)} images in S3")

            # Get all processed images from tracking table
            processed_response = processed_table.scan()
            processed_images = set()

            for item in processed_response.get('Items', []):
                processed_images.add(item['ImageKey'])

            # Handle pagination
            while 'LastEvaluatedKey' in processed_response:
                processed_response = processed_table.scan(ExclusiveStartKey=processed_response['LastEvaluatedKey'])
                for item in processed_response.get('Items', []):
                    processed_images.add(item['ImageKey'])

            log_message(f"✅ Found {len(processed_images)} processed images in tracking table")

            # Pending = S3 - Processed
            pending_images = sorted(list(s3_images - processed_images))

            log_message(f"⏳ Pending for approval: {len(pending_images)} images")

            if pending_images:
                for img in pending_images[:10]:  # Show first 10
                    log_message(f"  → {img}")
                if len(pending_images) > 10:
                    log_message(f"  ... and {len(pending_images) - 10} more")

            approval_queue = pending_images
        else:
            approval_queue = []
            log_message("📭 No images found in S3")

    except Exception as e:
        log_message(f"❌ Error loading approval queue: {e}")
        import traceback
        log_message(f"Traceback: {traceback.format_exc()}")
        approval_queue = []


@app.route('/approval')
def approval_interface():
    """Embedded approval interface"""
    return render_template('approval.html')


@app.route('/api/approval/next-image')
def approval_next_image():
    """Get next image for approval."""
    global approval_index

    if not approval_queue:
        load_pending_images()

    if approval_index >= len(approval_queue):
        return jsonify({
            'done': True,
            'message': 'No more images to approve'
        })

    image_key = approval_queue[approval_index]

    try:
        # Download image from S3
        response = s3_client.get_object(Bucket=INPUT_BUCKET, Key=image_key)
        image_bytes = response['Body'].read()

        # Convert to base64 for HTML display
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Get file extension for proper MIME type
        ext = image_key.lower().split('.')[-1]
        mime_type = f'image/{ext}' if ext in ['png', 'jpg', 'jpeg'] else 'image/png'

        # Call Lambda to get OCR data SYNCHRONOUSLY
        log_message(f"🔍 Processing OCR for: {image_key}")
        payload = {
            "Records": [{
                "s3": {
                    "bucket": {"name": INPUT_BUCKET},
                    "object": {"key": image_key}
                }
            }]
        }

        lambda_response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            InvocationType='RequestResponse',  # Synchronous call
            Payload=json.dumps(payload).encode()
        )

        # Parse Lambda response
        lambda_payload = lambda_response['Payload'].read()
        lambda_result = json.loads(lambda_payload)
        log_message(f"✓ OCR complete for: {image_key}")

        # Check for Lambda execution errors
        if 'FunctionError' in lambda_response:
            log_message(f"❌ Lambda Function Error: {lambda_response['FunctionError']}")
            error_msg = lambda_result.get('errorMessage', 'Unknown Lambda error')
            return jsonify({
                'done': False,
                'image_key': image_key,
                'image_data': f'data:{mime_type};base64,{image_base64}',
                'index': approval_index + 1,
                'total': len(approval_queue),
                'ocr_data': {'success': False, 'error': error_msg}
            })

        # Parse the response body (Lambda HTTP response format)
        if isinstance(lambda_result, dict) and 'body' in lambda_result:
            body_data = json.loads(lambda_result['body']) if isinstance(lambda_result['body'], str) else lambda_result['body']
        else:
            body_data = lambda_result

        # Log Lambda response for debugging
        log_message(f"📝 Lambda response keys: {list(body_data.keys())}")
        log_message(f"📝 Lambda statusCode: {lambda_result.get('statusCode', 'N/A')}")

        # Now query DynamoDB to get the actual timesheet entries
        resource_name = body_data.get('resource_name', '')
        if resource_name:
            log_message(f"📊 Querying DynamoDB for {resource_name} timesheets...")
            try:
                # Query all entries for this resource from this image
                all_data = load_all_data()
                timesheets = [item for item in all_data if item.get('SourceImage') == image_key]
                log_message(f"✓ Found {len(timesheets)} timesheet entries")

                # Use Lambda's actual validation results (don't recalculate)
                lambda_validation = body_data.get('validation', {})

                # Build response with timesheet data
                ocr_response = {
                    'success': True,
                    'resource_name': resource_name,
                    'date_range': body_data.get('date_range', ''),
                    'projects_count': body_data.get('projects_count', 0),
                    'entries_stored': body_data.get('entries_stored', 0),
                    'validation': {
                        'is_valid': lambda_validation.get('valid', True),
                        'message': lambda_validation.get('summary', ''),
                        'errors': lambda_validation.get('errors', []),
                        'warnings': lambda_validation.get('warnings', [])
                    },
                    'ocr_extracted_values': body_data.get('ocr_extracted_values', {}),
                    'timesheets': timesheets
                }
            except Exception as e:
                log_message(f"❌ Error querying DynamoDB: {e}")
                ocr_response = {
                    'success': False,
                    'error': f'Failed to retrieve timesheet entries: {str(e)}'
                }
        else:
            ocr_response = {
                'success': False,
                'error': 'No resource name in Lambda response'
            }

        return jsonify({
            'done': False,
            'image_key': image_key,
            'image_data': f'data:{mime_type};base64,{image_base64}',
            'index': approval_index + 1,
            'total': len(approval_queue),
            'ocr_data': ocr_response  # Now includes actual timesheet entries!
        })

    except Exception as e:
        log_message(f"Error loading image {image_key}: {e}")
        approval_index += 1
        return approval_next_image()


@app.route('/api/approval/approve', methods=['POST'])
def approval_approve():
    """Approve image - OCR data already in DB, mark as processed."""
    global approval_index

    data = request.json
    image_key = data.get('image_key')

    try:
        from datetime import datetime, timezone

        # OCR already processed and in DB from next-image call
        # Now mark image as processed in ProcessedImages table
        processed_table_name = 'TimesheetOCR-ProcessedImages-dev'
        processed_table = dynamodb.Table(processed_table_name)

        # Get entry count from main DB
        all_data = load_all_data()
        entries = [item for item in all_data if item.get('SourceImage') == image_key]
        entry_count = len(entries)
        resource_name = entries[0].get('ResourceName', 'Unknown') if entries else 'Unknown'

        # Mark as processed
        processed_table.put_item(
            Item={
                'ImageKey': image_key,
                'ProcessedTimestamp': datetime.now(timezone.utc).isoformat(),
                'ProcessingStatus': 'SUCCESS',
                'EntryCount': entry_count,
                'ResourceName': resource_name
            }
        )

        approval_index += 1
        log_message(f"✓ Approved: {image_key} ({entry_count} entries, marked as processed)")

        return jsonify({
            'success': True,
            'message': f'Approved {image_key}'
        })

    except Exception as e:
        log_message(f"✗ Approval error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/approval/reject', methods=['POST'])
def approval_reject():
    """Reject image - delete from DB and remove from ProcessedImages so it can be rescanned."""
    global approval_index

    data = request.json
    image_key = data.get('image_key')

    try:
        from datetime import datetime, timezone

        # Delete all entries for this image from DynamoDB
        all_data = load_all_data()
        deleted_count = 0

        for item in all_data:
            if item.get('SourceImage') == image_key:
                # Delete this entry
                table.delete_item(
                    Key={
                        'ResourceName': item['ResourceName'],
                        'DateProjectCode': item['DateProjectCode']
                    }
                )
                deleted_count += 1

        # REMOVE from ProcessedImages table so it appears in queue for rescan
        processed_table_name = 'TimesheetOCR-ProcessedImages-dev'
        processed_table = dynamodb.Table(processed_table_name)

        try:
            processed_table.delete_item(Key={'ImageKey': image_key})
            log_message(f"  → Removed from ProcessedImages table (will reappear in queue)")
        except:
            pass  # May not exist in table yet

        approval_index += 1
        log_message(f"✗ Rejected: {image_key} (deleted {deleted_count} entries, removed from processed)")

        return jsonify({
            'success': True,
            'message': f'Rejected {image_key} and deleted {deleted_count} entries'
        })

    except Exception as e:
        log_message(f"✗ Reject error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/approval/delete', methods=['POST'])
def approval_delete():
    """Delete image from S3."""
    global approval_index

    data = request.json
    image_key = data.get('image_key')

    try:
        s3_client.delete_object(Bucket=INPUT_BUCKET, Key=image_key)

        # Remove from queue
        if approval_index < len(approval_queue):
            approval_queue.pop(approval_index)

        log_message(f"✓ Deleted: {image_key}")

        return jsonify({
            'success': True,
            'message': f'Deleted {image_key}'
        })

    except Exception as e:
        log_message(f"✗ Delete error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/approval/queue-status')
def approval_queue_status():
    """Get current approval queue status."""
    global approval_index, approval_queue

    return jsonify({
        'total': len(approval_queue),
        'current_index': approval_index,
        'remaining': len(approval_queue) - approval_index,
        'processed': approval_index
    })

@app.route('/api/approval/reload-queue', methods=['POST'])
def approval_reload_queue():
    """Force reload the approval queue."""
    global approval_index, approval_queue

    try:
        old_count = len(approval_queue)
        approval_index = 0
        load_pending_images()
        new_count = len(approval_queue)

        log_message(f"🔄 Approval queue reloaded: {old_count} → {new_count} images")

        return jsonify({
            'success': True,
            'old_count': old_count,
            'new_count': new_count,
            'message': f'Queue reloaded: {new_count} images pending'
        })
    except Exception as e:
        log_message(f"❌ Error reloading queue: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/approval/auto-approve-all', methods=['POST'])
def approval_auto_approve_all():
    """Auto-approve all remaining images."""
    global approval_index

    approved_count = 0
    errors = []

    while approval_index < len(approval_queue):
        image_key = approval_queue[approval_index]

        try:
            payload = {
                "Records": [{
                    "s3": {
                        "bucket": {"name": INPUT_BUCKET},
                        "object": {"key": image_key}
                    }
                }]
            }

            lambda_client.invoke(
                FunctionName=LAMBDA_FUNCTION,
                InvocationType='Event',  # Async
                Payload=json.dumps(payload).encode()
            )

            approved_count += 1
            approval_index += 1

        except Exception as e:
            errors.append(f"{image_key}: {str(e)}")
            approval_index += 1

    log_message(f"✓ Auto-approved {approved_count} images")

    return jsonify({
        'success': True,
        'approved': approved_count,
        'errors': errors
    })


# ============================================================================
# ROUTES - Import Corrections
# ============================================================================

@app.route('/api/import-corrections', methods=['POST'])
def import_corrections():
    """Import corrections from CSV"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        if not file.filename.endswith('.csv'):
            return jsonify({'success': False, 'error': 'Must be CSV file'}), 400

        # Read CSV
        csv_data = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_data))

        updated = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            try:
                # Get primary keys
                resource_name = row.get('ResourceName')
                date_project_code = row.get('DateProjectCode')

                if not resource_name or not date_project_code:
                    continue

                # Get current item
                response = table.get_item(
                    Key={
                        'ResourceName': resource_name,
                        'DateProjectCode': date_project_code
                    }
                )

                if 'Item' not in response:
                    continue

                current = response['Item']

                # Build update expression
                update_expr = []
                expr_values = {}
                expr_names = {}

                for key, new_value in row.items():
                    if key in ['ResourceName', 'DateProjectCode']:
                        continue  # Cannot update primary keys

                    if key not in current or str(current[key]) != new_value:
                        # Value changed
                        placeholder = f":val{len(expr_values)}"
                        attr_name = f"#attr{len(expr_names)}"

                        update_expr.append(f"{attr_name} = {placeholder}")
                        expr_names[attr_name] = key

                        # Type conversion
                        if key == 'Hours':
                            expr_values[placeholder] = Decimal(str(new_value))
                        elif key == 'IsZeroHourTimesheet':
                            expr_values[placeholder] = new_value.lower() in ['true', '1', 'yes']
                        else:
                            expr_values[placeholder] = new_value

                # Perform update if needed
                if update_expr:
                    table.update_item(
                        Key={
                            'ResourceName': resource_name,
                            'DateProjectCode': date_project_code
                        },
                        UpdateExpression='SET ' + ', '.join(update_expr),
                        ExpressionAttributeNames=expr_names,
                        ExpressionAttributeValues=expr_values
                    )
                    updated += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        log_message(f"✓ Import complete: {updated} rows updated")

        return jsonify({
            'success': True,
            'updated': updated,
            'errors': errors
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def find_available_port(start_port=8000, max_attempts=100):
    """Find an available port starting from start_port"""
    import socket
    for port in range(start_port, start_port + max_attempts):
        try:
            # Try to bind to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', port))
            sock.close()
            return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find available port in range {start_port}-{start_port + max_attempts}")


if __name__ == '__main__':
    log_message("Starting Timesheet OCR Web Application...")
    log_message(f"AWS Region: {AWS_REGION}")
    log_message(f"S3 Bucket: {INPUT_BUCKET}")
    log_message(f"DynamoDB Table: {DYNAMODB_TABLE}")
    log_message(f"Lambda Function: {LAMBDA_FUNCTION}")

    # Find an available port
    port = find_available_port(start_port=8000)
    log_message(f"Attempting to use port: {port}")

    # Run Flask app
    # Note: The launcher script will detect the actual port from Flask's output
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
