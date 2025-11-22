"""
Labour Hours Report Generator for Clarity Months.

Generates a grid showing total hours worked by each team member per week,
with monthly totals. Similar layout to coverage report but with numeric hours.
"""
import json
import boto3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
from decimal import Decimal


def load_clarity_months():
    """Load Clarity month definitions from clarity_months.json."""
    try:
        with open('clarity_months.json', 'r') as f:
            data = json.load(f)
            months = {}
            for month_data in data.get('clarity_months', []):
                month_key = month_data['month']
                months[month_key] = {
                    'start': month_data['start_date'],
                    'end': month_data['end_date'],
                    'display': month_data.get('display', month_key)
                }
            return months
    except Exception as e:
        print(f"Error loading clarity_months.json: {e}")
        return {}


def load_team_roster():
    """Load team member names from team_roster.json."""
    try:
        with open('team_roster.json', 'r') as f:
            data = json.load(f)
            return sorted(data.get('team_members', []))
    except Exception as e:
        print(f"Error loading team_roster.json: {e}")
        return []


def get_monday_weeks_in_period(start_date: datetime, end_date: datetime) -> List[datetime]:
    """Get all Monday dates that start weeks within the period."""
    weeks = []
    current = start_date

    # Find the first Monday on or after start_date
    days_until_monday = (7 - current.weekday()) % 7
    if days_until_monday > 0 and current.weekday() != 0:
        current += timedelta(days=days_until_monday)

    if start_date.weekday() == 0:
        current = start_date

    # Collect all Mondays until end_date
    while current <= end_date:
        weeks.append(current)
        current += timedelta(days=7)

    return weeks


def parse_clarity_month(month_str: str) -> Tuple[datetime, datetime, str]:
    """Parse Clarity month string to get start/end dates and display name."""
    clarity_months = load_clarity_months()

    if month_str not in clarity_months:
        raise ValueError(f"Clarity month '{month_str}' not found in clarity_months.json")

    month_data = clarity_months[month_str]
    start_date = datetime.strptime(month_data['start'], "%Y-%m-%d")
    end_date = datetime.strptime(month_data['end'], "%Y-%m-%d")
    display = month_data.get('display', month_str)

    return start_date, end_date, display


def fetch_timesheet_data(table_name: str = 'TimesheetOCR-dev', profile_name: str = None, region: str = 'us-east-1'):
    """Fetch all timesheet data from DynamoDB."""
    try:
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region)
            dynamodb = session.resource('dynamodb')
        else:
            dynamodb = boto3.resource('dynamodb', region_name=region)

        table = dynamodb.Table(table_name)

        # Scan entire table
        response = table.scan()
        items = response.get('Items', [])

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))

        return items
    except Exception as e:
        print(f"Error fetching data from DynamoDB: {e}")
        return []


def calculate_weekly_hours(items: List[Dict], start_date: datetime, end_date: datetime, weeks: List[datetime]) -> Tuple[Dict, Dict]:
    """
    Calculate weekly hours for each person.

    Returns:
        Tuple of:
        - weekly_hours: Dict with {(person, week_start_str): total_hours}
        - zero_hour_weeks: Dict with {(person, week_start_str): True} for zero-hour timesheets
    """
    weekly_hours = defaultdict(float)
    zero_hour_weeks = {}

    for item in items:
        # Check if this is a zero-hour timesheet
        is_zero_hour = item.get('IsZeroHourTimesheet', False)

        # Get person name (convert underscores to spaces)
        person = item.get('ResourceName', '').replace('_', ' ')

        if is_zero_hour:
            # Zero-hour timesheets use Date field for week start
            date_str = item.get('Date')
            if not date_str:
                continue

            try:
                entry_date = datetime.strptime(date_str, '%Y-%m-%d')
            except (ValueError, TypeError):
                continue

            # Check if in our period
            if entry_date < start_date or entry_date > end_date:
                continue

            # Mark this week as zero-hour for this person
            week_start_str = entry_date.strftime('%Y-%m-%d')
            zero_hour_weeks[(person, week_start_str)] = True
            # Don't add hours - it's a zero-hour timesheet
            continue

        # Regular timesheet processing
        date_str = item.get('Date')
        if not date_str:
            continue

        try:
            entry_date = datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            continue

        # Check if entry is in our period
        if entry_date < start_date or entry_date > end_date:
            continue

        # Find which week this entry belongs to
        week_start = None
        for week in weeks:
            week_end = week + timedelta(days=6)
            if week <= entry_date <= week_end:
                week_start = week.strftime('%Y-%m-%d')
                break

        if not week_start:
            continue

        # Get hours (handle both Decimal and float/int)
        hours_value = item.get('Hours', 0)
        if isinstance(hours_value, Decimal):
            hours = float(hours_value)
        else:
            hours = float(hours_value)

        # Add to weekly total
        weekly_hours[(person, week_start)] += hours

    return weekly_hours, zero_hour_weeks


