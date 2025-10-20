"""
HTML report generation for timesheet calendar view.
"""
from typing import Dict
from datetime import datetime


def generate_html_calendar_report(report_data: Dict) -> str:
    """
    Generate HTML calendar report showing weeks with/without data.

    Args:
        report_data: Report data from generate_resource_calendar_report()

    Returns:
        HTML string
    """
    if not report_data.get('has_data'):
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Timesheet Report - {report_data['resource_name']}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    max-width: 1200px;
                    margin: 40px auto;
                    padding: 20px;
                    background: #f5f5f5;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>No Data Found</h1>
                <p>{report_data.get('message', 'No data available for this resource')}</p>
            </div>
        </body>
        </html>
        """

    resource_name = report_data['resource_name']
    stats = report_data['statistics']
    calendar = report_data['calendar']
    date_range = report_data['date_range']

    # Group weeks by month
    months = {}
    for week in calendar:
        week_start = datetime.strptime(week['week_start'], '%Y-%m-%d')
        month_key = week_start.strftime('%Y-%m')
        month_name = week_start.strftime('%B %Y')

        if month_key not in months:
            months[month_key] = {
                'name': month_name,
                'weeks': []
            }
        months[month_key]['weeks'].append(week)

    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Timesheet Report - {resource_name}</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}

            .container {{
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }}

            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px;
            }}

            .header h1 {{
                font-size: 32px;
                margin-bottom: 10px;
                font-weight: 600;
            }}

            .header p {{
                opacity: 0.9;
                font-size: 16px;
            }}

            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                padding: 40px;
                background: #f8f9fa;
                border-bottom: 1px solid #e0e0e0;
            }}

            .stat-card {{
                background: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                text-align: center;
            }}

            .stat-value {{
                font-size: 36px;
                font-weight: 700;
                color: #667eea;
                margin-bottom: 8px;
            }}

            .stat-label {{
                color: #666;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}

            .content {{
                padding: 40px;
            }}

            .month-section {{
                margin-bottom: 40px;
            }}

            .month-header {{
                font-size: 24px;
                font-weight: 600;
                color: #333;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 3px solid #667eea;
            }}

            .weeks-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 16px;
            }}

            .week-card {{
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                padding: 20px;
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }}

            .week-card::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 6px;
                height: 100%;
                background: #ddd;
            }}

            .week-card.present {{
                border-color: #4caf50;
                background: #f1f8f4;
            }}

            .week-card.present::before {{
                background: #4caf50;
            }}

            .week-card.zero-hour {{
                border-color: #ff9800;
                background: #fff8f0;
            }}

            .week-card.zero-hour::before {{
                background: #ff9800;
            }}

            .week-card.missing {{
                border-color: #f44336;
                background: #ffebee;
            }}

            .week-card.missing::before {{
                background: #f44336;
            }}

            .week-card:hover {{
                transform: translateY(-4px);
                box-shadow: 0 6px 20px rgba(0,0,0,0.15);
            }}

            .week-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }}

            .week-number {{
                font-size: 14px;
                font-weight: 600;
                color: #666;
            }}

            .status-badge {{
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
            }}

            .status-badge.present {{
                background: #4caf50;
                color: white;
            }}

            .status-badge.zero-hour {{
                background: #ff9800;
                color: white;
            }}

            .status-badge.missing {{
                background: #f44336;
                color: white;
            }}

            .week-dates {{
                font-size: 16px;
                font-weight: 600;
                color: #333;
                margin-bottom: 12px;
            }}

            .week-details {{
                font-size: 14px;
                color: #666;
                line-height: 1.6;
            }}

            .week-details .detail-row {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 6px;
            }}

            .icon {{
                display: inline-block;
                width: 24px;
                height: 24px;
                margin-right: 8px;
                vertical-align: middle;
            }}

            .icon.tick {{
                color: #4caf50;
                font-size: 24px;
            }}

            .icon.cross {{
                color: #f44336;
                font-size: 24px;
            }}

            .icon.warning {{
                color: #ff9800;
                font-size: 24px;
            }}

            .legend {{
                display: flex;
                gap: 30px;
                justify-content: center;
                padding: 30px;
                background: #f8f9fa;
                border-top: 1px solid #e0e0e0;
                margin-top: 40px;
            }}

            .legend-item {{
                display: flex;
                align-items: center;
                gap: 10px;
            }}

            .legend-color {{
                width: 24px;
                height: 24px;
                border-radius: 4px;
            }}

            .legend-color.present {{
                background: #4caf50;
            }}

            .legend-color.zero-hour {{
                background: #ff9800;
            }}

            .legend-color.missing {{
                background: #f44336;
            }}

            @media (max-width: 768px) {{
                .weeks-grid {{
                    grid-template-columns: 1fr;
                }}

                .stats {{
                    grid-template-columns: 1fr;
                }}

                .header {{
                    padding: 30px 20px;
                }}

                .content {{
                    padding: 20px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{resource_name}</h1>
                <p>Timesheet Submission Report</p>
                <p style="margin-top: 10px; font-size: 14px;">
                    Period: {date_range['start']} to {date_range['end']}
                </p>
            </div>

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value">{stats['total_weeks']}</div>
                    <div class="stat-label">Total Weeks</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: #4caf50;">{stats['weeks_present']}</div>
                    <div class="stat-label">Submitted</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: #f44336;">{stats['weeks_missing']}</div>
                    <div class="stat-label">Missing</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: #ff9800;">{stats['zero_hour_weeks']}</div>
                    <div class="stat-label">Zero Hour</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{stats['completion_percentage']}%</div>
                    <div class="stat-label">Completion</div>
                </div>
            </div>

            <div class="content">
    """

    # Generate month sections
    for month_key in sorted(months.keys(), reverse=True):
        month_data = months[month_key]
        html += f"""
                <div class="month-section">
                    <div class="month-header">{month_data['name']}</div>
                    <div class="weeks-grid">
        """

        for week in month_data['weeks']:
            status = week['status']
            is_zero_hour = week.get('is_zero_hour', False)

            # Determine card class and status badge
            if is_zero_hour:
                card_class = 'zero-hour'
                badge_class = 'zero-hour'
                badge_text = f"Zero Hour ({week.get('zero_hour_reason', 'ABSENCE')})"
                icon = '⚠'
            elif status == 'present':
                card_class = 'present'
                badge_class = 'present'
                badge_text = 'Submitted'
                icon = '✓'
            else:
                card_class = 'missing'
                badge_class = 'missing'
                badge_text = 'Missing'
                icon = '✗'

            week_start_fmt = datetime.strptime(week['week_start'], '%Y-%m-%d').strftime('%b %d')
            week_end_fmt = datetime.strptime(week['week_end'], '%Y-%m-%d').strftime('%b %d')

            html += f"""
                        <div class="week-card {card_class}">
                            <div class="week-header">
                                <span class="week-number">Week {week['iso_week']}</span>
                                <span class="status-badge {badge_class}">{badge_text}</span>
                            </div>
                            <div class="week-dates">
                                <span class="icon">{icon}</span>
                                {week_start_fmt} - {week_end_fmt}
                            </div>
                            <div class="week-details">
            """

            if status == 'present':
                if is_zero_hour:
                    html += f"""
                                <div class="detail-row">
                                    <span>Status:</span>
                                    <span><strong>Annual Leave / Absence</strong></span>
                                </div>
                    """
                else:
                    html += f"""
                                <div class="detail-row">
                                    <span>Total Hours:</span>
                                    <span><strong>{week['total_hours']:.1f}h</strong></span>
                                </div>
                                <div class="detail-row">
                                    <span>Projects:</span>
                                    <span><strong>{week['projects_count']}</strong></span>
                                </div>
                    """
                    if week.get('project_codes'):
                        codes = ', '.join(week['project_codes'][:3])
                        if len(week['project_codes']) > 3:
                            codes += f" +{len(week['project_codes']) - 3} more"
                        html += f"""
                                <div class="detail-row">
                                    <span style="font-size: 12px; color: #999;">{codes}</span>
                                </div>
                        """
            else:
                html += """
                                <div class="detail-row">
                                    <span>Status:</span>
                                    <span style="color: #f44336;"><strong>No Submission</strong></span>
                                </div>
                """

            html += """
                            </div>
                        </div>
            """

        html += """
                    </div>
                </div>
        """

    # Close HTML
    html += """
            </div>

            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color present"></div>
                    <span>Timesheet Submitted</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color zero-hour"></div>
                    <span>Zero Hour (Leave/Absence)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color missing"></div>
                    <span>Missing Submission</span>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return html
