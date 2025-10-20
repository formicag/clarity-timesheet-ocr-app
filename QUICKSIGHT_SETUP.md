# QuickSight Dashboard Setup Guide

This guide will help you set up an Amazon QuickSight dashboard to visualize your timesheet data from DynamoDB.

## Prerequisites

- AWS Account with QuickSight enabled
- DynamoDB table `TimesheetOCR-dev` with timesheet data
- Processed at least a few timesheets

## Step 1: Enable QuickSight

1. Go to [QuickSight Console](https://quicksight.aws.amazon.com/)
2. If not already set up, click "Sign up for QuickSight"
3. Choose **Enterprise Edition** (recommended) or **Standard Edition**
4. Select region: **us-east-1** (same as your DynamoDB table)
5. Give QuickSight a name (e.g., "TimesheetOCR-Analytics")
6. Enter your email address
7. Click **Finish**

**Cost**: Enterprise Edition ~$18/month for first user, Standard ~$9/month

## Step 2: Grant QuickSight Access to DynamoDB

1. In QuickSight Console, click your user icon (top right) → **Manage QuickSight**
2. Click **Security & permissions** (left sidebar)
3. Under **QuickSight access to AWS services**, click **Add or remove**
4. Check **Amazon DynamoDB**
5. Click **Choose specific tables**
6. Select **TimesheetOCR-dev**
7. Click **Finish**

## Step 3: Create a Data Source

1. In QuickSight Console, click **Datasets** (left sidebar)
2. Click **New dataset**
3. Choose **DynamoDB**
4. Connection settings:
   - **Data source name**: `TimesheetOCR`
   - **Region**: `us-east-1`
   - **Table**: `TimesheetOCR-dev`
5. Click **Create data source**
6. Click **Visualize** to open in analysis

## Step 4: Prepare the Data

QuickSight will import your DynamoDB data. You may want to:

1. **Edit dataset** to configure:
   - Change `Hours` field type to **Decimal** (if not already)
   - Change `Date` field type to **Date** (format: YYYY-MM-DD)
   - Add calculated fields if needed

2. **Refresh schedule** (optional):
   - Set up automatic refresh (e.g., hourly, daily)
   - This keeps your dashboard up-to-date

## Step 5: Create Visualizations

### Visualization 1: Total Hours by Resource

1. Click **Add visual** → **Vertical bar chart**
2. **X-axis**: Drag `ResourceNameDisplay` field
3. **Value**: Drag `Hours` field → Aggregate: **Sum**
4. **Visual title**: "Total Hours by Resource"

### Visualization 2: Hours Over Time

1. Click **Add visual** → **Line chart**
2. **X-axis**: Drag `Date` field
3. **Value**: Drag `Hours` field → Aggregate: **Sum**
4. **Color**: Drag `ResourceNameDisplay` field
5. **Visual title**: "Hours Trend by Resource"

### Visualization 3: Project Breakdown

1. Click **Add visual** → **Pie chart**
2. **Group/Color**: Drag `ProjectName` field
3. **Value**: Drag `Hours` field → Aggregate: **Sum**
4. **Visual title**: "Hours by Project"

### Visualization 4: Resource Summary Table

1. Click **Add visual** → **Table**
2. **Group by**: Drag `ResourceNameDisplay` field
3. **Values**:
   - Drag `Hours` field → Aggregate: **Sum** → Rename to "Total Hours"
   - Drag `ProjectCode` field → Aggregate: **Count distinct** → Rename to "Projects"
   - Drag `CostEstimateUSD` field → Aggregate: **Sum** → Rename to "Total Cost"
4. **Visual title**: "Resource Summary"

### Visualization 5: Weekly Hours Heatmap

1. Click **Add visual** → **Heat map**
2. **Rows**: Drag `ResourceNameDisplay` field
3. **Columns**: Drag `Date` field
4. **Values**: Drag `Hours` field → Aggregate: **Sum**
5. **Visual title**: "Weekly Hours Heatmap"

### Visualization 6: Cost Analysis

1. Click **Add visual** → **KPI**
2. **Value**: Drag `CostEstimateUSD` field → Aggregate: **Sum**
3. **Visual title**: "Total Processing Cost"
4. Add another KPI for **Average Cost** (Aggregate: **Average**)

## Step 6: Format Your Dashboard

1. **Add filters**:
   - Add filter for `Date` (date range selector)
   - Add filter for `ResourceNameDisplay` (multi-select dropdown)
   - Add filter for `ProjectCode` (multi-select dropdown)
   - Add filter for `YearMonth` (month selector)

2. **Customize theme**:
   - Click **Themes** (top toolbar)
   - Choose a theme or create custom

3. **Arrange visuals**:
   - Drag and resize visuals to organize layout
   - Place KPIs at the top
   - Group related visualizations

4. **Add text boxes**:
   - Add title: "Timesheet OCR Dashboard"
   - Add subtitle: "Real-time Timesheet Analysis"
   - Add last updated timestamp (parameter)

## Step 7: Publish Dashboard

1. Click **Share** (top right) → **Publish dashboard**
2. **Dashboard name**: `TimesheetOCR Dashboard`
3. Click **Publish**
4. **Share with users**:
   - Click **Share** → **Share dashboard**
   - Add email addresses of users
   - Set permissions (View/Edit)
   - Click **Share**

## Step 8: Set Up Email Reports (Optional)

1. Open your published dashboard
2. Click **Schedule email report** (top right)
3. Configure:
   - **Report name**: "Weekly Timesheet Summary"
   - **Recipients**: Enter email addresses
   - **Schedule**: Weekly (Monday 9 AM)
   - **Format**: PDF or Excel
4. Click **Create**

## Sample Dashboard Layout

```
┌────────────────────────────────────────────────────────────────┐
│                 Timesheet OCR Dashboard                        │
│                Real-time Timesheet Analysis                    │
├────────────────────────────────────────────────────────────────┤
│ Filters: [Date Range] [Resource] [Project] [Month]            │
├────────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│ │Total Cost│ │Avg Cost  │ │Resources │ │Projects  │         │
│ │  $0.25   │ │  $0.02   │ │    12    │ │    45    │         │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
├────────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────┐ ┌─────────────────────────┐    │
│ │                           │ │                         │    │
│ │  Total Hours by Resource  │ │   Hours by Project      │    │
│ │      (Bar Chart)          │ │     (Pie Chart)         │    │
│ │                           │ │                         │    │
│ └───────────────────────────┘ └─────────────────────────┘    │
├────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────┐     │
│ │                                                      │     │
│ │         Hours Trend by Resource                      │     │
│ │              (Line Chart)                            │     │
│ │                                                      │     │
│ └──────────────────────────────────────────────────────┘     │
├────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────┐     │
│ │         Weekly Hours Heatmap                         │     │
│ │         (Resource × Date)                            │     │
│ └──────────────────────────────────────────────────────┘     │
├────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────┐     │
│ │         Resource Summary Table                       │     │
│ │ Resource │ Total Hours │ Projects │ Total Cost      │     │
│ │─────────────────────────────────────────────────     │     │
│ │ John Doe │    160.0    │    8     │   $0.15        │     │
│ │ Jane Smith│   140.5    │    6     │   $0.12        │     │
│ └──────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────┘
```

## Advanced Features

### Calculated Fields

Add custom calculations to your dataset:

1. **Billable Hours** (example):
   ```
   ifelse({Hours} > 0, {Hours}, 0)
   ```

2. **Cost per Hour**:
   ```
   {CostEstimateUSD} / {Hours}
   ```

3. **Week Number**:
   ```
   weekOfYear({Date})
   ```

4. **Month Name**:
   ```
   formatDate({Date}, 'MMMM yyyy')
   ```

### Parameters

Create parameters for dynamic filtering:

1. **Start Date Parameter**:
   - Type: Date
   - Default: Beginning of current month

2. **End Date Parameter**:
   - Type: Date
   - Default: Today

3. Use parameters in calculated fields for custom date ranges

### Drill-Downs

Enable drill-down navigation:

1. Select a visual
2. Click **Field wells**
3. Add hierarchy: `YearMonth` → `Date` → `ResourceName`
4. Enable drill-down in visual settings

## Monitoring and Alerts

### Set Up Anomaly Detection

1. Select a visual (e.g., Hours Trend)
2. Click **Add** → **Add anomaly insight**
3. Configure sensitivity
4. QuickSight will highlight unusual patterns

### Create Threshold Alerts

1. Create a KPI visual for hours
2. Click **Format visual**
3. Set **Conditional formatting**:
   - Green: Hours > 100
   - Yellow: Hours 50-100
   - Red: Hours < 50

## Cost Optimization

QuickSight costs:
- **Standard**: $9/user/month (pay per session: $0.30/session, max $5/month)
- **Enterprise**: $18/user/month (unlimited sessions)
- **SPICE**: Additional storage beyond 10GB: $0.38/GB/month

**Recommendation**:
- Start with **Standard Edition** for cost savings
- Use **SPICE** (in-memory storage) for faster dashboards
- Set up **auto-refresh** to keep data current

## Troubleshooting

### Issue: Data Not Loading

**Solution**:
1. Check QuickSight has permission to access DynamoDB
2. Verify table name is correct: `TimesheetOCR-dev`
3. Check region is `us-east-1`

### Issue: Decimal Fields Show as Strings

**Solution**:
1. Edit dataset
2. Find `Hours` and `CostEstimateUSD` fields
3. Change type to **Decimal**
4. Save and refresh

### Issue: Date Field Not Recognized

**Solution**:
1. Edit dataset
2. Find `Date` field
3. Change type to **Date**
4. Set format: `yyyy-MM-dd`
5. Save and refresh

## Next Steps

1. ✅ Complete QuickSight setup (Steps 1-3)
2. ✅ Create initial visualizations (Steps 4-5)
3. ✅ Format and organize dashboard (Step 6)
4. ✅ Publish and share (Step 7)
5. ✅ Set up automated refresh schedule
6. ✅ Configure email reports (optional)
7. ✅ Add anomaly detection for insights
8. ✅ Train your team on using the dashboard

## Support Resources

- [QuickSight Documentation](https://docs.aws.amazon.com/quicksight/)
- [DynamoDB as Data Source](https://docs.aws.amazon.com/quicksight/latest/user/create-a-data-set-dynamodb.html)
- [QuickSight Pricing](https://aws.amazon.com/quicksight/pricing/)
- [QuickSight Best Practices](https://docs.aws.amazon.com/quicksight/latest/user/best-practices.html)

---

**Your DynamoDB data is ready for QuickSight! Follow this guide to create powerful visualizations and dashboards.**