def generate_labour_hours_report(clarity_month: str, table_name: str = 'TimesheetOCR-dev',
                                  profile_name: str = None, region: str = 'us-east-1') -> Dict:
    """
    Generate labour hours report for a Clarity month.

    Args:
        clarity_month: Month identifier like "Nov-25"
        table_name: DynamoDB table name
        profile_name: AWS profile name (optional)
        region: AWS region

    Returns:
        Dict with:
        {
            'clarity_month': str,
            'period_display': str,
            'weeks': List[datetime],
            'team_members': List[str],
            'weekly_hours': Dict[(person, week_str): hours],
            'month_totals': Dict[person: total_hours],
            'statistics': Dict
        }
    """
    # Parse Clarity month
    start_date, end_date, period_display = parse_clarity_month(clarity_month)

    # Get weeks
    weeks = get_monday_weeks_in_period(start_date, end_date)

    # Load team roster
    team_members = load_team_roster()

    # Fetch data from DynamoDB
    items = fetch_timesheet_data(table_name, profile_name, region)

    # Calculate weekly hours
    weekly_hours, zero_hour_weeks = calculate_weekly_hours(items, start_date, end_date, weeks)

    # Calculate month totals for each person
    month_totals = {}
    month_totals_days = {}
    for person in team_members:
        total = 0.0
        for week in weeks:
            week_str = week.strftime('%Y-%m-%d')
            total += weekly_hours.get((person, week_str), 0.0)
        month_totals[person] = total
        # Convert hours to days (7.5 hours = 1 day)
        month_totals_days[person] = total / 7.5 if total > 0 else 0.0

    # Calculate statistics
    total_expected_weeks = len(team_members) * len(weeks)
    total_hours_logged = sum(month_totals.values())

    statistics = {
        'total_team_members': len(team_members),
        'total_weeks': len(weeks),
        'total_expected_timesheets': total_expected_weeks,
        'total_hours_logged': round(total_hours_logged, 1),
        'average_hours_per_person': round(total_hours_logged / len(team_members), 1) if team_members else 0
    }

    return {
        'clarity_month': clarity_month,
        'period_display': period_display,
        'start_date': start_date,
        'end_date': end_date,
        'weeks': weeks,
        'team_members': team_members,
        'weekly_hours': weekly_hours,
        'zero_hour_weeks': zero_hour_weeks,
        'month_totals': month_totals,
        'month_totals_days': month_totals_days,
        'statistics': statistics
    }


