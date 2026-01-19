"""
Data Visualization Tools for OIP Assistant.
Generates Recharts-compatible JSON configurations with intelligent chart selection.

The tool automatically selects the best chart type based on data characteristics:
- BAR: For comparing values across categories
- LINE: For showing trends over time
- PIE: For part-to-whole relationships (≤5 categories)
- GAUGE: For single KPI/progress values
- AREA: For cumulative trends

Frontend Integration:
When the agent returns a chart, the response contains a JSON block marked with
<!--CHART_START--> and <!--CHART_END--> delimiters. The frontend should parse
this and render using Recharts.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
import json


class ChartType(Enum):
    """Supported chart types for Recharts visualization."""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    DONUT = "donut"
    AREA = "area"
    STACKED_BAR = "stackedBar"
    GROUPED_BAR = "groupedBar"
    GAUGE = "gauge"
    RADIAL = "radialBar"


# Professional color palette (consistent with OIP branding)
DEFAULT_COLORS = {
    "blue": "#3b82f6",
    "green": "#22c55e",
    "orange": "#f59e0b",
    "red": "#ef4444",
    "purple": "#8b5cf6",
    "cyan": "#06b6d4",
    "slate": "#64748b",
}

# Status-specific colors for ticket data
STATUS_COLORS = {
    "open": "#3b82f6",       # Blue
    "completed": "#22c55e",   # Green
    "suspended": "#f59e0b",   # Orange
    "pending": "#8b5cf6",     # Purple
    "breached": "#ef4444",    # Red
    "total": "#3b82f6",       # Blue
}


def analyze_data_for_chart_type(
    data: List[Dict],
    purpose: Optional[str] = None
) -> str:
    """
    Intelligently determine the best chart type based on data characteristics.

    This function analyzes the data structure and content to select the most
    appropriate visualization. The decision is based on:
    - Number of data points/categories
    - Presence of time-based fields
    - Whether values represent parts of a whole
    - Number of numeric series

    Args:
        data: List of data dictionaries to visualize
        purpose: Optional hint - "comparison", "trend", "composition", "distribution"

    Returns:
        str: Recommended chart type (bar, line, pie, gauge, area)
    """
    if not data:
        return ChartType.BAR.value

    num_categories = len(data)
    keys = list(data[0].keys()) if data else []
    numeric_keys = [k for k in keys if isinstance(data[0].get(k), (int, float))]

    # Check for time-based data (indicates trend)
    time_indicators = ['date', 'month', 'year', 'week', 'day', 'time', 'period', 'quarter']
    has_time_axis = any(
        any(t in k.lower() for t in time_indicators)
        for k in keys
        if not isinstance(data[0].get(k), (int, float))
    )

    # Check for percentage/proportion data (should sum to ~100)
    if numeric_keys:
        total = sum(d.get(numeric_keys[0], 0) for d in data)
        is_proportion = 95 <= total <= 105  # Roughly adds to 100
    else:
        is_proportion = False

    # Decision tree for chart type selection

    # 1. Explicit purpose takes priority
    if purpose == "trend" or has_time_axis:
        if len(numeric_keys) > 1:
            return ChartType.LINE.value  # Multi-line for multiple metrics
        return ChartType.LINE.value

    if purpose == "composition" or is_proportion:
        if num_categories <= 5:
            return ChartType.PIE.value
        return ChartType.BAR.value  # Too many slices for pie

    # 2. Single value = Gauge
    if num_categories == 1 and len(numeric_keys) == 1:
        return ChartType.GAUGE.value

    # 3. Small number of categories = Part-to-whole check
    if num_categories <= 5:
        # Check if it looks like a status breakdown
        status_keywords = ['status', 'type', 'category', 'state']
        non_numeric_key = next((k for k in keys if k not in numeric_keys), None)
        if non_numeric_key and any(kw in non_numeric_key.lower() for kw in status_keywords):
            return ChartType.PIE.value

    # 4. Default to bar for categorical comparisons
    return ChartType.BAR.value


def generate_insights(data: List[Dict], y_keys: List[str], chart_type: str) -> List[str]:
    """
    Generate automatic insights from the data.

    Provides 2-4 key observations about the data to help users understand
    the visualization at a glance.

    Args:
        data: The chart data
        y_keys: Keys representing the y-axis values
        chart_type: The type of chart being generated

    Returns:
        List of insight strings
    """
    insights = []

    if not data or not y_keys:
        return insights

    primary_key = y_keys[0]
    values = [d.get(primary_key, 0) for d in data if d.get(primary_key) is not None]

    if not values:
        return insights

    max_val = max(values)
    min_val = min(values)
    avg_val = sum(values) / len(values)
    total = sum(values)

    max_idx = values.index(max_val)
    min_idx = values.index(min_val)

    # Get category names (x-axis key)
    x_key = next((k for k in data[0].keys() if k not in y_keys), None)

    if x_key:
        max_category = data[max_idx].get(x_key, "Unknown")
        min_category = data[min_idx].get(x_key, "Unknown")

        # Format insights based on chart type
        if chart_type == ChartType.PIE.value:
            # For pie charts, show percentages
            max_pct = (max_val / total * 100) if total > 0 else 0
            insights.append(f"Largest segment: {max_category} ({max_pct:.1f}%)")
            if len(values) > 1 and min_val != max_val:
                min_pct = (min_val / total * 100) if total > 0 else 0
                insights.append(f"Smallest segment: {min_category} ({min_pct:.1f}%)")
        else:
            insights.append(f"Highest: {max_category} ({max_val})")
            if len(values) > 1 and min_val != max_val:
                insights.append(f"Lowest: {min_category} ({min_val})")

    # Add summary stats - but only if they make sense
    # Detect binary "X vs Non-X" comparisons where average is meaningless
    is_binary_comparison = False
    if len(values) == 2 and x_key:
        categories = [str(d.get(x_key, "")).lower() for d in data]
        # Check for "non-", "within", "remaining" patterns that indicate binary split
        binary_indicators = ["non-", "non_", "within", "remaining", "other", "rest"]
        is_binary_comparison = any(
            any(ind in cat for ind in binary_indicators)
            for cat in categories
        )

    if chart_type in [ChartType.LINE.value, ChartType.BAR.value]:
        if is_binary_comparison and total > 0:
            # For binary comparisons, show ratio instead of average
            pct1 = (values[0] / total * 100)
            pct2 = (values[1] / total * 100)
            cat1 = data[0].get(x_key, "First")
            cat2 = data[1].get(x_key, "Second")
            insights.append(f"Split: {pct1:.0f}% / {pct2:.0f}%")
        elif len(values) >= 2:
            # For multi-category or same-metric comparisons, average is useful
            insights.append(f"Average: {avg_val:.1f}")

    insights.append(f"Total: {total:,.0f}")

    return insights[:4]  # Max 4 insights


def generate_description(data: List[Dict], y_keys: List[str], chart_type: str, title: str) -> str:
    """
    Generate a contextual description for the chart.

    Args:
        data: The chart data
        y_keys: Keys representing the y-axis values
        chart_type: The type of chart
        title: The chart title

    Returns:
        A descriptive string about the chart
    """
    num_points = len(data)
    num_series = len(y_keys)

    type_descriptions = {
        ChartType.BAR.value: f"Comparison of {num_points} categories",
        ChartType.LINE.value: f"Trend analysis across {num_points} data points",
        ChartType.PIE.value: f"Distribution breakdown across {num_points} segments",
        ChartType.DONUT.value: f"Distribution breakdown across {num_points} segments",
        ChartType.AREA.value: f"Cumulative trend over {num_points} periods",
        ChartType.GAUGE.value: "Current value against target",
        ChartType.STACKED_BAR.value: f"Stacked comparison of {num_points} categories with {num_series} series",
        ChartType.GROUPED_BAR.value: f"Grouped comparison of {num_points} categories",
    }

    return type_descriptions.get(chart_type, f"Visualization with {num_points} data points")


def create_chart(
    data: List[Dict[str, Any]],
    title: str,
    x_key: str,
    y_keys: List[str],
    chart_type: Optional[str] = None,
    description: Optional[str] = None,
    y_labels: Optional[List[str]] = None,
    colors: Optional[List[str]] = None,
    figure_number: int = 1
) -> str:
    """
    Create a Recharts-compatible chart configuration with intelligent chart selection.

    This tool generates chart configurations for data visualization. If chart_type
    is not specified, it automatically selects the best type based on data
    characteristics (see analyze_data_for_chart_type for selection logic).

    The output is a JSON configuration wrapped in HTML comments that the frontend
    can detect and render as an interactive Recharts component.

    Args:
        data: List of data points, e.g., [{"month": "Jan", "tickets": 10}, ...]
              Each dict represents one data point with category (x) and value (y) keys.
        title: Chart title - should be descriptive and include context
               (e.g., "Ticket Status Distribution - January 2026")
        x_key: Key for x-axis/category values (e.g., "month", "status", "project")
        y_keys: Keys for y-axis values (e.g., ["tickets"], ["open", "completed"])
                Use multiple keys for multi-series charts.
        chart_type: Optional - "bar", "line", "pie", "area", "gauge", "stackedBar"
                   If not provided, automatically selected based on data.
        description: Optional chart description. Auto-generated if not provided.
        y_labels: Optional display labels for y_keys (e.g., ["Total Tickets"])
                  If not provided, y_keys are title-cased.
        colors: Optional color palette. Uses professional defaults if not provided.
        figure_number: Figure number for academic-style labeling (default: 1)

    Returns:
        str: HTML string containing the chart JSON configuration wrapped in
             <!--CHART_START--> and <!--CHART_END--> delimiters, followed by
             a text summary with insights.

    Example:
        # Ticket status breakdown (auto-selects pie chart)
        create_chart(
            data=[{"status": "Open", "count": 6}, {"status": "Closed", "count": 7}],
            title="Ticket Status Distribution",
            x_key="status",
            y_keys=["count"]
        )

        # Tickets over time (auto-selects line chart)
        create_chart(
            data=[{"month": "Jan", "tickets": 10}, {"month": "Feb", "tickets": 15}],
            title="Monthly Ticket Trend",
            x_key="month",
            y_keys=["tickets"]
        )
    """
    # Auto-select chart type if not specified
    if chart_type is None:
        chart_type = analyze_data_for_chart_type(data)

    # Default colors (professional palette)
    default_color_list = list(DEFAULT_COLORS.values())
    colors = colors or default_color_list

    # Build series configuration
    series = []
    for i, key in enumerate(y_keys):
        label = y_labels[i] if y_labels and i < len(y_labels) else key.replace("_", " ").title()
        series.append({
            "key": key,
            "label": label,
            "color": colors[i % len(colors)]
        })

    # Generate insights and description
    insights = generate_insights(data, y_keys, chart_type)
    auto_description = description or generate_description(data, y_keys, chart_type, title)

    # Create figure label
    figure_label = f"Figure {figure_number}: {title}"

    # Build the chart configuration
    config = {
        "type": chart_type,
        "title": title,
        "description": auto_description,
        "figureLabel": figure_label,
        "data": data,
        "xKey": x_key,
        "series": series,
        "insights": insights,
        "styling": {
            "showGrid": True,
            "showLegend": len(y_keys) > 1 or chart_type == ChartType.PIE.value,
            "showTooltip": True,
            "animate": True
        }
    }

    # Add chart-specific configurations
    # NOTE: Always use donut chart instead of pie for better aesthetics
    if chart_type == ChartType.PIE.value or chart_type == ChartType.DONUT.value:
        config["type"] = "donut"  # Always use donut
        config["innerRadius"] = 60
        config["outerRadius"] = 100
        config["showLabels"] = True
        config["labelType"] = "percentage"
    elif chart_type == ChartType.GAUGE.value and data:
        value = data[0].get(y_keys[0], 0) if data else 0
        config["value"] = value
        config["maxValue"] = 100
        config["thresholds"] = [
            {"value": 40, "color": "#ef4444", "label": "Critical"},
            {"value": 70, "color": "#f59e0b", "label": "Warning"},
            {"value": 100, "color": "#22c55e", "label": "Good"}
        ]

    # Generate the output with chart JSON and text summary
    chart_json = json.dumps(config, indent=2)

    # Build insights HTML
    insights_html = ""
    if insights:
        insights_list = "".join(f"<li>{insight}</li>" for insight in insights)
        insights_html = f"<p><strong>Key Insights:</strong></p><ul>{insights_list}</ul>"

    # Return both the chart config and a human-readable summary
    output = f"""<!--CHART_START-->
{chart_json}
<!--CHART_END-->

