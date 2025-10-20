#!/usr/bin/env python3
"""
Timesheet OCR - Desktop UI for Mac
Upload timesheets and view data in DynamoDB
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import boto3
import json
import os
import csv
from pathlib import Path
from datetime import datetime
import threading
from decimal import Decimal
from collections import defaultdict

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
        self.root.title("Timesheet OCR - DynamoDB Edition")
        self.root.geometry("1000x750")
        self.root.resizable(True, True)

        # Variables
        self.selected_files = []
        self.processing = False

        # Setup UI
        self.setup_ui()

    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        # Only the notebook (row 4) should expand vertically
        main_frame.rowconfigure(4, weight=1)

        # Title
        title = ttk.Label(main_frame, text="📊 Timesheet OCR Processor",
                         font=('Helvetica', 18, 'bold'))
        title.grid(row=0, column=0, pady=10)

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
        process_frame = ttk.Frame(main_frame, width=800, height=50)
        process_frame.grid(row=2, column=0, pady=15, sticky=(tk.W, tk.E))
        process_frame.grid_propagate(False)  # Maintain fixed height

        # Configure columns to expand evenly
        process_frame.columnconfigure(0, weight=1, minsize=180)
        process_frame.columnconfigure(1, weight=1, minsize=150)
        process_frame.columnconfigure(2, weight=1, minsize=120)
        process_frame.columnconfigure(3, weight=1, minsize=180)

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

        self.report_btn = ttk.Button(process_frame, text="📥 Download Report",
                                     command=self.download_report)
        self.report_btn.grid(row=0, column=3, padx=8, sticky=(tk.W, tk.E))

        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)

        # Notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        # Logs tab
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="📋 Logs")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15,
                                                  wrap=tk.WORD, state='disabled')
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Data view tab
        data_frame = ttk.Frame(notebook)
        notebook.add(data_frame, text="📊 Database View")
        data_frame.columnconfigure(0, weight=1)
        data_frame.rowconfigure(0, weight=1)

        # Create Treeview for data
        columns = ('Resource', 'Date', 'Project', 'Code', 'Hours')
        self.tree = ttk.Treeview(data_frame, columns=columns, show='headings', height=15)

        # Define headings
        self.tree.heading('Resource', text='Resource Name')
        self.tree.heading('Date', text='Date')
        self.tree.heading('Project', text='Project Name')
        self.tree.heading('Code', text='Project Code')
        self.tree.heading('Hours', text='Hours')

        # Define column widths
        self.tree.column('Resource', width=150)
        self.tree.column('Date', width=100)
        self.tree.column('Project', width=300)
        self.tree.column('Code', width=100)
        self.tree.column('Hours', width=80)

        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Add scrollbars to treeview
        tree_scroll_y = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scroll_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.tree.configure(yscrollcommand=tree_scroll_y.set)

        tree_scroll_x = ttk.Scrollbar(data_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        tree_scroll_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.tree.configure(xscrollcommand=tree_scroll_x.set)

        # Info footer
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(row=5, column=0, pady=10)

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

                self.tree.insert('', tk.END, values=(resource, date, project, code, hours))

            self.log(f"✓ Loaded {len(items)} entries from DynamoDB")

            # Show summary
            unique_resources = len(set(item.get('ResourceName', '') for item in items))
            total_hours = sum(float(item.get('Hours', 0)) for item in items)
            self.log(f"Summary: {unique_resources} resources, {total_hours:.1f} total hours")

        except Exception as e:
            self.log(f"✗ Error loading data: {str(e)}")
            messagebox.showerror("Error", f"Failed to load data from DynamoDB:\n{str(e)}")

    def download_report(self):
        """Generate and download a summary report grouped by resource and project."""
        self.log("Generating timesheet report...")
        thread = threading.Thread(target=self._download_report_thread)
        thread.daemon = True
        thread.start()

    def _download_report_thread(self):
        """Background thread for generating report."""
        try:
            # Scan DynamoDB table
            self.log("Fetching data from DynamoDB...")
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

            # Group data by Resource Name and Project
            # Structure: {ResourceName: {ProjectCode: {project_name, total_hours}}}
            report_data = defaultdict(lambda: defaultdict(lambda: {'project_name': '', 'total_hours': 0.0}))

            for item in items:
                resource_name = item.get('ResourceNameDisplay', item.get('ResourceName', 'Unknown'))
                project_code = item.get('ProjectCode', 'N/A')
                project_name = item.get('ProjectName', 'N/A')
                hours = float(item.get('Hours', 0))

                # Store project name and sum hours
                report_data[resource_name][project_code]['project_name'] = project_name
                report_data[resource_name][project_code]['total_hours'] += hours

            # Create CSV data
            csv_rows = []
            csv_rows.append(['Resource Name', 'Project Code', 'Project Name', 'Total Hours'])

            # Sort by resource name, then by project code
            for resource_name in sorted(report_data.keys()):
                projects = report_data[resource_name]
                for project_code in sorted(projects.keys()):
                    project_info = projects[project_code]
                    csv_rows.append([
                        resource_name,
                        project_code,
                        project_info['project_name'],
                        f"{project_info['total_hours']:.2f}"
                    ])

            self.log(f"✓ Generated report with {len(csv_rows)-1} entries")

            # Ask user where to save
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"timesheet_report_{timestamp}.csv"

            save_path = filedialog.asksaveasfilename(
                title="Save Report As",
                defaultextension=".csv",
                initialfile=default_filename,
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not save_path:
                self.log("Report download cancelled")
                return

            # Write CSV file
            with open(save_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(csv_rows)

            self.log(f"✓ Report saved to: {save_path}")

            # Show success message and open folder
            result = messagebox.showinfo(
                "Report Downloaded",
                f"Timesheet report saved successfully!\n\n"
                f"File: {os.path.basename(save_path)}\n"
                f"Location: {os.path.dirname(save_path)}\n\n"
                f"Entries: {len(csv_rows)-1}"
            )

            # Open the folder containing the file
            folder_path = os.path.dirname(save_path)
            os.system(f'open "{folder_path}"')

        except Exception as e:
            self.log(f"✗ Error generating report: {str(e)}")
            messagebox.showerror("Error", f"Failed to generate report:\n{str(e)}")


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