def generate_html_report(report_data: Dict) -> str:
    """Generate HTML for the labour hours report."""

    clarity_month = report_data['clarity_month']
    period_display = report_data['period_display']
    weeks = report_data['weeks']
    team_members = report_data['team_members']
    weekly_hours = report_data['weekly_hours']
    zero_hour_weeks = report_data['zero_hour_weeks']
    month_totals = report_data['month_totals']
    month_totals_days = report_data['month_totals_days']
    stats = report_data['statistics']

    # Generate week headers
    week_headers = []
    for week in weeks:
        week_str = week.strftime('%d %b')
        week_headers.append(f'<th class="week-header">{week_str}</th>')
    week_headers_html = '\n                    '.join(week_headers)

    # Generate table rows
    rows_html = []
    for person in team_members:
        cells = [f'<td class="person-name">{person}</td>']

        # Add weekly hour cells
        for week in weeks:
            week_str = week.strftime('%Y-%m-%d')
            is_zero_hour = (person, week_str) in zero_hour_weeks
            hours = weekly_hours.get((person, week_str), 0.0)

            if is_zero_hour:
                # Zero-hour timesheet (annual leave/absence)
                cell_class = "hours-cell zero-hours"
                cell_value = "0.0"
            elif hours > 0:
                # Regular hours logged
                cell_class = "hours-cell has-hours"
                cell_value = f"{hours:.1f}"
            else:
                # Missing timesheet
                cell_class = "hours-cell no-hours"
                cell_value = "-"

            cells.append(f'<td class="{cell_class}">{cell_value}</td>')

        # Add month totals (hours and days)
        total_hours = month_totals.get(person, 0.0)
        total_days = month_totals_days.get(person, 0.0)
        cells.append(f'<td class="month-total"><strong>{total_hours:.1f}</strong></td>')
        cells.append(f'<td class="month-total"><strong>{total_days:.1f}</strong></td>')

        row_html = '\n                    '.join(cells)
        rows_html.append(f'''
                <tr>
                    {row_html}
                </tr>''')

    rows_html_str = ''.join(rows_html)

    # Generate HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Labour Hours Report - {clarity_month}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 8px;
        }}

        .header p {{
            font-size: 16px;
            opacity: 0.9;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }}

        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
        }}

        .stat-value {{
            font-size: 32px;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 8px;
        }}

        .stat-label {{
            font-size: 14px;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .table-container {{
            overflow-x: auto;
            padding: 30px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
        }}

        th {{
            background: #667eea;
            color: white;
            padding: 15px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 14px;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        th.week-header {{
            text-align: center;
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid #e9ecef;
        }}

        td.person-name {{
            font-weight: 600;
            color: #2d3748;
            position: sticky;
            left: 0;
            background: white;
            z-index: 5;
        }}

        td.hours-cell {{
            text-align: center;
            font-weight: 500;
        }}

        td.has-hours {{
            color: #22c55e;
            background-color: #f0fdf4;
        }}

        td.zero-hours {{
            color: #f59e0b;
            background-color: #fffbeb;
            font-style: italic;
        }}

        td.no-hours {{
            color: #9ca3af;
            background-color: #f9fafb;
        }}

        td.month-total {{
            text-align: center;
            background: #f8f9fa;
            font-size: 16px;
            color: #1e293b;
            border-left: 2px solid #667eea;
        }}

        tr:hover {{
            background-color: #f8f9fa;
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}

            .container {{
                box-shadow: none;
            }}

            .stats {{
                page-break-after: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Labour Hours Report - {clarity_month}</h1>
            <p>Period: {period_display}</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{stats['total_team_members']}</div>
                <div class="stat-label">Team Members</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['total_weeks']}</div>
                <div class="stat-label">Weeks</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['total_hours_logged']:.1f}</div>
                <div class="stat-label">Total Hours</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['average_hours_per_person']:.1f}</div>
                <div class="stat-label">Avg Hours/Person</div>
            </div>
        </div>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        {week_headers_html}
                        <th class="week-header">Month Total (Hours)</th>
                        <th class="week-header">Month Total (Days)</th>
                    </tr>
                </thead>
                <tbody>{rows_html_str}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>'''

    return html


if __name__ == '__main__':
    # Test the report generation
    print("Generating Labour Hours Report for Nov-25...")

    report_data = generate_labour_hours_report(
        clarity_month='Nov-25',
        table_name='TimesheetOCR-dev',
        profile_name='AdministratorAccess-016164185850',
        region='us-east-1'
    )

    html = generate_html_report(report_data)

    # Save to file
    output_file = 'labour_hours_report_Nov-25.html'
    with open(output_file, 'w') as f:
        f.write(html)

    print(f"✓ Report generated: {output_file}")
    print(f"  Team members: {report_data['statistics']['total_team_members']}")
    print(f"  Weeks: {report_data['statistics']['total_weeks']}")
    print(f"  Total hours: {report_data['statistics']['total_hours_logged']:.1f}")