<p><em>{figure_label}</em></p>
<p>{auto_description}</p>
{insights_html}"""

    return output


def create_ticket_status_chart(
    open_tickets: int,
    completed_tickets: int,
    suspended_tickets: int,
    pending_approval: int = 0,
    sla_breached: int = 0,
    title: str = "Ticket Status Distribution"
) -> str:
    """
    Create a ticket status distribution chart (pie chart).

    Specialized helper for visualizing ticket status breakdown.
    Automatically uses pie chart for part-to-whole visualization.
    Uses consistent status colors (blue=open, green=completed, orange=suspended).

    Args:
        open_tickets: Number of tickets in Open status
        completed_tickets: Number of tickets marked Complete
        suspended_tickets: Number of tickets in Suspended status
        pending_approval: Number of tickets awaiting approval (optional)
        sla_breached: Number of tickets that breached SLA (shown as separate metric)
        title: Chart title (default: "Ticket Status Distribution")

    Returns:
        str: Chart configuration JSON with HTML wrapper

    Example:
        create_ticket_status_chart(
            open_tickets=12,
            completed_tickets=7,
            suspended_tickets=3,
            pending_approval=2
        )
    """
    data = []

    if open_tickets > 0:
        data.append({"status": "Open", "count": open_tickets, "color": STATUS_COLORS["open"]})
    if completed_tickets > 0:
        data.append({"status": "Completed", "count": completed_tickets, "color": STATUS_COLORS["completed"]})
    if suspended_tickets > 0:
        data.append({"status": "Suspended", "count": suspended_tickets, "color": STATUS_COLORS["suspended"]})
    if pending_approval > 0:
        data.append({"status": "Pending Approval", "count": pending_approval, "color": STATUS_COLORS["pending"]})

    if not data:
        return "<p>No ticket data available to chart.</p>"

    # Generate the pie chart
    chart_output = create_chart(
        data=data,
        title=title,
        x_key="status",
        y_keys=["count"],
        chart_type="pie",
        description="Distribution of tickets by current status",
        colors=[d["color"] for d in data]
    )

    # Add SLA breach warning if applicable
    if sla_breached > 0:
        chart_output += f"\n<p><span style='color:#ef4444'>⚠️ {sla_breached} tickets have breached SLA</span></p>"

    return chart_output


def create_completion_rate_gauge(
    completion_rate: float,
    target_rate: float = 80.0,
    title: str = "Completion Rate"
) -> str:
    """
    Create a completion rate gauge chart.

    Displays a single KPI value (completion rate) against a target,
    with color-coded thresholds (red < 40%, yellow 40-70%, green > 70%).

    Args:
        completion_rate: Current completion rate (0-100)
        target_rate: Target completion rate (default: 80%)
        title: Chart title (default: "Completion Rate")

    Returns:
        str: Gauge chart configuration with HTML wrapper

    Example:
        create_completion_rate_gauge(completion_rate=65.5, target_rate=80.0)
    """
    # Determine status color and message
    if completion_rate >= 70:
        status_color = "#22c55e"
        status_msg = "Good progress!"
    elif completion_rate >= 40:
        status_color = "#f59e0b"
        status_msg = "Moderate progress - keep pushing"
    else:
        status_color = "#ef4444"
        status_msg = "Below target - needs attention"

    config = {
        "type": "gauge",
        "title": title,
        "description": f"Current completion rate vs target of {target_rate:.0f}%",
        "figureLabel": f"Figure 1: {title}",
        "value": round(completion_rate, 1),
        "maxValue": 100,
        "target": target_rate,
        "thresholds": [
            {"value": 40, "color": "#ef4444", "label": "Critical"},
            {"value": 70, "color": "#f59e0b", "label": "Warning"},
            {"value": 100, "color": "#22c55e", "label": "Good"}
        ],
        "insights": [
            f"Current: {completion_rate:.1f}%",
            f"Target: {target_rate:.0f}%",
            f"Gap: {target_rate - completion_rate:.1f}%" if completion_rate < target_rate else "Target achieved!",
            status_msg
        ],
        "styling": {
            "showTooltip": True,
            "animate": True
        }
    }

    chart_json = json.dumps(config, indent=2)

    # Build insights HTML
    insights_html = f"""<ul>
