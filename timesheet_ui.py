#!/usr/bin/env python3
"""
Timesheet OCR - Desktop UI for Mac
Upload timesheets and view data in DynamoDB
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkcalendar import DateEntry
import boto3
import json
import os
import csv
import sys
from pathlib import Path
from datetime import datetime
import threading
import time
import io
from decimal import Decimal
from collections import defaultdict

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from team_manager import TeamManager

# AWS Configuration
INPUT_BUCKET = "timesheetocr-input-dev-016164185850"
DYNAMODB_TABLE = "TimesheetOCR-dev"
LAMBDA_FUNCTION = "TimesheetOCR-ocr-dev"
AWS_REGION = "us-east-1"

# AWS Clients
s3_client = boto3.client('s3', region_name=AWS_REGION)
lambda_client = boto3.client('lambda', region_name=AWS_REGION)
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE)


class TimesheetOCRApp:
    def __init__(self, root):
        self.root = root
        # Add version timestamp to window title
        version = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.root.title(f"Timesheet OCR - DynamoDB Edition [v{version}]")
        self.root.geometry("1200x1000")
        self.root.resizable(True, True)

        # Variables
        self.selected_files = []
        self.processing = False

        # Initialize team manager
        self.team_manager = TeamManager()

        # Setup UI
        self.setup_ui()

        # Load initial database view
        self.root.after(500, self.view_data)

    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        # Only the notebook (row 9) should expand vertically
        main_frame.rowconfigure(9, weight=1)

        # Title and status bar frame
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, pady=10)

        title = ttk.Label(title_frame, text="📊 Timesheet OCR Processor",
                         font=('Helvetica', 18, 'bold'))
        title.pack(side=tk.LEFT, padx=(0, 20))

        # Bank holiday indicator
        bank_holiday_frame = ttk.Frame(title_frame, relief=tk.RIDGE, borderwidth=2, padding=5)
        bank_holiday_frame.pack(side=tk.LEFT)

        bank_holiday_icon = ttk.Label(bank_holiday_frame, text="✓",
                                      foreground="green", font=('Helvetica', 14, 'bold'))
        bank_holiday_icon.pack(side=tk.LEFT, padx=(0, 5))

        bank_holiday_label = ttk.Label(bank_holiday_frame,
                                       text="2025 UK Bank Holidays Enabled",
                                       font=('Helvetica', 10))
        bank_holiday_label.pack(side=tk.LEFT)

        # File selection frame
        file_frame = ttk.LabelFrame(main_frame, text="1. Select Timesheet Images", padding="10")
        file_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
        file_frame.columnconfigure(1, weight=1)

        self.select_btn = ttk.Button(file_frame, text="📁 Select Files...",
                                     command=self.select_files, width=20)
        self.select_btn.grid(row=0, column=0, padx=5)

        self.file_label = ttk.Label(file_frame, text="No files selected",
                                    foreground="gray")
        self.file_label.grid(row=0, column=1, sticky=tk.W, padx=10)

        self.clear_btn = ttk.Button(file_frame, text="✕ Clear",
                                    command=self.clear_files, width=10)
        self.clear_btn.grid(row=0, column=2, padx=5)
        self.clear_btn.state(['disabled'])

        # File list
        self.file_listbox = tk.Listbox(file_frame, height=5, selectmode=tk.EXTENDED)
        self.file_listbox.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E),
                              pady=10, padx=5)

        scrollbar = ttk.Scrollbar(file_frame, orient=tk.VERTICAL,
                                 command=self.file_listbox.yview)
        scrollbar.grid(row=1, column=3, sticky=(tk.N, tk.S))
        self.file_listbox.configure(yscrollcommand=scrollbar.set)

        # Process button frame
        process_frame = ttk.Frame(main_frame, width=1000, height=80)
        process_frame.grid(row=2, column=0, pady=10, sticky=(tk.W, tk.E))
        process_frame.grid_propagate(False)  # Maintain fixed height

        # Configure columns to expand evenly
        process_frame.columnconfigure(0, weight=1, minsize=200)
        process_frame.columnconfigure(1, weight=1, minsize=160)
        process_frame.columnconfigure(2, weight=1, minsize=130)
        process_frame.columnconfigure(3, weight=1, minsize=200)

        self.process_btn = ttk.Button(process_frame, text="🚀 Upload & Process",
                                      command=self.process_files)
        self.process_btn.grid(row=0, column=0, padx=8, sticky=(tk.W, tk.E))
        self.process_btn.state(['disabled'])

        self.view_btn = ttk.Button(process_frame, text="📊 View Data",
                                   command=self.view_data)
        self.view_btn.grid(row=0, column=1, padx=8, sticky=(tk.W, tk.E))

        self.refresh_btn = ttk.Button(process_frame, text="🔄 Refresh",
                                      command=self.refresh_data)
        self.refresh_btn.grid(row=0, column=2, padx=8, sticky=(tk.W, tk.E))

        self.report_btn = ttk.Button(process_frame, text="📥 Export Full Data",
                                     command=self.export_full_database)
        self.report_btn.grid(row=0, column=3, padx=8, sticky=(tk.W, tk.E))

        # Add import button
        self.import_btn = ttk.Button(process_frame, text="📤 Import Corrections",
                                     command=self.import_corrections)
        self.import_btn.grid(row=1, column=3, padx=8, pady=5, sticky=(tk.W, tk.E))

        # Add re-scan failed images button
        self.rescan_btn = ttk.Button(process_frame, text="🔄 Re-scan Failed Images",
                                     command=self.rescan_failed_images)
        self.rescan_btn.grid(row=1, column=0, columnspan=2, padx=8, pady=5, sticky=(tk.W, tk.E))

        # Data Quality section
        quality_frame = ttk.LabelFrame(main_frame, text="🔍 Data Quality", padding="10")
        quality_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        quality_frame.columnconfigure(0, weight=1)
        quality_frame.columnconfigure(1, weight=1)

        self.similar_codes_btn = ttk.Button(
            quality_frame,
            text="🔎 Find Similar Project Codes",
            command=self.find_similar_codes
        )
        self.similar_codes_btn.grid(row=0, column=0, padx=5, sticky=(tk.W, tk.E))

        ttk.Label(quality_frame, text="Detect potential OCR errors in project codes",
                 font=('TkDefaultFont', 9, 'italic')).grid(row=0, column=1, padx=5, sticky=tk.W)

        # Add dictionary update button
        self.update_dict_btn = ttk.Button(
            quality_frame,
            text="📚 Update Reference Dictionaries",
            command=self.update_dictionaries
        )
        self.update_dict_btn.grid(row=1, column=0, padx=5, pady=5, sticky=(tk.W, tk.E))

        ttk.Label(quality_frame, text="Rebuild validation dictionaries from current database",
                 font=('TkDefaultFont', 9, 'italic')).grid(row=1, column=1, padx=5, sticky=tk.W)

        # S3 Bucket Information section
        bucket_frame = ttk.LabelFrame(main_frame, text="🪣 S3 Buckets", padding="10")
        bucket_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)
        bucket_frame.columnconfigure(0, weight=1)
        bucket_frame.columnconfigure(1, weight=1)

        self.list_bucket_btn = ttk.Button(
            bucket_frame,
            text="📋 List Images in S3",
            command=self.list_bucket_images
        )
        self.list_bucket_btn.grid(row=0, column=0, padx=5, sticky=(tk.W, tk.E))

        ttk.Label(bucket_frame, text=f"Bucket: {INPUT_BUCKET}",
                 font=('TkDefaultFont', 9, 'italic')).grid(row=0, column=1, padx=5, sticky=tk.W)

        # Bulk Operations section
        bulk_frame = ttk.LabelFrame(main_frame, text="⚙️ Bulk Operations", padding="10")
        bulk_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=10)
        bulk_frame.columnconfigure(0, weight=1)
        bulk_frame.columnconfigure(1, weight=1)

        self.flush_db_btn = ttk.Button(
            bulk_frame,
            text="🗑️ Flush Database",
            command=self.flush_database
        )
        self.flush_db_btn.grid(row=0, column=0, padx=5, sticky=(tk.W, tk.E))

        ttk.Label(bulk_frame, text="Careful! This deletes ALL data from DynamoDB",
                 font=('TkDefaultFont', 9, 'italic'), foreground='red').grid(row=0, column=1, padx=5, sticky=tk.W)

        # Period summary export frame
        summary_frame = ttk.LabelFrame(main_frame, text="📅 Period Export", padding="10")
        summary_frame.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=10)
        summary_frame.columnconfigure(0, weight=0, minsize=80)   # Label
        summary_frame.columnconfigure(1, weight=0, minsize=180)  # Start date picker
        summary_frame.columnconfigure(2, weight=0, minsize=80)   # Label
        summary_frame.columnconfigure(3, weight=0, minsize=180)  # End date picker
        summary_frame.columnconfigure(4, weight=1, minsize=160)  # Summary button
        summary_frame.columnconfigure(5, weight=1, minsize=160)  # Detailed button

        # Start date with calendar picker
        ttk.Label(summary_frame, text="Start Date:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.start_date_picker = DateEntry(
            summary_frame,
            width=15,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',
            firstweekday='monday'
        )
        # Default to first day of current month
        self.start_date_picker.set_date(datetime.now().replace(day=1))
        self.start_date_picker.grid(row=0, column=1, padx=5, sticky=tk.W)

        # End date with calendar picker
        ttk.Label(summary_frame, text="End Date:").grid(row=0, column=2, padx=5, sticky=tk.W)
        self.end_date_picker = DateEntry(
            summary_frame,
            width=15,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',
            firstweekday='monday'
        )
        # Default to today
        self.end_date_picker.set_date(datetime.now())
        self.end_date_picker.grid(row=0, column=3, padx=5, sticky=tk.W)

        # Export buttons
        self.summary_btn = ttk.Button(summary_frame, text="📊 Export Summary", width=18,
                                      command=self.export_period_summary)
        self.summary_btn.grid(row=0, column=4, padx=5, sticky=(tk.W, tk.E))

        self.detailed_btn = ttk.Button(summary_frame, text="📋 Export Detailed", width=18,
                                       command=self.export_period_detailed)
        self.detailed_btn.grid(row=0, column=5, padx=5, sticky=(tk.W, tk.E))

        # Clarity Month export frame (VMO2 billing periods)
        clarity_frame = ttk.LabelFrame(main_frame, text="📅 Clarity Month Export (VMO2)", padding="10")
        clarity_frame.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=10)
        clarity_frame.columnconfigure(0, weight=0, minsize=120)  # Label
        clarity_frame.columnconfigure(1, weight=1, minsize=350)  # Dropdown
        clarity_frame.columnconfigure(2, weight=0, minsize=160)  # Summary button
        clarity_frame.columnconfigure(3, weight=0, minsize=160)  # Detailed button

        # Load Clarity months
        self.clarity_months = self.load_clarity_months()

        # Clarity month dropdown
        ttk.Label(clarity_frame, text="Clarity Month:").grid(row=0, column=0, padx=5, sticky=tk.W)

        self.clarity_month_var = tk.StringVar()
        clarity_month_options = [cm['display'] for cm in self.clarity_months]

        # Default to current Clarity month
        current_clarity = self.get_current_clarity_month()
        if current_clarity:
            self.clarity_month_var.set(current_clarity['display'])
        elif clarity_month_options:
            self.clarity_month_var.set(clarity_month_options[0])

        self.clarity_dropdown = ttk.Combobox(
            clarity_frame,
            textvariable=self.clarity_month_var,
            values=clarity_month_options,
            state='readonly',
            width=45
        )
        self.clarity_dropdown.grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))

        # Export buttons for Clarity month
        self.clarity_summary_btn = ttk.Button(
            clarity_frame,
            text="📊 Export Summary",
            width=18,
            command=self.export_clarity_summary
        )
        self.clarity_summary_btn.grid(row=0, column=2, padx=5, sticky=(tk.W, tk.E))

        self.clarity_detailed_btn = ttk.Button(
            clarity_frame,
            text="📋 Export Detailed",
            width=18,
            command=self.export_clarity_detailed
        )
        self.clarity_detailed_btn.grid(row=0, column=3, padx=5, sticky=(tk.W, tk.E))

        self.clarity_coverage_btn = ttk.Button(
            clarity_frame,
            text="🔍 Coverage Check",
            width=18,
            command=self.check_clarity_coverage
        )
        self.clarity_coverage_btn.grid(row=0, column=4, padx=5, sticky=(tk.W, tk.E))

        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=8, column=0, sticky=(tk.W, tk.E), pady=5)

        # Notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=9, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        # Logs tab
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="📋 Logs")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8,
                                                  wrap=tk.WORD, state='disabled')
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Data view tab
        data_frame = ttk.Frame(notebook)
        notebook.add(data_frame, text="📊 Database View")
        data_frame.columnconfigure(0, weight=1)
        data_frame.rowconfigure(0, weight=0)
        data_frame.rowconfigure(1, weight=1)

        # Database control buttons
        db_controls = ttk.Frame(data_frame)
        db_controls.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)

        ttk.Button(db_controls, text="🔄 Refresh",
                  command=self.refresh_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_controls, text="🗑️ Delete Selected Image",
                  command=self.delete_by_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_controls, text="📋 Show Image Source",
                  command=self.show_image_source).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_controls, text="❌ Export Failed Images",
                  command=self.export_failed_images).pack(side=tk.LEFT, padx=5)

        # Create Treeview for data
        columns = ('Resource', 'Date', 'Project', 'Code', 'Hours', 'Source')
        self.tree = ttk.Treeview(data_frame, columns=columns, show='headings', height=15)

        # Define headings
        self.tree.heading('Resource', text='Resource Name')
        self.tree.heading('Date', text='Date')
        self.tree.heading('Project', text='Project Name')
        self.tree.heading('Code', text='Project Code')
        self.tree.heading('Hours', text='Hours')
        self.tree.heading('Source', text='Source Image')

        # Define column widths
        self.tree.column('Resource', width=150)
        self.tree.column('Date', width=100)
        self.tree.column('Project', width=250)
        self.tree.column('Code', width=100)
        self.tree.column('Hours', width=80)
        self.tree.column('Source', width=250)

        self.tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Add scrollbars to treeview
        tree_scroll_y = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scroll_y.grid(row=1, column=1, sticky=(tk.N, tk.S))
        self.tree.configure(yscrollcommand=tree_scroll_y.set)

        tree_scroll_x = ttk.Scrollbar(data_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        tree_scroll_x.grid(row=2, column=0, sticky=(tk.W, tk.E))
        self.tree.configure(xscrollcommand=tree_scroll_x.set)

        # Team Management tab
        team_frame = ttk.Frame(notebook)
        notebook.add(team_frame, text="👥 Team Management")
        team_frame.columnconfigure(0, weight=1)
        team_frame.columnconfigure(1, weight=1)
        team_frame.rowconfigure(0, weight=1)  # Top row with roster and duplicates
        team_frame.rowconfigure(1, weight=1)  # Bottom row with aliases

        # Team roster section
        roster_frame = ttk.LabelFrame(team_frame, text="Team Roster", padding="10")
        roster_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        roster_frame.columnconfigure(0, weight=1)
        roster_frame.rowconfigure(0, weight=1)

        # Team member listbox
        self.team_listbox = tk.Listbox(roster_frame, height=15)
        self.team_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        roster_scroll = ttk.Scrollbar(roster_frame, orient=tk.VERTICAL, command=self.team_listbox.yview)
        roster_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.team_listbox.configure(yscrollcommand=roster_scroll.set)

        # Roster buttons
        roster_btn_frame = ttk.Frame(roster_frame)
        roster_btn_frame.grid(row=1, column=0, columnspan=2, pady=10)

        ttk.Button(roster_btn_frame, text="➕ Add Member", width=18,
                  command=self.add_team_member).grid(row=0, column=0, padx=5, pady=2)
        ttk.Button(roster_btn_frame, text="➖ Remove Selected", width=18,
                  command=self.remove_team_member).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(roster_btn_frame, text="🔄 Refresh", width=18,
                  command=self.refresh_team_roster).grid(row=0, column=2, padx=5, pady=2)

        # Duplicate detection section
        dup_frame = ttk.LabelFrame(team_frame, text="Duplicate Detection", padding="10")
        dup_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        dup_frame.columnconfigure(0, weight=1)
        dup_frame.rowconfigure(0, weight=1)

        # Duplicates display
        self.dup_text = scrolledtext.ScrolledText(dup_frame, height=15, wrap=tk.WORD, state='disabled')
        self.dup_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Duplicate buttons
        dup_btn_frame = ttk.Frame(dup_frame)
        dup_btn_frame.grid(row=1, column=0, pady=10)

        ttk.Button(dup_btn_frame, text="🔍 Find Duplicates", width=22,
                  command=self.find_duplicates).grid(row=0, column=0, padx=5, pady=2)
        ttk.Button(dup_btn_frame, text="🔧 How to Fix", width=22,
                  command=self.fix_duplicate).grid(row=0, column=1, padx=5, pady=2)

        # Name aliases section
        alias_frame = ttk.LabelFrame(team_frame, text="Name Aliases (OCR Corrections)", padding="10")
        alias_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        alias_frame.columnconfigure(0, weight=1)
        alias_frame.rowconfigure(0, weight=1)

        # Alias treeview
        alias_columns = ('Alias', 'Correct Name')
        self.alias_tree = ttk.Treeview(alias_frame, columns=alias_columns, show='headings', height=8)
        self.alias_tree.heading('Alias', text='OCR Variant')
        self.alias_tree.heading('Correct Name', text='Canonical Name')
        self.alias_tree.column('Alias', width=200)
        self.alias_tree.column('Correct Name', width=200)
        self.alias_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        alias_scroll = ttk.Scrollbar(alias_frame, orient=tk.VERTICAL, command=self.alias_tree.yview)
        alias_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.alias_tree.configure(yscrollcommand=alias_scroll.set)

        # Alias buttons
        alias_btn_frame = ttk.Frame(alias_frame)
        alias_btn_frame.grid(row=1, column=0, columnspan=2, pady=10)

        ttk.Button(alias_btn_frame, text="➕ Add Alias", width=20,
                  command=self.add_alias).grid(row=0, column=0, padx=5, pady=2)
        ttk.Button(alias_btn_frame, text="➖ Remove Selected", width=20,
                  command=self.remove_alias).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(alias_btn_frame, text="🔄 Refresh", width=20,
                  command=self.refresh_aliases).grid(row=0, column=2, padx=5, pady=2)

        # Project Management tab
        project_frame = ttk.Frame(notebook)
        notebook.add(project_frame, text="📦 Project Management")
        project_frame.columnconfigure(0, weight=1)
        project_frame.rowconfigure(0, weight=0)
        project_frame.rowconfigure(1, weight=1)

        # Project controls
        project_controls = ttk.Frame(project_frame)
        project_controls.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

        ttk.Button(project_controls, text="🔄 Refresh Projects",
                  command=self.refresh_projects).pack(side=tk.LEFT, padx=5)
        ttk.Button(project_controls, text="➕ Add Project",
                  command=self.add_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(project_controls, text="✏️ Edit Selected",
                  command=self.edit_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(project_controls, text="🗑️ Delete Selected",
                  command=self.delete_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(project_controls, text="📥 Import from DB",
                  command=self.import_projects_from_db).pack(side=tk.LEFT, padx=5)

        # Project list
        project_list_frame = ttk.Frame(project_frame)
        project_list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        project_list_frame.columnconfigure(0, weight=1)
        project_list_frame.rowconfigure(0, weight=1)

        # Create Treeview for projects
        project_columns = ('Code', 'Name', 'Aliases')
        self.project_tree = ttk.Treeview(project_list_frame, columns=project_columns,
                                         show='headings', height=15)

        # Define headings
        self.project_tree.heading('Code', text='Project Code')
        self.project_tree.heading('Name', text='Project Name')
        self.project_tree.heading('Aliases', text='Known Aliases')

        # Column widths
        self.project_tree.column('Code', width=150)
        self.project_tree.column('Name', width=300)
        self.project_tree.column('Aliases', width=400)

        # Scrollbars for project tree
        project_scroll_y = ttk.Scrollbar(project_list_frame, orient=tk.VERTICAL,
                                        command=self.project_tree.yview)
        project_scroll_x = ttk.Scrollbar(project_list_frame, orient=tk.HORIZONTAL,
                                        command=self.project_tree.xview)

        self.project_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        project_scroll_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        project_scroll_x.grid(row=1, column=0, sticky=(tk.W, tk.E))

        self.project_tree.configure(yscrollcommand=project_scroll_y.set,
                                   xscrollcommand=project_scroll_x.set)

        # Load initial team data
        self.refresh_team_roster()
        self.refresh_aliases()
        self.refresh_projects()

        # Info footer (moved to row 6, after notebook on row 5)
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(row=6, column=0, pady=10)

        ttk.Label(info_frame, text=f"📦 Input Bucket: {INPUT_BUCKET}",
                 font=('Courier', 9)).grid(row=0, column=0, padx=20)
        ttk.Label(info_frame, text=f"💾 DynamoDB Table: {DYNAMODB_TABLE}",
                 font=('Courier', 9)).grid(row=0, column=1, padx=20)

        # Initial log message
        self.log("Ready! Select timesheet images to upload and process.")
        self.log("Data is now stored in DynamoDB instead of CSV files.")

    def select_files(self):
        """Open file dialog to select timesheet images"""
        files = filedialog.askopenfilenames(
            title="Select Timesheet Images",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg"),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("All files", "*.*")
            ]
        )

        if files:
            self.selected_files = list(files)
            self.file_listbox.delete(0, tk.END)
            for file in self.selected_files:
                self.file_listbox.insert(tk.END, Path(file).name)

            count = len(self.selected_files)
            self.file_label.config(text=f"{count} file(s) selected", foreground="green")
            self.clear_btn.state(['!disabled'])
            self.process_btn.state(['!disabled'])
            self.log(f"Selected {count} file(s)")

    def clear_files(self):
        """Clear selected files"""
        self.selected_files = []
        self.file_listbox.delete(0, tk.END)
        self.file_label.config(text="No files selected", foreground="gray")
        self.clear_btn.state(['disabled'])
        self.process_btn.state(['disabled'])
        self.log("Cleared file selection")

    def log(self, message):
        """Add message to log area"""
        self.log_text.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.root.update_idletasks()

    def process_files(self):
        """Upload files and trigger Lambda processing"""
        if not self.selected_files:
            messagebox.showwarning("No Files", "Please select files first!")
            return

        # Disable buttons during processing
        self.process_btn.state(['disabled'])
        self.select_btn.state(['disabled'])
        self.clear_btn.state(['disabled'])
        self.processing = True
        self.progress.start()

        # Process in background thread
        thread = threading.Thread(target=self._process_files_thread)
        thread.daemon = True
        thread.start()

    def _process_files_thread(self):
        """Background thread for processing files"""
        results = []

        try:
            for i, file_path in enumerate(self.selected_files):
                filename = Path(file_path).name
                self.log(f"Processing {i+1}/{len(self.selected_files)}: {filename}")

                # Upload to S3
                self.log(f"  ⬆️  Uploading to S3...")
                s3_client.upload_file(file_path, INPUT_BUCKET, filename)
                self.log(f"  ✓ Uploaded to s3://{INPUT_BUCKET}/{filename}")

                # Trigger Lambda
                self.log(f"  🚀 Triggering Lambda function...")
                payload = {
                    "Records": [{
                        "s3": {
                            "bucket": {"name": INPUT_BUCKET},
                            "object": {"key": filename}
                        }
                    }]
                }

                response = lambda_client.invoke(
                    FunctionName=LAMBDA_FUNCTION,
                    InvocationType='RequestResponse',
                    Payload=json.dumps(payload)
                )

                # Parse response
                response_payload = json.loads(response['Payload'].read())

                if response_payload.get('statusCode') == 200:
                    body = json.loads(response_payload['body'])
                    self.log(f"  ✓ Success!")
                    self.log(f"    Resource: {body.get('resource_name', 'N/A')}")
                    self.log(f"    Date Range: {body.get('date_range', 'N/A')}")
                    self.log(f"    Projects: {body.get('projects_count', 0)}")
                    self.log(f"    Entries Stored: {body.get('entries_stored', 0)}")
                    self.log(f"    Time: {body.get('processing_time_seconds', 0):.2f}s")
                    self.log(f"    Cost: ${body.get('cost_estimate_usd', 0):.6f}")
                    results.append((filename, "Success", body))
                else:
                    error = json.loads(response_payload['body']).get('error', 'Unknown error')
                    self.log(f"  ✗ Error: {error}")
                    results.append((filename, "Failed", error))

                self.log("")  # Blank line

            # Summary
            success_count = sum(1 for _, status, _ in results if status == "Success")
            self.log(f"{'='*50}")
            self.log(f"Processing complete!")
            self.log(f"Success: {success_count}/{len(results)}")

            if success_count > 0:
                self.log(f"✓ Data stored in DynamoDB table: {DYNAMODB_TABLE}")
                self.log(f"✓ Click 'View Data' or 'Refresh' to see the results")
                messagebox.showinfo("Success",
                                   f"Successfully processed {success_count}/{len(results)} timesheet(s)!\n\n"
                                   f"Data is now in DynamoDB.\n"
                                   f"Click 'View Data' to see results.")
                # Auto-refresh data view
                self.root.after(0, self.refresh_data)

        except Exception as e:
            self.log(f"✗ ERROR: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")

        finally:
            # Re-enable buttons
            self.processing = False
            self.progress.stop()
            self.root.after(0, self._enable_buttons)

    def _enable_buttons(self):
        """Re-enable buttons after processing"""
        self.process_btn.state(['!disabled'])
        self.select_btn.state(['!disabled'])
        if self.selected_files:
            self.clear_btn.state(['!disabled'])

    def view_data(self):
        """View data in DynamoDB table"""
        self.log("Loading data from DynamoDB...")
        thread = threading.Thread(target=self._load_data_thread)
        thread.daemon = True
        thread.start()

    def refresh_data(self):
        """Refresh data view"""
        self.view_data()

    def load_data(self):
        """Alias for view_data() - for compatibility"""
        self.view_data()

    def show_image_source(self):
        """Show which image the selected entry came from"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an entry to view its source")
            return

        # Get the selected item's source image
        item = self.tree.item(selection[0])
        values = item['values']
        source_image = values[5]  # Source column is index 5

        messagebox.showinfo("Source Image",
                          f"This entry came from:\n\n{source_image}")

    def delete_by_image(self):
        """Delete all entries from the same source image as the selected entry"""
        try:
            selection = self.tree.selection()
            if not selection:
                messagebox.showwarning("No Selection",
                                     "Please select an entry to delete all entries from its source image")
                return

            # Get the selected item's source image
            item = self.tree.item(selection[0])
            values = item['values']
            source_image = values[5]  # Source column is index 5
            resource_name = values[0]

            # Confirm deletion
            if not messagebox.askyesno("Confirm Delete",
                                      f"This will delete ALL entries from:\n\n"
                                      f"Image: {source_image}\n"
                                      f"Resource: {resource_name}\n\n"
                                      f"Are you sure?"):
                return

            self.log(f"🗑️ Deleting all entries from: {source_image}")

            # Query all entries with this source image
            response = table.scan(
                FilterExpression='SourceImage = :img',
                ExpressionAttributeValues={':img': source_image}
            )

            items_to_delete = response.get('Items', [])

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = table.scan(
                    FilterExpression='SourceImage = :img',
                    ExpressionAttributeValues={':img': source_image},
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items_to_delete.extend(response.get('Items', []))

            if not items_to_delete:
                messagebox.showinfo("No Data", "No entries found for this image")
                return

            # Delete all items in batches
            deleted_count = 0
            with table.batch_writer() as batch:
                for item in items_to_delete:
                    batch.delete_item(
                        Key={
                            'ResourceName': item['ResourceName'],
                            'DateProjectCode': item['DateProjectCode']
                        }
                    )
                    deleted_count += 1

            self.log(f"✓ Deleted {deleted_count} entries from {source_image}")

            # Refresh the view
            self.refresh_data()

            messagebox.showinfo("Delete Complete",
                              f"Deleted {deleted_count} entries from:\n{source_image}")

        except Exception as e:
            self.log(f"✗ Error deleting entries: {str(e)}")
            messagebox.showerror("Delete Error", f"Failed to delete entries:\n{str(e)}")

    def export_failed_images(self):
        """Export failed images report to CSV"""
        try:
            from src.failed_image_logger import export_failed_images_csv, get_failure_statistics

            self.log("Generating failed images report...")

            # Get statistics
            stats = get_failure_statistics(table_name)

            if stats['total_failures'] == 0:
                messagebox.showinfo("No Failures", "No failed images found in database!")
                self.log("No failed images to export")
                return

            # Ask where to save
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"failed_images_{timestamp}.csv"

            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=default_filename
            )

            if not filepath:
                self.log("Export cancelled")
                return

            # Export to CSV
            count = export_failed_images_csv(table_name, filepath)

            # Show statistics
            self.log(f"✓ Exported {count} failures to {filepath}")

            stats_message = (
                f"Failed Images Export Complete\n\n"
                f"Total failures: {stats['total_failures']}\n"
                f"Unique images: {stats['unique_images']}\n"
                f"Recent (24h): {stats['recent_failures_24h']}\n\n"
                f"Failure Types:\n"
            )

            if stats['failure_types']:
                for ftype, fcount in stats['failure_types'].items():
                    stats_message += f"  - {ftype}: {fcount}\n"

            stats_message += f"\n✅ Exported to:\n{filepath}"

            messagebox.showinfo("Export Complete", stats_message)

        except ImportError:
            messagebox.showerror("Error",
                               "Failed image logging module not found.\n"
                               "Make sure src/failed_image_logger.py exists.")
        except Exception as e:
            self.log(f"✗ Error exporting failed images: {str(e)}")
            messagebox.showerror("Error", f"Failed to export: {str(e)}")

    def _load_data_thread(self):
        """Background thread for loading data"""
        try:
            # Clear existing data
            for item in self.tree.get_children():
                self.tree.delete(item)

            # Scan DynamoDB table (in production, you'd want pagination)
            self.log("Scanning DynamoDB table...")
            response = table.scan()
            items = response.get('Items', [])

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                items.extend(response.get('Items', []))

            if not items:
                self.log("No data found in DynamoDB table")
                messagebox.showinfo("No Data", "No timesheet data found in DynamoDB.\n\n"
                                   "Process some timesheets first!")
                return

            # Sort by date and resource
            items_sorted = sorted(items, key=lambda x: (x.get('Date', ''), x.get('ResourceName', '')))

            # Insert data into treeview
            for item in items_sorted:
                resource = item.get('ResourceNameDisplay', item.get('ResourceName', 'N/A'))
                date = item.get('Date', 'N/A')
                project = item.get('ProjectName', 'N/A')
                code = item.get('ProjectCode', 'N/A')
                hours = float(item.get('Hours', 0))
                source = item.get('SourceImage', 'N/A')

                self.tree.insert('', tk.END, values=(resource, date, project, code, hours, source))

            self.log(f"✓ Loaded {len(items)} entries from DynamoDB")

            # Show summary
            unique_resources = len(set(item.get('ResourceName', '') for item in items))
            total_hours = sum(float(item.get('Hours', 0)) for item in items)
            self.log(f"Summary: {unique_resources} resources, {total_hours:.1f} total hours")

        except Exception as e:
            self.log(f"✗ Error loading data: {str(e)}")
            messagebox.showerror("Error", f"Failed to load data from DynamoDB:\n{str(e)}")

    def export_full_database(self):
        """Export complete database with ALL fields for offline editing."""
        self.log("Exporting full database...")
        thread = threading.Thread(target=self._export_full_database_thread)
        thread.daemon = True
        thread.start()

    def _export_full_database_thread(self):
        """Background thread for exporting complete database."""
        try:
            # Scan DynamoDB table
            self.log("Fetching all data from DynamoDB...")
            response = table.scan()
            items = response.get('Items', [])

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                items.extend(response.get('Items', []))

            if not items:
                self.log("No data found in DynamoDB table")
                messagebox.showinfo("No Data", "No timesheet data found.\n\nProcess some timesheets first!")
                return

            self.log(f"Fetched {len(items)} records from database")

            # Define all fields to export (maintaining order for consistency)
            all_fields = [
                'ResourceName',           # Primary Key (partition)
                'DateProjectCode',        # Sort Key
                'ResourceNameDisplay',    # Display name
                'Date',                   # Individual date
                'WeekStartDate',          # Week start
                'WeekEndDate',            # Week end
                'ProjectCode',            # Project code
                'ProjectName',            # Project name
                'Hours',                  # Hours worked
                'IsZeroHourTimesheet',    # Zero hour flag
                'ZeroHourReason',         # Reason if zero hour
                'SourceImage',            # Original image filename
                'ProcessingTimestamp',    # When processed
                'YearMonth',              # For querying
            ]

            # Create CSV data with ALL fields
            csv_rows = []
            csv_rows.append(all_fields)  # Header row

            # Convert each item to CSV row
            for item in sorted(items, key=lambda x: (x.get('ResourceName', ''), x.get('DateProjectCode', ''))):
                row = []
                for field in all_fields:
                    value = item.get(field, '')

                    # Convert Decimal to float for proper CSV formatting
                    if isinstance(value, Decimal):
                        value = float(value)

                    # Convert boolean to string
                    if isinstance(value, bool):
                        value = str(value)

                    # Ensure it's a string
                    row.append(str(value) if value != '' else '')

                csv_rows.append(row)

            self.log(f"✓ Prepared {len(csv_rows)-1} rows for export")

            # Ask user where to save
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"timesheet_full_export_{timestamp}.csv"

            save_path = filedialog.asksaveasfilename(
                title="Export Full Database",
                defaultextension=".csv",
                initialfile=default_filename,
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not save_path:
                self.log("Export cancelled")
                return

            # Write CSV file
            with open(save_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(csv_rows)

            self.log(f"✓ Full database exported to: {save_path}")

            # Show success message
            messagebox.showinfo(
                "Export Complete",
                f"Full database exported successfully!\n\n"
                f"File: {os.path.basename(save_path)}\n"
                f"Location: {os.path.dirname(save_path)}\n\n"
                f"Total Records: {len(csv_rows)-1}\n\n"
                f"You can now:\n"
                f"1. Open in Excel/Numbers to fix OCR errors\n"
                f"2. Use 'Import Corrections' to update database"
            )

            # Open the folder containing the file
            folder_path = os.path.dirname(save_path)
            os.system(f'open "{folder_path}"')

        except Exception as e:
            self.log(f"✗ Error generating report: {str(e)}")
            messagebox.showerror("Error", f"Failed to generate report:\n{str(e)}")

    def import_corrections(self):
        """Import corrected CSV to update database with only changed rows."""
        self.log("Starting import of corrections...")

        # Ask user to select CSV file
        file_path = filedialog.askopenfilename(
            title="Select Corrected CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            self.log("Import cancelled")
            return

        self.log(f"Selected file: {file_path}")

        # Start import in background thread
        thread = threading.Thread(target=self._import_corrections_thread, args=(file_path,))
        thread.daemon = True
        thread.start()

    def _import_corrections_thread(self, file_path):
        """Background thread for importing corrections."""
        try:
            # Read CSV file
            self.log("Reading CSV file...")
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                csv_rows = list(reader)

            if not csv_rows:
                self.log("✗ No data found in CSV file")
                messagebox.showerror("Error", "CSV file is empty or has no data rows")
                return

            self.log(f"✓ Read {len(csv_rows)} rows from CSV")

            # Expected fields (must match export format)
            expected_fields = [
                'ResourceName', 'DateProjectCode', 'ResourceNameDisplay', 'Date',
                'WeekStartDate', 'WeekEndDate', 'ProjectCode', 'ProjectName',
                'Hours', 'IsZeroHourTimesheet', 'ZeroHourReason', 'SourceImage',
                'ProcessingTimestamp', 'YearMonth'
            ]

            # Validate CSV headers
            csv_fields = set(reader.fieldnames) if hasattr(reader, 'fieldnames') else set(csv_rows[0].keys())
            missing_fields = set(expected_fields) - csv_fields

            if missing_fields:
                error_msg = f"CSV is missing required fields: {', '.join(missing_fields)}"
                self.log(f"✗ {error_msg}")
                messagebox.showerror("Invalid CSV", error_msg)
                return

            self.log("✓ CSV format validated")

            # Process each row
            rows_checked = 0
            rows_updated = 0
            rows_skipped = 0
            errors = []

            for idx, csv_row in enumerate(csv_rows, start=1):
                try:
                    # Extract primary key
                    resource_name = csv_row.get('ResourceName', '').strip()
                    date_project_code = csv_row.get('DateProjectCode', '').strip()

                    if not resource_name or not date_project_code:
                        errors.append(f"Row {idx}: Missing primary key (ResourceName or DateProjectCode)")
                        rows_skipped += 1
                        continue

                    # Fetch existing item from DynamoDB
                    response = table.get_item(
                        Key={
                            'ResourceName': resource_name,
                            'DateProjectCode': date_project_code
                        }
                    )

                    existing_item = response.get('Item')

                    if not existing_item:
                        # Item doesn't exist in database - skip it
                        errors.append(f"Row {idx}: No matching record found for {resource_name} / {date_project_code}")
                        rows_skipped += 1
                        continue

                    rows_checked += 1

                    # Compare fields to detect changes
                    has_changes = False
                    updates = {}

                    for field in expected_fields:
                        # Skip primary keys (can't update those)
                        if field in ['ResourceName', 'DateProjectCode']:
                            continue

                        csv_value = csv_row.get(field, '').strip()
                        existing_value = existing_item.get(field, '')

                        # Convert existing value to string for comparison
                        if isinstance(existing_value, Decimal):
                            existing_value = str(float(existing_value))
                        elif isinstance(existing_value, bool):
                            existing_value = str(existing_value)
                        else:
                            existing_value = str(existing_value) if existing_value else ''

                        # Compare values
                        if csv_value != existing_value:
                            has_changes = True

                            # Convert CSV value to appropriate type
                            if field == 'Hours':
                                # Convert to Decimal for DynamoDB
                                updates[field] = Decimal(str(csv_value)) if csv_value else Decimal('0')
                            elif field == 'IsZeroHourTimesheet':
                                # Convert to boolean
                                updates[field] = csv_value.lower() in ['true', '1', 'yes']
                            else:
                                # Keep as string
                                updates[field] = csv_value

                    # Update item if changes detected
                    if has_changes:
                        # Build update expression
                        update_expr = "SET " + ", ".join([f"#{k} = :{k}" for k in updates.keys()])
                        expr_attr_names = {f"#{k}": k for k in updates.keys()}
                        expr_attr_values = {f":{k}": v for k, v in updates.items()}

                        # Update in DynamoDB
                        table.update_item(
                            Key={
                                'ResourceName': resource_name,
                                'DateProjectCode': date_project_code
                            },
                            UpdateExpression=update_expr,
                            ExpressionAttributeNames=expr_attr_names,
                            ExpressionAttributeValues=expr_attr_values
                        )

                        rows_updated += 1
                        self.log(f"  → Updated: {resource_name} / {date_project_code}")

                except Exception as e:
                    errors.append(f"Row {idx}: {str(e)}")
                    rows_skipped += 1

            # Build result message
            result_msg = (
                f"Import Complete!\n\n"
                f"Rows in CSV: {len(csv_rows)}\n"
                f"Rows checked: {rows_checked}\n"
                f"Rows updated: {rows_updated}\n"
                f"Rows skipped: {rows_skipped}\n"
            )

            if errors:
                result_msg += f"\nErrors encountered: {len(errors)}\n"
                if len(errors) <= 10:
                    result_msg += "\n" + "\n".join(errors)
                else:
                    result_msg += "\n" + "\n".join(errors[:10]) + f"\n... and {len(errors) - 10} more"

            self.log(f"✓ Import complete: {rows_updated} rows updated, {rows_skipped} skipped")

            if errors:
                messagebox.showwarning("Import Complete (with errors)", result_msg)
            else:
                messagebox.showinfo("Import Complete", result_msg)

            # Refresh the display
            if rows_updated > 0:
                self.log("Refreshing display...")
                self.load_data()

        except Exception as e:
            self.log(f"✗ Error importing corrections: {str(e)}")
            messagebox.showerror("Import Error", f"Failed to import corrections:\n{str(e)}")

    def rescan_failed_images(self):
        """Find and re-process failed images from S3."""
        # Ask user for scan mode
        mode_dialog = messagebox.askquestion(
            "Scan Mode",
            "Do you want to review each image before adding to database?\n\n"
            "• YES = Interactive review mode (approve each image)\n"
            "• NO = Automatic batch processing (no approval needed)",
            icon='question'
        )

        interactive_mode = (mode_dialog == 'yes')

        self.log(f"🔍 Starting scan in {'INTERACTIVE' if interactive_mode else 'AUTOMATIC'} mode...")
        thread = threading.Thread(target=self._rescan_failed_thread, args=(interactive_mode,))
        thread.daemon = True
        thread.start()

    def _rescan_failed_thread(self, interactive_mode=False):
        """Background thread for finding and re-processing failed images."""
        import os
        import tempfile

        # Prevent concurrent scans using a lock file
        lock_file = os.path.join(tempfile.gettempdir(), 'timesheet_ui_scan.lock')

        if os.path.exists(lock_file):
            # Check if lock is stale (older than 1 hour)
            lock_age = time.time() - os.path.getmtime(lock_file)
            if lock_age < 3600:  # 1 hour
                self.log("⚠️  Another scan is already in progress! Please wait for it to complete.")
                messagebox.showwarning(
                    "Scan In Progress",
                    "Another scan is already running. Please wait for it to complete before starting a new scan."
                )
                return
            else:
                self.log("⚠️  Found stale lock file (>1 hour old), removing it...")
                try:
                    os.remove(lock_file)
                except:
                    pass

        # Create lock file
        try:
            with open(lock_file, 'w') as f:
                f.write(f"{os.getpid()}\n{time.time()}\n")
        except Exception as e:
            self.log(f"⚠️  Warning: Could not create lock file: {e}")

        try:
            self.interactive_mode = interactive_mode
            self.stop_scan = False  # Flag to stop scanning
            # Step 1: Find failed images
            self.log("📁 Scanning S3 bucket...")
            s3_images = set()
            paginator = s3_client.get_paginator('list_objects_v2')

            for page in paginator.paginate(Bucket=INPUT_BUCKET):
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    key = obj['Key']
                    if key.lower().endswith(('.png', '.jpg', '.jpeg')) and not key.startswith('quicksight-data/'):
                        s3_images.add(key)

            self.log(f"✓ Found {len(s3_images)} images in S3")

            # Step 2: Get processed images from DynamoDB
            # NEW APPROACH: Get ALL images that have been successfully stored
            # We check for actual timesheet entries (not REJECTED or ZERO_HOUR metadata entries)
            self.log("📊 Checking DynamoDB for processed images...")

            # Get all unique SourceImage values from actual timesheet entries
            response = table.scan(
                ProjectionExpression='SourceImage,DateProjectCode,ResourceName,#d',
                FilterExpression='attribute_exists(ResourceName) AND attribute_exists(#d)',
                ExpressionAttributeNames={'#d': 'Date'}
            )
            processed_images = set()

            for item in response.get('Items', []):
                source = item.get('SourceImage', '')
                # If it has ResourceName and Date, it's a real timesheet entry
                if source:
                    processed_images.add(source)

            while 'LastEvaluatedKey' in response:
                response = table.scan(
                    ProjectionExpression='SourceImage,DateProjectCode,ResourceName,#d',
                    FilterExpression='attribute_exists(ResourceName) AND attribute_exists(#d)',
                    ExpressionAttributeNames={'#d': 'Date'},
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                for item in response.get('Items', []):
                    source = item.get('SourceImage', '')
                    if source:
                        processed_images.add(source)

            self.log(f"✓ Found {len(processed_images)} processed images in DB")

            # Step 3: Find failed images
            failed_images = sorted(list(s3_images - processed_images))

            if not failed_images:
                self.log("🎉 No failed images found! All S3 images have been processed.")
                messagebox.showinfo(
                    "No Failed Images",
                    "Great news! All images in S3 have been successfully processed.\n\n"
                    f"Total images: {len(s3_images)}\n"
                    f"Successfully processed: {len(processed_images)}\n"
                    f"Success rate: 100%"
                )
                return

            # Show summary and ask for confirmation
            success_rate = (len(processed_images) / len(s3_images) * 100) if s3_images else 0
            self.log(f"⚠️  Found {len(failed_images)} failed images ({success_rate:.1f}% success rate)")

            # Ask user if they want to proceed
            result = messagebox.askyesno(
                "Re-scan Failed Images",
                f"Found {len(failed_images)} images that failed to process.\n\n"
                f"Total images in S3: {len(s3_images)}\n"
                f"Successfully processed: {len(processed_images)}\n"
                f"Failed: {len(failed_images)}\n"
                f"Success rate: {success_rate:.1f}%\n\n"
                f"Do you want to re-process the failed images now?\n"
                f"(This may take several minutes)"
            )

            if not result:
                self.log("Re-scan cancelled by user")
                return

            # Step 4: Re-process failed images
            self.log(f"🚀 Starting re-processing of {len(failed_images)} failed images...")

            success_count = 0
            fail_count = 0

            # Track successfully processed images in this session to avoid re-scanning
            newly_processed_images = set()

            for i, image_key in enumerate(failed_images, 1):
                # Check if user requested stop
                if self.stop_scan:
                    self.log("⚠️  Scan stopped by user")
                    break

                # Skip if already processed in this session
                if image_key in newly_processed_images:
                    self.log(f"[{i}/{len(failed_images)}] Skipping {image_key} - already processed in this session")
                    success_count += 1
                    continue

                self.log(f"[{i}/{len(failed_images)}] Processing: {image_key}")

                try:
                    if self.interactive_mode:
                        # Interactive mode: OCR first, then show approval, then save
                        # Add rate limiting: wait 2 seconds between OCR calls to prevent throttling
                        if i > 1:  # Skip delay for first image
                            time.sleep(2)

                        self.log(f"  [DEBUG] Interactive mode - starting OCR...")
                        print(f"[DEBUG] Image {i}: Starting OCR for {image_key}")

                        ocr_data = self._perform_ocr_only(image_key)
                        print(f"[DEBUG] Image {i}: OCR returned: {ocr_data.keys() if isinstance(ocr_data, dict) else 'ERROR'}")

                        if ocr_data.get('error'):
                            self.log(f"  ✗ OCR Failed: {ocr_data['error']}")
                            print(f"[DEBUG] Image {i}: OCR failed with error")
                            fail_count += 1
                            continue

                        self.log(f"  OCR complete: {ocr_data.get('resource_name', 'Unknown')}")
                        print(f"[DEBUG] Image {i}: OCR successful, preparing dialog...")
                        self.log(f"  [DEBUG] Preparing approval dialog...")

                        # Use queue to get result from main thread
                        import queue
                        result_queue = queue.Queue()
                        dialog_shown = {'flag': False}

                        def show_dialog_wrapper():
                            try:
                                print(f"[DEBUG] Image {i}: show_dialog_wrapper CALLED")
                                dialog_shown['flag'] = True
                                action = self._show_approval_dialog_blocking(image_key, ocr_data)
                                print(f"[DEBUG] Image {i}: Dialog returned action: {action}")
                                result_queue.put(action)
                            except Exception as e:
                                print(f"[DEBUG] Image {i}: Dialog exception: {str(e)}")
                                import traceback
                                traceback.print_exc()
                                self.log(f"  ✗ Dialog error: {str(e)}")
                                result_queue.put('approve')  # Default to approve on error

                        # Schedule dialog on main thread
                        print(f"[DEBUG] Image {i}: Scheduling dialog on main thread...")
                        self.root.after(0, show_dialog_wrapper)

                        # Wait a moment to ensure it's scheduled
                        time.sleep(0.5)
                        print(f"[DEBUG] Image {i}: Waiting for dialog result... (dialog_shown={dialog_shown['flag']})")
                        self.log(f"  [DEBUG] Waiting for user approval...")

                        # Wait for result
                        approval = result_queue.get(timeout=300)  # 5 minute timeout
                        print(f"[DEBUG] Image {i}: Got approval result: {approval}")

                        if approval == 'stop':
                            self.log("⚠️  Scan stopped by user")
                            self.stop_scan = True
                            break
                        elif approval == 'delete':
                            self.log(f"  🗑️ Image deleted from S3 (low quality)")
                            fail_count += 1
                        elif approval == 'auto':
                            self.log("  → Switching to automatic mode")
                            self.interactive_mode = False
                            # Save to database
                            self._save_ocr_to_database(image_key, ocr_data)
                            self.log(f"  ✓ Success: {ocr_data.get('resource_name', 'Unknown')}")
                            newly_processed_images.add(image_key)  # Mark as processed
                            success_count += 1
                        elif approval == 'approve':
                            # Save to database
                            self._save_ocr_to_database(image_key, ocr_data)
                            self.log(f"  ✓ Approved: {ocr_data.get('resource_name', 'Unknown')}")
                            newly_processed_images.add(image_key)  # Mark as processed
                            success_count += 1
                        elif approval == 'reject':
                            self.log(f"  ✗ Rejected by user")
                            fail_count += 1
                    else:
                        # Automatic mode: use Lambda (which saves automatically)
                        payload = {
                            "Records": [{
                                "s3": {
                                    "bucket": {"name": INPUT_BUCKET},
                                    "object": {"key": image_key}
                                }
                            }]
                        }

                        response = lambda_client.invoke(
                            FunctionName=LAMBDA_FUNCTION,
                            InvocationType='RequestResponse',
                            Payload=json.dumps(payload)
                        )

                        result = json.loads(response['Payload'].read())

                        if response['StatusCode'] == 200 and 'errorMessage' not in result:
                            if isinstance(result, dict) and 'body' in result:
                                body = json.loads(result['body'])
                                resource_name = body.get('resource_name', 'Unknown')
                                entries = body.get('entries_stored', 0)
                                self.log(f"  ✓ Success: {resource_name} - {entries} entries")
                                newly_processed_images.add(image_key)  # Mark as processed
                                success_count += 1
                            else:
                                self.log(f"  ✓ Processed")
                                newly_processed_images.add(image_key)  # Mark as processed
                                success_count += 1
                        else:
                            error_msg = result.get('errorMessage', 'Unknown error')
                            self.log(f"  ✗ Failed: {error_msg}")
                            fail_count += 1

                except Exception as e:
                    self.log(f"  ✗ Error: {str(e)}")
                    fail_count += 1

                # Small delay every 10 images to avoid rate limiting
                if i % 10 == 0:
                    time.sleep(1)

            # Show summary
            final_success_rate = (success_count / len(failed_images) * 100) if failed_images else 0

            self.log("=" * 60)
            self.log(f"✓ Re-processing complete!")
            self.log(f"  Attempted: {len(failed_images)}")
            self.log(f"  Successful: {success_count}")
            self.log(f"  Still failed: {fail_count}")
            self.log(f"  Success rate: {final_success_rate:.1f}%")

            messagebox.showinfo(
                "Re-scan Complete",
                f"Re-processing finished!\n\n"
                f"Attempted: {len(failed_images)}\n"
                f"✓ Successful: {success_count}\n"
                f"✗ Still failed: {fail_count}\n"
                f"Success rate: {final_success_rate:.1f}%\n\n"
                f"Click 'Refresh' to see the updated data."
            )

            # Auto-refresh the data
            self.load_data()

        except Exception as e:
            self.log(f"✗ Error during re-scan: {str(e)}")
            messagebox.showerror("Re-scan Error", f"Failed to re-scan images:\n{str(e)}")

        finally:
            # Always clean up lock file
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    self.log("🔓 Released scan lock")
            except Exception as e:
                self.log(f"⚠️  Warning: Could not remove lock file: {e}")

    def update_dictionaries(self):
        """Update reference dictionaries for field validators."""
        # Confirm action
        result = messagebox.askyesno(
            "Update Reference Dictionaries",
            "This will scan the database and rebuild the reference dictionaries\n"
            "used by field validators to auto-correct OCR errors.\n\n"
            "This may take 1-2 minutes. Continue?",
            icon='question'
        )

        if not result:
            return

        self.log("📚 Updating reference dictionaries...")
        thread = threading.Thread(target=self._update_dictionaries_thread)
        thread.daemon = True
        thread.start()

    def _update_dictionaries_thread(self):
        """Background thread for updating dictionaries."""
        try:
            self.progress.start()

            # Import the extraction logic from create_dictionaries.py
            import subprocess
            import sys

            # Get the script path
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, 'create_dictionaries.py')

            # Run the dictionary extraction script
            self.log("   Scanning database for high-quality records...")
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            self.progress.stop()

            if result.returncode == 0:
                # Parse the output to extract statistics
                output_lines = result.stdout.split('\n')
                stats = {}
                for line in output_lines:
                    if 'Project Codes:' in line:
                        stats['project_codes'] = line.split(':')[1].strip()
                    elif 'Person Names:' in line:
                        stats['person_names'] = line.split(':')[1].strip()

                success_msg = "✅ Reference dictionaries updated successfully!\n\n"
                if stats:
                    success_msg += f"Project Codes: {stats.get('project_codes', 'N/A')}\n"
                    success_msg += f"Person Names: {stats.get('person_names', 'N/A')}\n"
                success_msg += "\nLambda functions will use the updated dictionaries on next invocation."

                self.log(success_msg.replace('\n', ' '))
                self.root.after(0, messagebox.showinfo, "Dictionaries Updated", success_msg)
            else:
                error_msg = f"Failed to update dictionaries:\n{result.stderr}"
                self.log(f"❌ {error_msg}")
                self.root.after(0, messagebox.showerror, "Update Failed", error_msg)

        except subprocess.TimeoutExpired:
            self.progress.stop()
            error_msg = "Dictionary update timed out (>5 minutes)"
            self.log(f"❌ {error_msg}")
            self.root.after(0, messagebox.showerror, "Timeout", error_msg)
        except Exception as e:
            self.progress.stop()
            error_msg = f"Failed to update dictionaries: {str(e)}"
            self.log(f"❌ {error_msg}")
            self.root.after(0, messagebox.showerror, "Update Failed", error_msg)

    def find_similar_codes(self):
        """Find similar project codes that might be OCR errors."""
        self.log("🔍 Searching for similar project codes...")
        thread = threading.Thread(target=self._find_similar_codes_thread)
        thread.daemon = True
        thread.start()

    def _find_similar_codes_thread(self):
        """Background thread for finding similar project codes."""
        try:
            self.progress.start()

            from find_similar_project_codes import (
                get_all_resources,
                find_similar_codes_for_resource,
                highlight_difference
            )

            # Get all resources
            resources = get_all_resources()
            self.log(f"✅ Found {len(resources)} unique resources")

            # Find similar codes
            all_similar_pairs = []
            total_similar = 0

            for resource in resources:
                similar_pairs = find_similar_codes_for_resource(resource)

                if len(similar_pairs) > 0:
                    display_name = resource.replace('_', ' ')
                    self.log(f"   {display_name}: {len(similar_pairs)} similar pairs")
                    all_similar_pairs.append((resource, similar_pairs))
                    total_similar += len(similar_pairs)

            self.progress.stop()

            # Display results
            self.root.after(0, self._show_similar_codes_report, all_similar_pairs, total_similar)

        except Exception as e:
            self.progress.stop()
            error_msg = f"Failed to find similar codes: {str(e)}"
            self.log(f"❌ {error_msg}")
            self.root.after(0, messagebox.showerror, "Similar Codes Failed", error_msg)

    def _show_similar_codes_report(self, all_similar_pairs, total_similar):
        """Display similar codes report in a popup window."""
        if total_similar == 0:
            messagebox.showinfo(
                "No Similar Codes",
                "✅ No similar project codes found!\n\n"
                "All project codes appear to be unique."
            )
            return

        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title("Similar Project Codes - Potential OCR Errors")
        popup.geometry("1200x800")

        # Main frame
        main_frame = ttk.Frame(popup, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        popup.columnconfigure(0, weight=1)
        popup.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Summary at top
        summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding="10")
        summary_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        summary_text = f"Found {total_similar} potential OCR errors across {len(all_similar_pairs)} people\n"
        summary_text += "These are project codes that differ by only 1-2 characters on the same date."

        summary_label = ttk.Label(summary_frame, text=summary_text, font=('TkDefaultFont', 10))
        summary_label.pack()

        # Report text area
        text_frame = ttk.Frame(main_frame)
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        report_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, font=('Courier', 10))
        report_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Build report content
        from find_similar_project_codes import highlight_difference

        lines = []
        lines.append("=" * 100)
        lines.append("SIMILAR PROJECT CODES - POTENTIAL OCR ERRORS")
        lines.append("=" * 100)
        lines.append("")
        lines.append("These are cases where similar project codes exist for the same person on the same date.")
        lines.append("This often indicates OCR errors (e.g., PJ024542 vs PJ024642 where 5 was misread as 6).")
        lines.append("")
        lines.append("🔍 FILTERING APPLIED:")
        lines.append("   • Only shows codes with Levenshtein distance ≤ 2")
        lines.append("   • Only shows codes where project names are ≥70% similar")
        lines.append("   • This filters out legitimate different projects with similar codes")
        lines.append("")

        for resource, similar_pairs in all_similar_pairs:
            display_name = resource.replace('_', ' ')
            lines.append("")
            lines.append("=" * 100)
            lines.append(f"👤 {display_name} - {len(similar_pairs)} potential errors")
            lines.append("=" * 100)

            for date_str, distance, details1, details2 in similar_pairs:
                lines.append("")
                lines.append(f"📅 Date: {date_str}")

                # Highlight differences
                highlighted1, highlighted2 = highlight_difference(details1['code'], details2['code'])

                lines.append(f"   Code 1: {highlighted1}")
                lines.append(f"      Hours: {details1['hours']}h")
                lines.append(f"      Source: {details1['source']}")
                lines.append(f"      Project: {details1['project_name']}")

                lines.append(f"   Code 2: {highlighted2}")
                lines.append(f"      Hours: {details2['hours']}h")
                lines.append(f"      Source: {details2['source']}")
                lines.append(f"      Project: {details2['project_name']}")

                name_sim = details1.get('name_similarity', 0) * 100
                lines.append(f"   Code Distance: {distance} character(s) | Name Similarity: {name_sim:.0f}%")
                lines.append("")

        lines.append("=" * 100)
        lines.append("⚠️  RECOMMENDATION:")
        lines.append("Review the source images to determine which project code is correct.")
        lines.append("Delete the incorrect entries manually from the Database View tab.")
        lines.append("=" * 100)

        report_content = "\n".join(lines)
        report_text.insert('1.0', report_content)
        report_text.config(state='disabled')

        # Buttons at bottom
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        def export_txt():
            """Export report as text file."""
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"similar_codes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if filename:
                try:
                    with open(filename, 'w') as f:
                        f.write(report_content)
                    messagebox.showinfo("Success", f"Report exported to:\n{filename}")
                except Exception as e:
                    messagebox.showerror("Export Failed", f"Failed to export report: {e}")

        ttk.Button(button_frame, text="📄 Export TXT", command=export_txt).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Close", command=popup.destroy).pack(side=tk.RIGHT, padx=5)

    def export_period_summary(self):
        """Export summary of hours worked by resource for a selected period."""
        try:
            # Get dates from calendar pickers
            start_date = self.start_date_picker.get_date()
            end_date = self.end_date_picker.get_date()

            # Convert to datetime objects (calendar returns date objects)
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.min.time())

            # Validate date range
            if start_date > end_date:
                messagebox.showerror("Invalid Date Range",
                                   "Start date must be before or equal to end date")
                return

            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            self.log(f"Exporting summary for period: {start_date_str} to {end_date_str}")

            # Start export in background thread
            thread = threading.Thread(target=self._export_period_summary_thread,
                                    args=(start_date, end_date))
            thread.daemon = True
            thread.start()

        except Exception as e:
            self.log(f"✗ Error: {str(e)}")
            messagebox.showerror("Error", f"Failed to start export:\n{str(e)}")

    def _export_period_summary_thread(self, start_date, end_date):
        """Background thread for exporting period summary."""
        try:
            # Format dates for display and filtering
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            self.log("Fetching data from DynamoDB...")

            # Scan DynamoDB table
            response = table.scan()
            items = response.get('Items', [])

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                items.extend(response.get('Items', []))

            if not items:
                self.log("No data found in database")
                messagebox.showinfo("No Data", "No timesheet data found in database")
                return

            self.log(f"✓ Fetched {len(items)} records")

            # Filter items by date range (INCLUSIVE of both start and end dates)
            # This means if you select 2025-10-01 to 2025-10-31, timesheets
            # dated 2025-10-01 AND 2025-10-31 will both be included
            self.log(f"Filtering for dates: {start_str} to {end_str} (inclusive)")
            filtered_items = []
            for item in items:
                item_date_str = item.get('Date', '')
                if not item_date_str:
                    continue

                try:
                    item_date = datetime.strptime(item_date_str, "%Y-%m-%d")
                    # IMPORTANT: Using <= ensures BOTH start and end dates are included
                    if start_date <= item_date <= end_date:
                        filtered_items.append(item)
                except ValueError:
                    # Skip items with invalid date format
                    continue

            if not filtered_items:
                self.log(f"No data found for period {start_str} to {end_str}")
                messagebox.showinfo("No Data",
                                  f"No timesheet data found for the period:\n"
                                  f"{start_str} to {end_str}")
                return

            self.log(f"✓ Found {len(filtered_items)} records in date range")

            # Aggregate hours by resource
            resource_hours = {}
            for item in filtered_items:
                resource = item.get('ResourceNameDisplay') or item.get('ResourceName', 'Unknown')
                hours = item.get('Hours', Decimal('0'))

                # Convert Decimal to float
                if isinstance(hours, Decimal):
                    hours = float(hours)
                else:
                    hours = float(hours) if hours else 0.0

                if resource in resource_hours:
                    resource_hours[resource] += hours
                else:
                    resource_hours[resource] = hours

            self.log(f"✓ Calculated totals for {len(resource_hours)} resources")

            # Create CSV data
            csv_rows = []
            csv_rows.append(['Resource Name', 'Total Hours', 'Total Days (Hours ÷ 7.5)'])

            # Sort by resource name
            for resource in sorted(resource_hours.keys()):
                total_hours = resource_hours[resource]
                total_days = total_hours / 7.5  # Convert hours to days

                csv_rows.append([
                    resource,
                    f"{total_hours:.2f}",
                    f"{total_days:.2f}"
                ])

            # Add totals row
            grand_total_hours = sum(resource_hours.values())
            grand_total_days = grand_total_hours / 7.5
            csv_rows.append([])  # Empty row
            csv_rows.append([
                'TOTAL',
                f"{grand_total_hours:.2f}",
                f"{grand_total_days:.2f}"
            ])

            # Ask user where to save
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"timesheet_summary_{start_str}_to_{end_str}_{timestamp}.csv"

            save_path = filedialog.asksaveasfilename(
                title="Export Period Summary",
                defaultextension=".csv",
                initialfile=default_filename,
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not save_path:
                self.log("Export cancelled")
                return

            # Write CSV file
            with open(save_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(csv_rows)

            self.log(f"✓ Period summary exported to: {save_path}")

            # Show success message
            messagebox.showinfo(
                "Export Complete",
                f"Period summary exported successfully!\n\n"
                f"File: {os.path.basename(save_path)}\n"
                f"Location: {os.path.dirname(save_path)}\n\n"
                f"Period: {start_str} to {end_str}\n"
                f"Resources: {len(resource_hours)}\n"
                f"Total Hours: {grand_total_hours:.2f}\n"
                f"Total Days: {grand_total_days:.2f}"
            )

            # Open the folder containing the file
            folder_path = os.path.dirname(save_path)
            os.system(f'open "{folder_path}"')

        except Exception as e:
            self.log(f"✗ Error exporting summary: {str(e)}")
            messagebox.showerror("Export Error", f"Failed to export summary:\n{str(e)}")

    def export_period_detailed(self):
        """Export detailed timesheet data (all fields) for a selected period."""
        try:
            # Get dates from calendar pickers
            start_date = self.start_date_picker.get_date()
            end_date = self.end_date_picker.get_date()

            # Convert to datetime objects (calendar returns date objects)
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.min.time())

            # Validate date range
            if start_date > end_date:
                messagebox.showerror("Invalid Date Range",
                                   "Start date must be before or equal to end date")
                return

            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            self.log(f"Exporting detailed data for period: {start_date_str} to {end_date_str}")

            # Start export in background thread
            thread = threading.Thread(target=self._export_period_detailed_thread,
                                    args=(start_date, end_date))
            thread.daemon = True
            thread.start()

        except Exception as e:
            self.log(f"✗ Error: {str(e)}")
            messagebox.showerror("Error", f"Failed to start export:\n{str(e)}")

    def _export_period_detailed_thread(self, start_date, end_date):
        """Background thread for exporting detailed period data."""
        try:
            # Format dates for display
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            self.log("Fetching data from DynamoDB...")

            # Scan DynamoDB table
            response = table.scan()
            items = response.get('Items', [])

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                items.extend(response.get('Items', []))

            if not items:
                self.log("No data found in database")
                messagebox.showinfo("No Data", "No timesheet data found in database")
                return

            self.log(f"✓ Fetched {len(items)} records")

            # Filter items by date range (INCLUSIVE of both start and end dates)
            self.log(f"Filtering for dates: {start_str} to {end_str} (inclusive)")
            filtered_items = []
            for item in items:
                item_date_str = item.get('Date', '')
                if not item_date_str:
                    continue

                try:
                    item_date = datetime.strptime(item_date_str, "%Y-%m-%d")
                    # IMPORTANT: Using <= ensures BOTH start and end dates are included
                    if start_date <= item_date <= end_date:
                        filtered_items.append(item)
                except ValueError:
                    # Skip items with invalid date format
                    continue

            if not filtered_items:
                self.log(f"No data found for period {start_str} to {end_str}")
                messagebox.showinfo("No Data",
                                  f"No timesheet data found for the period:\n"
                                  f"{start_str} to {end_str}")
                return

            self.log(f"✓ Found {len(filtered_items)} records in date range")

            # Define all fields to export (same as full export)
            all_fields = [
                'ResourceName',           # Primary Key (partition)
                'DateProjectCode',        # Sort Key
                'ResourceNameDisplay',    # Display name
                'Date',                   # Individual date
                'WeekStartDate',          # Week start
                'WeekEndDate',            # Week end
                'ProjectCode',            # Project code
                'ProjectName',            # Project name
                'Hours',                  # Hours worked
                'IsZeroHourTimesheet',    # Zero hour flag
                'ZeroHourReason',         # Reason if zero hour
                'SourceImage',            # Original image filename
                'ProcessingTimestamp',    # When processed
                'YearMonth',              # For querying
            ]

            # Create CSV data with ALL fields
            csv_rows = []
            csv_rows.append(all_fields)  # Header row

            # Convert each filtered item to CSV row
            for item in sorted(filtered_items, key=lambda x: (x.get('Date', ''), x.get('ResourceName', ''))):
                row = []
                for field in all_fields:
                    value = item.get(field, '')

                    # Convert Decimal to float for proper CSV formatting
                    if isinstance(value, Decimal):
                        value = float(value)

                    # Convert boolean to string
                    if isinstance(value, bool):
                        value = str(value)

                    # Ensure it's a string
                    row.append(str(value) if value != '' else '')

                csv_rows.append(row)

            self.log(f"✓ Prepared {len(csv_rows)-1} rows for export")

            # Ask user where to save
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"timesheet_detailed_{start_str}_to_{end_str}_{timestamp}.csv"

            save_path = filedialog.asksaveasfilename(
                title="Export Detailed Period Data",
                defaultextension=".csv",
                initialfile=default_filename,
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not save_path:
                self.log("Export cancelled")
                return

            # Write CSV file
            with open(save_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(csv_rows)

            self.log(f"✓ Detailed data exported to: {save_path}")

            # Show success message
            messagebox.showinfo(
                "Export Complete",
                f"Detailed timesheet data exported successfully!\n\n"
                f"File: {os.path.basename(save_path)}\n"
                f"Location: {os.path.dirname(save_path)}\n\n"
                f"Period: {start_str} to {end_str}\n"
                f"Total Records: {len(csv_rows)-1}\n"
                f"All {len(all_fields)} fields included"
            )

            # Open the folder containing the file
            folder_path = os.path.dirname(save_path)
            os.system(f'open "{folder_path}"')

        except Exception as e:
            self.log(f"✗ Error exporting detailed data: {str(e)}")
            messagebox.showerror("Export Error", f"Failed to export detailed data:\n{str(e)}")

    # Team Management Methods

    def refresh_team_roster(self):
        """Refresh the team roster listbox"""
        self.team_listbox.delete(0, tk.END)
        members = self.team_manager.get_team_members()
        for member in members:
            self.team_listbox.insert(tk.END, member)
        self.log(f"Team roster loaded: {len(members)} members")

    def add_team_member(self):
        """Add a new team member"""
        # Create input dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Team Member")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Enter team member name:").pack(pady=10)

        name_var = tk.StringVar()
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=40)
        name_entry.pack(pady=5)
        name_entry.focus()

        def do_add():
            name = name_var.get().strip()
            if name:
                if self.team_manager.add_member(name):
                    self.refresh_team_roster()
                    self.log(f"✓ Added team member: {name}")
                    dialog.destroy()
                else:
                    messagebox.showwarning("Duplicate", f"{name} is already in the team roster")
            else:
                messagebox.showwarning("Invalid", "Please enter a name")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Add", command=do_add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        dialog.bind('<Return>', lambda e: do_add())

    def remove_team_member(self):
        """Remove selected team member"""
        selection = self.team_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a team member to remove")
            return

        name = self.team_listbox.get(selection[0])

        if messagebox.askyesno("Confirm", f"Remove {name} from team roster?"):
            if self.team_manager.remove_member(name):
                self.refresh_team_roster()
                self.log(f"✓ Removed team member: {name}")

    def refresh_aliases(self):
        """Refresh the aliases treeview"""
        # Clear existing items
        for item in self.alias_tree.get_children():
            self.alias_tree.delete(item)

        # Add all aliases
        aliases = self.team_manager.get_aliases()
        for alias, canonical in sorted(aliases.items()):
            self.alias_tree.insert('', tk.END, values=(alias, canonical))

        self.log(f"Name aliases loaded: {len(aliases)} mappings")

    def add_alias(self):
        """Add a new name alias"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Name Alias")
        dialog.geometry("500x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="OCR Variant (incorrect name):").pack(pady=5)
        alias_var = tk.StringVar()
        alias_entry = ttk.Entry(dialog, textvariable=alias_var, width=50)
        alias_entry.pack(pady=5)
        alias_entry.focus()

        ttk.Label(dialog, text="Canonical Name (correct name):").pack(pady=5)
        canonical_var = tk.StringVar()
        canonical_combo = ttk.Combobox(dialog, textvariable=canonical_var, width=47)
        canonical_combo['values'] = self.team_manager.get_team_members()
        canonical_combo.pack(pady=5)

        def do_add():
            alias = alias_var.get().strip()
            canonical = canonical_var.get().strip()

            if not alias or not canonical:
                messagebox.showwarning("Invalid", "Please enter both names")
                return

            if canonical not in self.team_manager.team_members:
                messagebox.showwarning("Invalid", f"{canonical} is not in the team roster.\nAdd them first!")
                return

            if self.team_manager.add_alias(alias, canonical):
                self.refresh_aliases()
                self.log(f"✓ Added alias: {alias} → {canonical}")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to add alias")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Add", command=do_add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        dialog.bind('<Return>', lambda e: do_add())

    def remove_alias(self):
        """Remove selected alias"""
        selection = self.alias_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an alias to remove")
            return

        item = self.alias_tree.item(selection[0])
        alias = item['values'][0]

        if messagebox.askyesno("Confirm", f"Remove alias '{alias}'?"):
            if self.team_manager.remove_alias(alias):
                self.refresh_aliases()
                self.log(f"✓ Removed alias: {alias}")

    # Project Management Methods

    def refresh_projects(self):
        """Refresh the project list from project_master.json"""
        try:
            from src.project_manager import ProjectManager

            # Clear existing items
            for item in self.project_tree.get_children():
                self.project_tree.delete(item)

            # Load projects
            pm = ProjectManager()
            projects = pm.get_projects()

            if not projects:
                self.log("No projects found in project_master.json")
                return

            # Add to tree
            for project in projects:
                code = project.get('code', '')
                name = project.get('name', '')
                aliases = project.get('aliases', {})

                # Format aliases for display
                code_aliases = ', '.join(aliases.get('codes', []))
                name_aliases = ', '.join(aliases.get('names', []))
                all_aliases = []
                if code_aliases:
                    all_aliases.append(f"Codes: {code_aliases}")
                if name_aliases:
                    all_aliases.append(f"Names: {name_aliases}")
                alias_display = ' | '.join(all_aliases) if all_aliases else 'None'

                self.project_tree.insert('', tk.END, values=(code, name, alias_display))

            self.log(f"Loaded {len(projects)} projects")

        except FileNotFoundError:
            self.log("⚠️  project_master.json not found - will be created when you add projects")
        except Exception as e:
            self.log(f"✗ Error loading projects: {str(e)}")

    def add_project(self):
        """Add a new project to the master list"""
        try:
            from src.project_manager import ProjectManager

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Add New Project")
            dialog.geometry("400x150")
            dialog.transient(self.root)
            dialog.grab_set()

            # Code input
            ttk.Label(dialog, text="Project Code:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
            code_entry = ttk.Entry(dialog, width=30)
            code_entry.grid(row=0, column=1, padx=10, pady=10)

            # Name input
            ttk.Label(dialog, text="Project Name:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
            name_entry = ttk.Entry(dialog, width=30)
            name_entry.grid(row=1, column=1, padx=10, pady=10)

            def save_project():
                code = code_entry.get().strip()
                name = name_entry.get().strip()

                if not code or not name:
                    messagebox.showerror("Error", "Both code and name are required")
                    return

                pm = ProjectManager()
                if pm.add_project(code, name):
                    self.log(f"✓ Added project: {code} - {name}")
                    self.refresh_projects()
                    dialog.destroy()
                else:
                    messagebox.showerror("Error", f"Project {code} already exists")

            # Buttons
            btn_frame = ttk.Frame(dialog)
            btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
            ttk.Button(btn_frame, text="Save", command=save_project).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

            code_entry.focus()

        except Exception as e:
            self.log(f"✗ Error adding project: {str(e)}")
            messagebox.showerror("Error", f"Failed to add project:\n{str(e)}")

    def edit_project(self):
        """Edit selected project"""
        try:
            selection = self.project_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a project to edit")
                return

            from src.project_manager import ProjectManager

            # Get selected project
            item = self.project_tree.item(selection[0])
            old_code, old_name, _ = item['values']

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Project")
            dialog.geometry("400x150")
            dialog.transient(self.root)
            dialog.grab_set()

            # Code (read-only)
            ttk.Label(dialog, text="Project Code:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
            ttk.Label(dialog, text=old_code, foreground="gray").grid(row=0, column=1, padx=10, pady=10, sticky=tk.W)

            # Name input
            ttk.Label(dialog, text="Project Name:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
            name_entry = ttk.Entry(dialog, width=30)
            name_entry.insert(0, old_name)
            name_entry.grid(row=1, column=1, padx=10, pady=10)

            def save_changes():
                new_name = name_entry.get().strip()

                if not new_name:
                    messagebox.showerror("Error", "Name is required")
                    return

                pm = ProjectManager()
                if pm.update_project(old_code, new_name):
                    self.log(f"✓ Updated project: {old_code} - {new_name}")
                    self.refresh_projects()
                    dialog.destroy()
                else:
                    messagebox.showerror("Error", f"Failed to update project {old_code}")

            # Buttons
            btn_frame = ttk.Frame(dialog)
            btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
            ttk.Button(btn_frame, text="Save", command=save_changes).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

            name_entry.focus()

        except Exception as e:
            self.log(f"✗ Error editing project: {str(e)}")
            messagebox.showerror("Error", f"Failed to edit project:\n{str(e)}")

    def delete_project(self):
        """Delete selected project"""
        try:
            selection = self.project_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a project to delete")
                return

            from src.project_manager import ProjectManager

            # Get selected project
            item = self.project_tree.item(selection[0])
            code, name, _ = item['values']

            # Confirm deletion
            if not messagebox.askyesno("Confirm Delete",
                                      f"Are you sure you want to delete:\n\n{code} - {name}"):
                return

            pm = ProjectManager()
            if pm.remove_project(code):
                self.log(f"✓ Deleted project: {code}")
                self.refresh_projects()
            else:
                messagebox.showerror("Error", f"Failed to delete project {code}")

        except Exception as e:
            self.log(f"✗ Error deleting project: {str(e)}")
            messagebox.showerror("Error", f"Failed to delete project:\n{str(e)}")

    def import_projects_from_db(self):
        """Import unique projects from DynamoDB to project_master.json"""
        try:
            from src.project_manager import ProjectManager

            self.log("📥 Importing projects from DynamoDB...")

            # Scan DynamoDB for unique projects
            response = table.scan(
                ProjectionExpression='ProjectCode, ProjectName, IsZeroHourTimesheet'
            )

            unique_projects = {}
            for item in response.get('Items', []):
                # Skip zero-hour timesheets (they don't have real projects)
                if item.get('IsZeroHourTimesheet'):
                    continue

                code = item.get('ProjectCode', '')
                name = item.get('ProjectName', '')
                if code and name:
                    unique_projects[code] = name

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = table.scan(
                    ProjectionExpression='ProjectCode, ProjectName, IsZeroHourTimesheet',
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                for item in response.get('Items', []):
                    # Skip zero-hour timesheets
                    if item.get('IsZeroHourTimesheet'):
                        continue

                    code = item.get('ProjectCode', '')
                    name = item.get('ProjectName', '')
                    if code and name:
                        unique_projects[code] = name

            if not unique_projects:
                messagebox.showinfo("Import", "No projects found in DynamoDB")
                return

            # Add to project master
            pm = ProjectManager()
            added_count = 0
            skipped_count = 0

            for code, name in unique_projects.items():
                if pm.add_project(code, name):
                    added_count += 1
                else:
                    skipped_count += 1

            self.log(f"✓ Import complete:")
            self.log(f"  Added: {added_count} new projects")
            self.log(f"  Skipped: {skipped_count} existing projects")
            self.log(f"  Total unique: {len(unique_projects)}")

            self.refresh_projects()

            messagebox.showinfo("Import Complete",
                              f"Imported {added_count} new projects\n"
                              f"Skipped {skipped_count} existing projects\n"
                              f"Total: {len(unique_projects)} unique projects in DB")

        except Exception as e:
            self.log(f"✗ Error importing projects: {str(e)}")
            messagebox.showerror("Import Error", f"Failed to import projects:\n{str(e)}")

    def find_duplicates(self):
        """Find duplicate names in the database"""
        try:
            self.log("Scanning database for duplicate names...")

            # Scan DynamoDB
            response = table.scan()
            items = response.get('Items', [])

            while 'LastEvaluatedKey' in response:
                response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                items.extend(response.get('Items', []))

            self.log(f"✓ Scanned {len(items)} records")

            # Find duplicates
            duplicates = self.team_manager.find_duplicates_in_database(items)

            # Display results
            self.dup_text.config(state='normal')
            self.dup_text.delete('1.0', tk.END)

            if not duplicates:
                self.dup_text.insert(tk.END, "✓ No duplicates found!\n\n")
                self.dup_text.insert(tk.END, "All names are unique or already normalized.")
            else:
                self.dup_text.insert(tk.END, f"Found {len(duplicates)} potential duplicates:\n\n")

                for canonical, variants in sorted(duplicates.items()):
                    self.dup_text.insert(tk.END, f"📋 {canonical}\n")
                    for variant in variants:
                        if variant != canonical:
                            self.dup_text.insert(tk.END, f"   ⚠️  {variant}\n")
                    self.dup_text.insert(tk.END, "\n")

                self.dup_text.insert(tk.END, "\n💡 Use 'Export Full Data' → Edit CSV → 'Import Corrections' to fix these.\n")
                self.dup_text.insert(tk.END, "Or add aliases in the 'Name Aliases' section below.")

            self.dup_text.config(state='disabled')
            self.log(f"✓ Duplicate scan complete: {len(duplicates)} potential duplicates")

        except Exception as e:
            self.log(f"✗ Error finding duplicates: {str(e)}")
            messagebox.showerror("Error", f"Failed to scan for duplicates:\n{str(e)}")

    def fix_duplicate(self):
        """Show instructions for fixing duplicates"""
        messagebox.showinfo(
            "Fix Duplicates",
            "To fix duplicate names:\n\n"
            "Method 1: Add Alias\n"
            "1. Click '➕ Add Alias' below\n"
            "2. Enter the incorrect OCR variant\n"
            "3. Select the correct canonical name\n"
            "4. Future OCR will auto-correct\n\n"
            "Method 2: Manual Correction\n"
            "1. Click '📥 Export Full Data'\n"
            "2. Open CSV in Excel/Numbers\n"
            "3. Find and replace incorrect names\n"
            "4. Save CSV\n"
            "5. Click '📤 Import Corrections'\n"
            "6. Database will be updated"
        )

    def load_clarity_months(self):
        """Load Clarity month definitions from JSON file."""
        try:
            with open('clarity_months.json', 'r') as f:
                data = json.load(f)
                return data.get('clarity_months', [])
        except FileNotFoundError:
            self.log("⚠️ clarity_months.json not found")
            return []
        except json.JSONDecodeError:
            self.log("⚠️ Invalid JSON in clarity_months.json")
            return []

    def get_current_clarity_month(self):
        """Get the Clarity month that contains today's date."""
        from datetime import date
        today = date.today()

        for cm in self.clarity_months:
            start = datetime.strptime(cm['start_date'], '%Y-%m-%d').date()
            end = datetime.strptime(cm['end_date'], '%Y-%m-%d').date()

            if start <= today <= end:
                return cm

        return None

    def export_clarity_summary(self):
        """Export summary report for selected Clarity month."""
        selected_display = self.clarity_month_var.get()
        if not selected_display:
            messagebox.showwarning("No Selection", "Please select a Clarity month first.")
            return

        # Find the selected Clarity month
        selected_month = None
        for cm in self.clarity_months:
            if cm['display'] == selected_display:
                selected_month = cm
                break

        if not selected_month:
            messagebox.showerror("Error", "Invalid Clarity month selection.")
            return

        # Parse dates
        try:
            start_date = datetime.strptime(selected_month['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(selected_month['end_date'], '%Y-%m-%d')
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid date format: {e}")
            return

        # Use existing export_period_summary logic in a thread
        thread = threading.Thread(
            target=self._export_period_summary_thread,
            args=(start_date, end_date)
        )
        thread.daemon = True
        thread.start()

    def export_clarity_detailed(self):
        """Export detailed report for selected Clarity month."""
        selected_display = self.clarity_month_var.get()
        if not selected_display:
            messagebox.showwarning("No Selection", "Please select a Clarity month first.")
            return

        # Find the selected Clarity month
        selected_month = None
        for cm in self.clarity_months:
            if cm['display'] == selected_display:
                selected_month = cm
                break

        if not selected_month:
            messagebox.showerror("Error", "Invalid Clarity month selection.")
            return

        # Parse dates
        try:
            start_date = datetime.strptime(selected_month['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(selected_month['end_date'], '%Y-%m-%d')
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid date format: {e}")
            return

        # Use existing export_period_detailed logic in a thread
        thread = threading.Thread(
            target=self._export_period_detailed_thread,
            args=(start_date, end_date)
        )
        thread.daemon = True
        thread.start()

    def check_clarity_coverage(self):
        """Generate and display coverage report for selected Clarity month."""
        selected_display = self.clarity_month_var.get()
        if not selected_display:
            messagebox.showwarning("No Selection", "Please select a Clarity month first.")
            return

        # Find the selected Clarity month
        selected_month = None
        for cm in self.clarity_months:
            if cm['display'] == selected_display:
                selected_month = cm
                break

        if not selected_month:
            messagebox.showerror("Error", "Invalid Clarity month selection.")
            return

        # Extract month key (e.g., "Sep-25" from "Sep-25 (Aug 18 - Sep 14)")
        month_key = selected_month['month']

        # Run in thread to avoid blocking UI
        thread = threading.Thread(
            target=self._check_coverage_thread,
            args=(month_key,)
        )
        thread.daemon = True
        thread.start()

    def _check_coverage_thread(self, clarity_month):
        """Thread worker to generate coverage report."""
        try:
            self.log(f"🔍 Generating coverage report for {clarity_month}...")
            self.progress.start()

            # Import coverage checker
            from src.timesheet_coverage import generate_coverage_report, format_coverage_report_text, format_coverage_report_csv

            # Generate report
            report = generate_coverage_report(clarity_month)

            # Format as text
            text_report = format_coverage_report_text(report)

            # Display in popup window
            self.root.after(0, self._show_coverage_report, text_report, report, clarity_month)

            self.progress.stop()
            self.log(f"✅ Coverage report generated successfully")

        except Exception as e:
            self.progress.stop()
            error_msg = f"Failed to generate coverage report: {str(e)}"
            self.log(f"❌ {error_msg}")
            self.root.after(0, messagebox.showerror, "Coverage Check Failed", error_msg)

    def _show_coverage_report(self, text_report, report_data, clarity_month):
        """Display coverage report in a popup window."""
        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title(f"Coverage Report - {clarity_month}")
        popup.geometry("1000x700")

        # Main frame
        main_frame = ttk.Frame(popup, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        popup.columnconfigure(0, weight=1)
        popup.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Statistics summary at top
        stats = report_data['statistics']
        summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding="10")
        summary_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        summary_text = f"Period: {report_data['period']['start']} to {report_data['period']['end']}\n"
        summary_text += f"Weeks: {report_data['week_count']} | Team: {report_data['team_count']} members\n"
        summary_text += f"Expected: {stats['total_expected']} | "
        summary_text += f"Submitted: {stats['total_submitted']} ({stats['coverage_percentage']:.1f}%) | "
        summary_text += f"Missing: {stats['total_missing']}"

        summary_label = ttk.Label(summary_frame, text=summary_text, font=('Courier', 10))
        summary_label.pack()

        # Report text area
        text_frame = ttk.Frame(main_frame)
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        report_text = scrolledtext.ScrolledText(text_frame, wrap=tk.NONE, font=('Courier', 10))
        report_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        report_text.insert('1.0', text_report)
        report_text.config(state='disabled')

        # Buttons at bottom
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        def export_csv():
            """Export report as CSV."""
            from src.timesheet_coverage import format_coverage_report_csv
            csv_data = format_coverage_report_csv(report_data)

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"coverage_{clarity_month}.csv"
            )

            if filename:
                try:
                    with open(filename, 'w') as f:
                        f.write(csv_data)
                    messagebox.showinfo("Success", f"Report exported to:\n{filename}")
                except Exception as e:
                    messagebox.showerror("Export Failed", f"Failed to export CSV: {e}")

        ttk.Button(button_frame, text="📊 Export CSV", command=export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Close", command=popup.destroy).pack(side=tk.RIGHT, padx=5)

    def _perform_ocr_only(self, image_key):
        """Perform OCR on image without saving to database."""
        print(f"\n{'='*80}")
        print(f"[DEBUG OCR V2] _perform_ocr_only() called for: {image_key}")
        print(f"{'='*80}\n")
        try:
            import base64
            from src.prompt import get_ocr_prompt
            from src.parsing import parse_timesheet_json

            # Download image from S3
            response = s3_client.get_object(Bucket=INPUT_BUCKET, Key=image_key)
            image_bytes = response['Body'].read()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            # Determine media type
            if image_key.lower().endswith('.png'):
                media_type = 'image/png'
            elif image_key.lower().endswith(('.jpg', '.jpeg')):
                media_type = 'image/jpeg'
            else:
                media_type = 'image/png'

            # Call Bedrock for OCR
            bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')
            prompt = get_ocr_prompt()

            # Log prompt to verify it's correct
            print(f"[DEBUG OCR] Checking prompt for zero-hour instructions...")
            if "PROJECT TIME: 0%" in prompt:
                print(f"[DEBUG OCR] ✓ Prompt contains 'PROJECT TIME: 0%' detection")
            else:
                print(f"[DEBUG OCR] ✗ WARNING: Prompt MISSING 'PROJECT TIME: 0%' detection!")

            if "is_zero_hour_timesheet" in prompt:
                print(f"[DEBUG OCR] ✓ Prompt mentions is_zero_hour_timesheet field")
            else:
                print(f"[DEBUG OCR] ✗ WARNING: Prompt does NOT mention is_zero_hour_timesheet!")

            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            }

            # Call Bedrock with exponential backoff for throttling
            max_retries = 5
            base_delay = 2
            max_delay = 60

            for attempt in range(max_retries):
                try:
                    # Use Claude 3.5 Sonnet v2 for best OCR accuracy
                    response = bedrock_runtime.invoke_model(
                        modelId='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
                        body=json.dumps(request_body),
                        contentType='application/json',
                        accept='application/json'
                    )

                    if attempt > 0:
                        print(f"[DEBUG OCR] ✓ Succeeded after {attempt} retries")

                    break  # Success, exit retry loop

                except Exception as e:
                    error_str = str(e)
                    if 'ThrottlingException' in error_str or 'Too many requests' in error_str:
                        if attempt < max_retries - 1:
                            delay = min(base_delay * (2 ** attempt), max_delay)
                            print(f"[DEBUG OCR] ⚠️  Throttled (attempt {attempt + 1}/{max_retries}), waiting {delay}s...")
                            time.sleep(delay)
                            continue
                        else:
                            print(f"[DEBUG OCR] ❌ Failed after {max_retries} retries due to throttling")
                            raise
                    else:
                        # Non-throttling error, don't retry
                        raise

            response_body = json.loads(response['body'].read())
            extracted_text = response_body['content'][0]['text']

            # Log FULL raw response
            print("=" * 80)
            print(f"[DEBUG OCR] ===== PROCESSING IMAGE: {image_key} =====")
            print("=" * 80)
            print(f"[DEBUG OCR] FULL RAW CLAUDE RESPONSE:")
            print("-" * 80)
            print(extracted_text)
            print("-" * 80)

            # Save to file for inspection
            debug_file = f"/tmp/ocr_debug_{image_key.replace('/', '_').replace('.png', '')}.txt"
            with open(debug_file, 'w') as f:
                f.write(f"IMAGE: {image_key}\n")
                f.write("=" * 80 + "\n")
                f.write("FULL CLAUDE RESPONSE:\n")
                f.write("=" * 80 + "\n")
                f.write(extracted_text)
                f.write("\n\n")
            print(f"[DEBUG OCR] Full response saved to: {debug_file}")

            # Parse JSON
            timesheet_data = parse_timesheet_json(extracted_text)

            # Log parsed data in detail
            print(f"[DEBUG OCR] PARSED DATA:")
            print(f"[DEBUG OCR]   Keys: {list(timesheet_data.keys())}")
            print(f"[DEBUG OCR]   resource_name: {timesheet_data.get('resource_name')}")
            print(f"[DEBUG OCR]   date_range: {timesheet_data.get('date_range')}")
            print(f"[DEBUG OCR]   is_zero_hour_timesheet: {timesheet_data.get('is_zero_hour_timesheet')}")
            print(f"[DEBUG OCR]   zero_hour_reason: {timesheet_data.get('zero_hour_reason')}")
            print(f"[DEBUG OCR]   daily_totals: {timesheet_data.get('daily_totals')}")
            print(f"[DEBUG OCR]   weekly_total: {timesheet_data.get('weekly_total')}")
            print(f"[DEBUG OCR]   projects count: {len(timesheet_data.get('projects', []))}")
            if timesheet_data.get('projects'):
                for i, p in enumerate(timesheet_data.get('projects', [])):
                    print(f"[DEBUG OCR]     Project {i+1}: {p.get('project_name')} ({p.get('project_code')})")
            print("=" * 80)

            return timesheet_data

        except Exception as e:
            return {'error': str(e)}

    def _save_ocr_to_database(self, image_key, ocr_data):
        """Save OCR data to DynamoDB."""
        try:
            from src.dynamodb_handler import store_timesheet_entries

            result = store_timesheet_entries(
                timesheet_data=ocr_data,
                image_key=image_key,
                processing_time=0,
                model_id='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
                input_tokens=0,
                output_tokens=0,
                cost_estimate=0.0,
                table_name=DYNAMODB_TABLE
            )

            return result

        except Exception as e:
            import traceback
            print(f"[DEBUG UI] EXCEPTION during save:")
            print(f"[DEBUG UI] Exception type: {type(e).__name__}")
            print(f"[DEBUG UI] Exception message: {str(e)}")
            print(f"[DEBUG UI] Full traceback:")
            traceback.print_exc()
            self.log(f"✗ Error saving to database: {str(e)}")
            return {'error': str(e)}

    def _show_approval_dialog_blocking(self, image_key, ocr_data):
        """Show approval dialog and return user's choice."""
        try:
            print(f"[DEBUG] _show_approval_dialog_blocking: START for {image_key}")

            # Download image from S3
            print(f"[DEBUG] _show_approval_dialog_blocking: Downloading image from S3...")
            response = s3_client.get_object(Bucket=INPUT_BUCKET, Key=image_key)
            image_bytes = response['Body'].read()
            print(f"[DEBUG] _show_approval_dialog_blocking: Downloaded {len(image_bytes)} bytes")

            # Create approval dialog
            print(f"[DEBUG] _show_approval_dialog_blocking: Creating Toplevel dialog...")
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Review OCR Result - {image_key}")
            dialog.geometry("1000x800")
            dialog.transient(self.root)
            dialog.grab_set()
            print(f"[DEBUG] _show_approval_dialog_blocking: Dialog created")

            # Main container
            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Image display (top - 75% of space)
            top_frame = ttk.Frame(main_frame)
            top_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            ttk.Label(top_frame, text="📷 Timesheet Image:", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(0, 5))

            # Load and display image
            from PIL import Image, ImageTk
            img = Image.open(io.BytesIO(image_bytes))

            # Resize to fit display - larger now since it has more space
            max_width = 950
            max_height = 600
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            img_label = ttk.Label(top_frame, image=photo)
            img_label.image = photo  # Keep reference
            img_label.pack(expand=True)

            # OCR data display (bottom - 25% of space)
            bottom_frame = ttk.Frame(main_frame, height=200)
            bottom_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, pady=(10, 0))
            bottom_frame.pack_propagate(False)  # Don't shrink

            ttk.Label(bottom_frame, text="📋 Extracted OCR Data:", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(0, 5))

            # Scrollable text area for OCR data
            text_frame = ttk.Frame(bottom_frame)
            text_frame.pack(fill=tk.BOTH, expand=True)

            scrollbar = ttk.Scrollbar(text_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            text_widget = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set,
                                 font=('Courier', 9))
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=text_widget.yview)

            # Format OCR result nicely
            ocr_text = self._format_ocr_data(ocr_data)
            text_widget.insert('1.0', ocr_text)
            text_widget.config(state=tk.DISABLED)

            # Button frame at bottom
            button_frame = ttk.Frame(dialog, padding="10")
            button_frame.pack(fill=tk.X, side=tk.BOTTOM)

            # Result variable
            result = {'action': 'approve'}

            def on_approve():
                result['action'] = 'approve'
                dialog.destroy()

            def on_reject():
                result['action'] = 'reject'
                dialog.destroy()

            def on_auto():
                result['action'] = 'auto'
                dialog.destroy()

            def on_stop():
                result['action'] = 'stop'
                dialog.destroy()

            def on_delete():
                # Confirm deletion
                if messagebox.askyesno("Delete Image",
                                      f"Delete this image from S3?\n\n{image_key}\n\n"
                                      f"This will permanently remove the image.\n"
                                      f"The OCR data will NOT be saved.",
                                      parent=dialog):
                    try:
                        # Delete from S3
                        s3_client.delete_object(Bucket=INPUT_BUCKET, Key=image_key)
                        self.log(f"🗑️ Deleted low-quality image from S3: {image_key}")
                        result['action'] = 'delete'
                        dialog.destroy()
                    except Exception as e:
                        messagebox.showerror("Delete Error",
                                           f"Failed to delete image:\n{str(e)}",
                                           parent=dialog)

            # Buttons
            ttk.Button(button_frame, text="✓ Approve & Add to Database", command=on_approve,
                      width=25).pack(side=tk.LEFT, padx=5)

            ttk.Button(button_frame, text="✗ Reject (Don't Add)", command=on_reject,
                      width=20).pack(side=tk.LEFT, padx=5)

            ttk.Button(button_frame, text="🗑️ Delete Image from S3", command=on_delete,
                      width=22).pack(side=tk.LEFT, padx=5)

            ttk.Button(button_frame, text="⚡ Auto Mode (Approve Rest)", command=on_auto,
                      width=25).pack(side=tk.LEFT, padx=5)

            ttk.Button(button_frame, text="⏹ Stop Scan", command=on_stop,
                      width=15).pack(side=tk.LEFT, padx=5)

            # Wait for dialog to close
            print(f"[DEBUG] _show_approval_dialog_blocking: Calling wait_window()...")
            dialog.wait_window()
            print(f"[DEBUG] _show_approval_dialog_blocking: Dialog closed, returning: {result['action']}")

            return result['action']

        except Exception as e:
            self.log(f"✗ Error showing approval dialog: {str(e)}")
            print(f"[DEBUG] _show_approval_dialog_blocking: EXCEPTION: {str(e)}")
            import traceback
            traceback.print_exc()
            return 'approve'  # Default to approve on error

    def _format_ocr_data(self, ocr_data):
        """Format OCR data for display in approval dialog."""
        from src.utils import validate_timesheet_totals

        lines = []
        lines.append("=" * 60)
        lines.append(f"Resource Name: {ocr_data.get('resource_name', 'Unknown')}")
        lines.append(f"Date Range: {ocr_data.get('date_range', 'Unknown')}")
        lines.append("=" * 60)
        lines.append("")

        # Check for zero-hour timesheet first
        is_zero_hour = ocr_data.get('is_zero_hour_timesheet', False)

        if is_zero_hour:
            lines.append("⚠️  ZERO-HOUR TIMESHEET DETECTED")
            lines.append(f"   Reason: {ocr_data.get('zero_hour_reason', 'Not specified')}")
            lines.append("   This timesheet has NO project hours logged.")
            lines.append("")
            lines.append("✅ VALIDATION: Zero-hour timesheet (no validation needed)")
            lines.append("")
            lines.append("=" * 60)
            lines.append("")
            total_entries = 1
            lines.append("Will create 1 database entry (zero-hour marker)")
            lines.append("=" * 60)
            return "\n".join(lines)

        # Validate totals for regular timesheets
        validation = validate_timesheet_totals(ocr_data)

        # Show validation results prominently
        lines.append("VALIDATION RESULTS:")
        lines.append("")

        if validation['valid']:
            lines.append("✅ ALL TOTALS MATCH - Data is consistent!")
        else:
            lines.append("❌ VALIDATION FAILED - Totals do not match!")
            for error in validation['errors']:
                lines.append(f"   ⚠️  {error}")

        lines.append("")
        lines.append("Daily Totals Validation:")
        day_abbrev = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for i, day_val in enumerate(validation['daily_validation']):
            status = "✅" if day_val['match'] else "❌"
            lines.append(f"  {status} {day_abbrev[i]}: Expected {day_val['expected']:.2f}h, "
                        f"Got {day_val['actual']:.2f}h")

        lines.append("")
        weekly_val = validation['weekly_validation']
        status = "✅" if weekly_val['match'] else "❌"
        lines.append(f"{status} Weekly Total: Expected {weekly_val['expected']:.2f}h, "
                    f"Got {weekly_val['actual']:.2f}h")

        lines.append("")
        lines.append("=" * 60)
        lines.append("")

        # Show projects
        projects = ocr_data.get('projects', [])
        lines.append(f"PROJECTS ({len(projects)} found):")
        lines.append("")

        for idx, project in enumerate(projects, 1):
            lines.append(f"{idx}. {project.get('project_name', 'Unknown')}")
            lines.append(f"   Project Code: {project.get('project_code', 'N/A')}")

            # Show hours by day
            hours_by_day = project.get('hours_by_day', [])
            total_hours = sum(float(day.get('hours', 0)) for day in hours_by_day)

            lines.append(f"   Hours:")
            for day in hours_by_day:
                day_name = day.get('day', 'Unknown')
                hours = day.get('hours', '0')
                if float(hours) > 0:
                    lines.append(f"     {day_name}: {hours}")

            lines.append(f"   Total Hours: {total_hours}")
            lines.append("")

        # Check for zero-hour timesheet
        if ocr_data.get('is_zero_hour_timesheet'):
            lines.append("⚠️  ZERO-HOUR TIMESHEET")
            lines.append(f"   Reason: {ocr_data.get('zero_hour_reason', 'N/A')}")
            lines.append("")

        lines.append("=" * 60)
        total_entries = len(projects) * 7  # 7 days per project
        lines.append(f"Will create {total_entries} database entries")

        if not validation['valid']:
            lines.append("")
            lines.append("⚠️  WARNING: Validation failed. Review carefully before approving!")

        lines.append("=" * 60)

        return "\n".join(lines)

    def show_ocr_approval_dialog(self, image_key, ocr_result):
        """
        Show dialog with image and OCR results for user approval.

        Returns:
            'approve' - Add to database
            'reject' - Don't add to database (and rollback if already added)
            'auto' - Switch to automatic mode (no more approvals)
            'stop' - Stop the scan
        """
        # Download image from S3
        try:
            response = s3_client.get_object(Bucket=INPUT_BUCKET, Key=image_key)
            image_bytes = response['Body'].read()

            # Create approval dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Review OCR Result - {image_key}")
            dialog.geometry("1000x800")
            dialog.transient(self.root)
            dialog.grab_set()

            # Result variable
            result = {'action': 'approve'}

            # Main container with scrollbar
            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Image display (left side)
            left_frame = ttk.Frame(main_frame)
            left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

            ttk.Label(left_frame, text="📷 Original Image:", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(0, 5))

            # Load and display image
            from PIL import Image, ImageTk
            img = Image.open(io.BytesIO(image_bytes))

            # Resize to fit display
            max_width = 480
            max_height = 600
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            img_label = ttk.Label(left_frame, image=photo)
            img_label.image = photo  # Keep reference
            img_label.pack()

            # OCR data display (right side)
            right_frame = ttk.Frame(main_frame)
            right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            ttk.Label(right_frame, text="📋 Extracted Data:", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(0, 5))

            # Scrollable text area for OCR data
            text_frame = ttk.Frame(right_frame)
            text_frame.pack(fill=tk.BOTH, expand=True)

            scrollbar = ttk.Scrollbar(text_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            text_widget = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set,
                                 font=('Courier', 10), height=30)
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=text_widget.yview)

            # Format OCR result nicely
            ocr_text = self._format_ocr_result(ocr_result)
            text_widget.insert('1.0', ocr_text)
            text_widget.config(state=tk.DISABLED)

            # Button frame at bottom
            button_frame = ttk.Frame(dialog, padding="10")
            button_frame.pack(fill=tk.X, side=tk.BOTTOM)

            def on_approve():
                result['action'] = 'approve'
                dialog.destroy()

            def on_reject():
                result['action'] = 'reject'
                dialog.destroy()

            def on_auto():
                result['action'] = 'auto'
                dialog.destroy()

            def on_stop():
                result['action'] = 'stop'
                dialog.destroy()

            # Buttons
            ttk.Button(button_frame, text="✓ Approve & Continue", command=on_approve,
                      style='success.TButton', width=20).pack(side=tk.LEFT, padx=5)

            ttk.Button(button_frame, text="✗ Reject", command=on_reject,
                      style='danger.TButton', width=15).pack(side=tk.LEFT, padx=5)

            ttk.Button(button_frame, text="⚡ Auto Mode (No More Approvals)", command=on_auto,
                      width=30).pack(side=tk.LEFT, padx=5)

            ttk.Button(button_frame, text="⏹ Stop Scan", command=on_stop,
                      width=15).pack(side=tk.LEFT, padx=5)

            # Wait for dialog to close
            dialog.wait_window()

            return result['action']

        except Exception as e:
            self.log(f"✗ Error showing approval dialog: {str(e)}")
            # Default to approve on error
            return 'approve'

    def _format_ocr_result(self, ocr_result):
        """Format OCR result data for display."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"Resource: {ocr_result.get('resource_name', 'Unknown')}")
        lines.append(f"Date Range: {ocr_result.get('date_range', 'Unknown')}")
        lines.append(f"Entries Stored: {ocr_result.get('entries_stored', 0)}")
        lines.append(f"Projects Count: {ocr_result.get('projects_count', 0)}")
        lines.append("=" * 60)
        lines.append("")

        # Get detailed project breakdown from Lambda logs or parse from result
        lines.append("PROJECTS:")
        lines.append("")

        # If we have project details, show them
        # Note: We'd need to modify Lambda to return this, for now show summary
        lines.append(f"  Total entries: {ocr_result.get('entries_stored', 0)}")
        lines.append(f"  Total projects: {ocr_result.get('projects_count', 0)}")
        lines.append("")
        lines.append("(Project details are stored in database)")
        lines.append("")

        lines.append("=" * 60)
        lines.append("VALIDATION SUMMARY:")
        lines.append("")

        dup_info = ocr_result.get('duplicate_info', {})
        if dup_info.get('was_duplicate'):
            lines.append(f"  ⚠️  Overwrote {dup_info.get('overwritten_entries', 0)} existing entries")
        else:
            lines.append(f"  ✓ No duplicates - new entries created")

        return "\n".join(lines)

    def _rollback_ocr_entries(self, resource_name, date_range):
        """Rollback (delete) OCR entries that were just added."""
        try:
            self.log(f"  ⏪ Rolling back entries for {resource_name}...")

            # Parse date range to get dates
            from src.utils import parse_date_range, generate_week_dates

            start_date, end_date = parse_date_range(date_range)
            week_dates = generate_week_dates(start_date, end_date)

            # Delete entries for this resource and date range
            deleted_count = 0
            with table.batch_writer() as batch:
                for date_obj in week_dates:
                    date_str = date_obj.strftime('%Y-%m-%d')

                    # Query for this resource and date
                    response = table.query(
                        KeyConditionExpression='ResourceName = :rn AND begins_with(DateProjectCode, :date)',
                        ExpressionAttributeValues={
                            ':rn': resource_name,
                            ':date': date_str
                        }
                    )

                    for item in response.get('Items', []):
                        batch.delete_item(
                            Key={
                                'ResourceName': item['ResourceName'],
                                'DateProjectCode': item['DateProjectCode']
                            }
                        )
                        deleted_count += 1

            self.log(f"  ⏪ Rolled back {deleted_count} entries")

        except Exception as e:
            self.log(f"  ✗ Error rolling back: {str(e)}")

    def list_bucket_images(self):
        """List all images in the S3 bucket."""
        self.log("📋 Listing images in S3 bucket...")
        thread = threading.Thread(target=self._list_bucket_thread)
        thread.daemon = True
        thread.start()

    def _list_bucket_thread(self):
        """Background thread for listing S3 images."""
        try:
            self.log(f"🪣 Scanning bucket: {INPUT_BUCKET}")
            paginator = s3_client.get_paginator('list_objects_v2')
            images = []

            for page in paginator.paginate(Bucket=INPUT_BUCKET):
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    key = obj['Key']
                    if key.lower().endswith(('.png', '.jpg', '.jpeg')) and not key.startswith('quicksight-data/'):
                        size_mb = obj['Size'] / (1024 * 1024)
                        modified = obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
                        images.append(f"{key} ({size_mb:.2f} MB, modified: {modified})")

            self.log(f"✅ Found {len(images)} images in S3:")
            for img in sorted(images)[:50]:  # Show first 50
                self.log(f"   • {img}")
            if len(images) > 50:
                self.log(f"   ... and {len(images) - 50} more")

        except Exception as e:
            self.log(f"❌ Error listing bucket: {str(e)}")

    def flush_database(self):
        """Delete all entries from DynamoDB (with confirmation)."""
        confirm = messagebox.askyesno(
            "⚠️ DANGER: Flush Database",
            "This will DELETE ALL ENTRIES from the DynamoDB table!\n\n"
            "Are you absolutely sure you want to do this?\n\n"
            "This cannot be undone!",
            icon='warning'
        )

        if not confirm:
            self.log("❌ Database flush cancelled")
            return

        # Double confirmation
        confirm2 = messagebox.askyesno(
            "⚠️ FINAL WARNING",
            f"You are about to delete ALL data from:\n\n"
            f"   Table: {DYNAMODB_TABLE}\n\n"
            "Type YES to confirm:",
            icon='warning'
        )

        if not confirm2:
            self.log("❌ Database flush cancelled")
            return

        self.log("🗑️ Starting database flush...")
        thread = threading.Thread(target=self._flush_database_thread)
        thread.daemon = True
        thread.start()

    def _flush_database_thread(self):
        """Background thread for flushing DynamoDB."""
        try:
            deleted_count = 0
            self.log("📊 Scanning database for entries...")

            while True:
                response = table.scan()
                items = response.get('Items', [])

                if not items:
                    break

                self.log(f"🗑️ Deleting batch of {len(items)} entries...")
                with table.batch_writer() as batch:
                    for item in items:
                        batch.delete_item(
                            Key={
                                'ResourceName': item['ResourceName'],
                                'DateProjectCode': item['DateProjectCode']
                            }
                        )
                        deleted_count += 1

                if 'LastEvaluatedKey' not in response:
                    break

            self.log(f"✅ Database flush complete! Deleted {deleted_count} entries")
            messagebox.showinfo("Success", f"Deleted {deleted_count} entries from database")

        except Exception as e:
            self.log(f"❌ Error flushing database: {str(e)}")
            messagebox.showerror("Error", f"Failed to flush database: {str(e)}")


def main():
    # Check AWS credentials
    try:
        sts = boto3.client('sts')
        sts.get_caller_identity()
    except Exception as e:
        messagebox.showerror("AWS Error",
                           f"AWS credentials not configured or expired.\n\n"
                           f"Run: aws sso login\n\n"
                           f"Error: {str(e)}")
        return

    # Create and run app
    root = tk.Tk()
    app = TimesheetOCRApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