<li>Current: <strong>{completion_rate:.1f}%</strong></li>
<li>Target: {target_rate:.0f}%</li>
<li><span style='color:{status_color}'>{status_msg}</span></li>
</ul>"""

    return f"""<!--CHART_START-->
{chart_json}
<!--CHART_END-->

<p><em>Figure 1: {title}</em></p>
{insights_html}"""


def create_tickets_over_time_chart(
    data: List[Dict[str, Any]],
    time_key: str = "month",
    value_keys: List[str] = None,
    title: str = "Ticket Trend"
) -> str:
    """
    Create a line chart showing tickets over time.

    Specialized helper for time-series ticket visualizations.
    Automatically uses line chart for trend analysis.

    Args:
        data: List of time-series data points
              e.g., [{"month": "Jan", "total": 15, "completed": 10}, ...]
        time_key: Key for the time axis (default: "month")
        value_keys: Keys for values to plot (default: auto-detect numeric keys)
        title: Chart title (default: "Ticket Trend")

    Returns:
        str: Line chart configuration with HTML wrapper

    Example:
        create_tickets_over_time_chart(
            data=[
                {"month": "Jan", "total": 15, "completed": 10},
                {"month": "Feb", "total": 18, "completed": 14}
            ],
            time_key="month",
            value_keys=["total", "completed"]
        )
    """
    if not data:
        return "<p>No data available to chart.</p>"

    # Auto-detect numeric keys if not provided
    if value_keys is None:
        first_item = data[0]
        value_keys = [k for k, v in first_item.items()
                      if isinstance(v, (int, float)) and k != time_key]

    if not value_keys:
        return "<p>No numeric data found to visualize.</p>"

    return create_chart(
        data=data,
        title=title,
        x_key=time_key,
        y_keys=value_keys,
        chart_type="line",
        description=f"Trend of {', '.join(value_keys)} over time"
    )


def create_project_comparison_chart(
    data: List[Dict[str, Any]],
    project_key: str = "project",
    value_keys: List[str] = None,
    title: str = "Project Comparison"
) -> str:
    """
    Create a bar chart comparing metrics across projects.

    Specialized helper for project-level comparisons.
    Uses grouped or stacked bar chart depending on number of metrics.

    Args:
        data: List of project data points
              e.g., [{"project": "ANB", "open": 12, "completed": 8}, ...]
        project_key: Key for project names (default: "project")
        value_keys: Keys for values to compare (default: auto-detect)
        title: Chart title (default: "Project Comparison")

    Returns:
        str: Bar chart configuration with HTML wrapper

    Example:
        create_project_comparison_chart(
            data=[
                {"project": "ANB", "open": 12, "completed": 8, "suspended": 3},
                {"project": "Barclays", "open": 8, "completed": 15, "suspended": 1}
            ]
        )
    """
    if not data:
        return "<p>No project data available to chart.</p>"

    # Auto-detect numeric keys if not provided
    if value_keys is None:
        first_item = data[0]
        value_keys = [k for k, v in first_item.items()
                      if isinstance(v, (int, float)) and k != project_key]

    if not value_keys:
        return "<p>No numeric data found to visualize.</p>"

    # Use stacked bar if multiple metrics, otherwise regular bar
    chart_type = "stackedBar" if len(value_keys) > 1 else "bar"

    # Apply status colors if applicable
    colors = []
    for key in value_keys:
        key_lower = key.lower()
        if "open" in key_lower:
            colors.append(STATUS_COLORS["open"])
        elif "complete" in key_lower:
            colors.append(STATUS_COLORS["completed"])
        elif "suspend" in key_lower:
            colors.append(STATUS_COLORS["suspended"])
        elif "pending" in key_lower:
            colors.append(STATUS_COLORS["pending"])
        else:
            colors.append(DEFAULT_COLORS["blue"])

    return create_chart(
        data=data,
        title=title,
        x_key=project_key,
        y_keys=value_keys,
        chart_type=chart_type,
        description=f"Comparison of {', '.join(value_keys)} across projects",
        colors=colors
    )


# For testing
if __name__ == "__main__":
    # Test ticket status chart
    print("=== Ticket Status Pie Chart ===")
    result = create_ticket_status_chart(
        open_tickets=12,
        completed_tickets=7,
        suspended_tickets=3,
        pending_approval=2,
        sla_breached=5
    )
    print(result)
    print()

    # Test completion rate gauge
    print("=== Completion Rate Gauge ===")
    result = create_completion_rate_gauge(65.5, 80.0)
    print(result)
    print()

    # Test auto-selection for time series
    print("=== Auto-Selected Line Chart ===")
    result = create_chart(
        data=[
            {"month": "Jan", "tickets": 15},
            {"month": "Feb", "tickets": 18},
            {"month": "Mar", "tickets": 12}
        ],
        title="Monthly Ticket Trend",
        x_key="month",
        y_keys=["tickets"]
    )
    print(result)
