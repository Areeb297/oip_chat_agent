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
import re


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
    BUBBLE = "bubble"
    SCATTER = "scatter"


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

# Extended palette for pie/donut slices (16+ distinct colors)
PIE_COLORS = [
    "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6",
    "#06b6d4", "#ec4899", "#f97316", "#14b8a6", "#6366f1",
    "#84cc16", "#e11d48", "#0ea5e9", "#a855f7", "#d946ef",
    "#64748b", "#facc15", "#2dd4bf", "#fb923c", "#818cf8",
]


def _humanize_key(key: str) -> str:
    """Convert a CamelCase or snake_case key to a human-readable label.

    Examples:
        TicketsCreated  -> Tickets Created
        SLABreached     -> SLA Breached
        open_tickets    -> Open Tickets
        CompletionRate  -> Completion Rate
    """
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', key)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s)
    s = s.replace('_', ' ')
    return ' '.join(w if w.isupper() else w.capitalize() for w in s.split())


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
        if chart_type in [ChartType.PIE.value, ChartType.DONUT.value]:
            # For pie/donut charts, show percentages
            max_pct = (max_val / total * 100) if total > 0 else 0
            insights.append(f"Largest segment: {max_category} ({max_val:,.0f}, {max_pct:.1f}%)")
            if len(values) > 1 and min_val != max_val:
                min_pct = (min_val / total * 100) if total > 0 else 0
                insights.append(f"Smallest segment: {min_category} ({min_val:,.0f}, {min_pct:.1f}%)")
            # Add concentration insight
            if max_pct > 80 and len(values) > 2:
                insights.append(f"{max_category} dominates at {max_pct:.0f}% of total")
            # Add non-zero category count
            non_zero = sum(1 for v in values if v > 0)
            if non_zero < len(values):
                insights.append(f"{non_zero} of {len(values)} categories have activity")
        else:
            insights.append(f"Highest: {max_category} ({max_val:,.0f})")
            if len(values) > 1 and min_val != max_val:
                insights.append(f"Lowest: {min_category} ({min_val:,.0f})")
            # Add range insight for bar/line with 3+ items
            if len(values) >= 3:
                spread = max_val - min_val
                insights.append(f"Range: {spread:,.0f} (from {min_val:,.0f} to {max_val:,.0f})")

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

    return insights[:5]  # Max 5 insights


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
    figure_number: int = 1,
    tool_context=None,
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
        label = y_labels[i] if y_labels and i < len(y_labels) else _humanize_key(key)
        series.append({
            "key": key,
            "label": label,
            "color": colors[i % len(colors)]
        })

    # Generate insights and description
    insights = generate_insights(data, y_keys, chart_type)
    auto_description = description or generate_description(data, y_keys, chart_type, title)

    # Build the chart configuration (figureLabel set after session state determines number)
    config = {
        "type": chart_type,
        "title": title,
        "description": auto_description,
        "figureLabel": "",  # set below after accumulator determines figure number
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
    if chart_type == ChartType.PIE.value:
        # True pie chart - solid filled circle with wedge slices (no hole)
        config["type"] = "pie"
        config["innerRadius"] = 0
        config["outerRadius"] = 100
        config["showLabels"] = True
        config["labelType"] = "percentage"
        # Position legend to the right to avoid overlapping with slice labels
        config["styling"]["legendPosition"] = "right"
        # Assign distinct colors to each slice
        for i, point in enumerate(config["data"]):
            point["color"] = PIE_COLORS[i % len(PIE_COLORS)]
    elif chart_type == ChartType.DONUT.value:
        # Donut chart - ring with hollow center
        config["type"] = "donut"
        config["innerRadius"] = 60
        config["outerRadius"] = 100
        config["showLabels"] = True
        config["labelType"] = "percentage"
        # Position legend to the right to avoid overlapping with slice labels
        config["styling"]["legendPosition"] = "right"
        # Assign distinct colors to each slice
        for i, point in enumerate(config["data"]):
            point["color"] = PIE_COLORS[i % len(PIE_COLORS)]
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
    print(f"📊 [CHART CONFIG] type={chart_type}, series={[s['key'] for s in series]}, data_points={len(data)}")
    print(f"📊 [CHART JSON preview] {chart_json[:500]}")

    # Determine figure number from invocation-scoped counter, then store
    _fig_num = figure_number  # default from parameter
    if tool_context is not None:
        try:
            # Use temp: prefix for invocation-scoped state (resets each request)
            chart_count = tool_context.state.get("temp:chart_count") or 0
            _fig_num = chart_count + 1
            tool_context.state["temp:chart_count"] = _fig_num
            config["figureLabel"] = f"Figure {_fig_num}: {title}"
            chart_json = json.dumps(config, indent=2)  # re-serialize with correct label
            tool_context.state["last_chart_output"] = chart_json
            # Also accumulate for multi-chart session fallback
            existing = tool_context.state.get("last_chart_outputs") or []
            if isinstance(existing, str):
                existing = [existing]
            existing.append(chart_json)
            tool_context.state["last_chart_outputs"] = existing
        except Exception:
            pass
    figure_label = f"Figure {_fig_num}: {title}"
    if not config.get("figureLabel"):
        config["figureLabel"] = figure_label
        chart_json = json.dumps(config, indent=2)

    # Return chart block + brief context for the LLM to write its own analysis.
    # The chart card already renders figureLabel, description, and insights from JSON.
    # We give the LLM a plain-text context note (not HTML) so it knows what data the
    # chart contains and can write unique analytical commentary.
    insights_note = "; ".join(insights) if insights else ""
    context_note = f"[Chart rendered: {figure_label}. {auto_description}. {insights_note}]"

    output = f"""<!--CHART_START-->
{chart_json}
<!--CHART_END-->
{context_note}"""

    return output


def create_ticket_status_chart(
    open_tickets: int,
    completed_tickets: int,
    suspended_tickets: int,
    pending_approval: int = 0,
    sla_breached: int = 0,
    title: str = "Ticket Status Distribution",
    tool_context=None,
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

    # Generate the donut chart (default for status distribution)
    # Users can request a true pie chart via create_chart_from_session with chart_type="pie"
    chart_output = create_chart(
        data=data,
        title=title,
        x_key="status",
        y_keys=["count"],
        chart_type="donut",
        description="Distribution of tickets by current status",
        colors=[d["color"] for d in data],
        tool_context=tool_context,
    )

    # Add SLA breach warning if applicable
    if sla_breached > 0:
        chart_output += f"\n<p><span style='color:#ef4444'>⚠️ {sla_breached} tickets have breached SLA</span></p>"

    return chart_output


def create_completion_rate_gauge(
    completion_rate: float,
    target_rate: float = 80.0,
    title: str = "Completion Rate",
    tool_context=None,
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
        "figureLabel": "",  # set below after accumulator determines figure number
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

    # Determine figure number from invocation-scoped counter, then store
    _fig_num = 1
    if tool_context is not None:
        try:
            chart_count = tool_context.state.get("temp:chart_count") or 0
            _fig_num = chart_count + 1
            tool_context.state["temp:chart_count"] = _fig_num
            config["figureLabel"] = f"Figure {_fig_num}: {title}"
            chart_json = json.dumps(config, indent=2)
            tool_context.state["last_chart_output"] = chart_json
            existing = tool_context.state.get("last_chart_outputs") or []
            if isinstance(existing, str):
                existing = [existing]
            existing.append(chart_json)
            tool_context.state["last_chart_outputs"] = existing
        except Exception:
            chart_json = json.dumps(config, indent=2)
    else:
        config["figureLabel"] = f"Figure {_fig_num}: {title}"
        chart_json = json.dumps(config, indent=2)
    figure_label = f"Figure {_fig_num}: {title}"

    # Return chart block + brief context note for LLM analysis
    context_note = f"[Chart rendered: {figure_label}. Current: {completion_rate:.1f}%, Target: {target_rate:.0f}%. {status_msg}]"

    return f"""<!--CHART_START-->
{chart_json}
<!--CHART_END-->
{context_note}"""


def create_tickets_over_time_chart(
    chart_type: str = "auto",
    title: str = "Ticket Trend",
    tool_context=None,
) -> str:
    """
    Create a line or area chart showing tickets created vs completed over time.

    Reads timeline data automatically from session state (stored by get_ticket_timeline).
    Do NOT pass data directly — just call this after get_ticket_timeline().

    By default auto-selects chart type:
      - "area" when showing created vs completed (highlights backlog gap)
      - "line" for single series

    Args:
        chart_type: "auto" (default), "line", or "area"
        title: Chart title (default: "Ticket Trend")

    Returns:
        str: Line or area chart configuration with HTML wrapper

    Example flow:
        1. Call get_ticket_timeline(period="month")
        2. Call create_tickets_over_time_chart(title="Monthly Ticket Trend")
    """
    # Read timeline data from session state (stored by get_ticket_timeline)
    data = None
    if tool_context is not None:
        last_data = tool_context.state.get("last_ticket_data")
        if last_data and isinstance(last_data, dict):
            data = last_data.get("timeline", [])

    if not data:
        return "<p>No timeline data in session. Please call get_ticket_timeline() first.</p>"

    # Timeline data uses "Period" as the time key
    time_key = "Period"

    # Auto-detect numeric keys
    first_item = data[0]
    value_keys = [k for k, v in first_item.items()
                  if isinstance(v, (int, float)) and k != time_key]

    if not value_keys:
        return "<p>No numeric data found to visualize.</p>"

    # Auto-select chart type: area for 2-series comparisons (shows backlog gap), line otherwise
    if chart_type == "auto":
        chart_type = "area" if len(value_keys) == 2 else "line"

    print(f"📊 [TIMELINE CHART] type={chart_type}, keys={value_keys}, points={len(data)}, data[0]={data[0]}")

    return create_chart(
        data=data,
        title=title,
        x_key=time_key,
        y_keys=value_keys,
        chart_type=chart_type,
        description="Trend of {} over time".format(
            ", ".join(_humanize_key(k) for k in value_keys)
        ),
        tool_context=tool_context,
    )


def create_project_comparison_chart(
    data: List[Dict[str, Any]],
    project_key: str = "project",
    value_keys: List[str] = None,
    title: str = "Project Comparison",
    tool_context=None,
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
        description="Comparison of {} across projects".format(
            ", ".join(_humanize_key(k) for k in value_keys)
        ),
        colors=colors,
        tool_context=tool_context,
    )


def create_breakdown_chart(
    breakdown_type: str,
    chart_type: str = "bar",
    metric: str = "TotalTickets",
    title: str = None,
    tool_context = None,
) -> str:
    """
    Create a chart from breakdown data stored in session.

    SIMPLE TOOL: Just specify the breakdown type and this creates the chart.
    Uses data from the last get_ticket_summary(include_breakdown=True) call.

    Args:
        breakdown_type: Which breakdown to chart. MUST be one of:
                       - "region" or "by_region" - Chart by region
                       - "project" or "by_project" - Chart by project
                       - "team" or "by_team" - Chart by team
        chart_type: Chart type - "bar" or "pie" (default: "bar")
        metric: Which metric to chart - "TotalTickets", "OpenTickets", "CompletedTickets",
                "CompletionRate" (derived: completed/total * 100)
                (default: "TotalTickets")
        title: Custom title (auto-generated if not provided)
        tool_context: ADK ToolContext for session access

    Returns:
        str: Chart HTML with embedded JSON configuration

    Example calls:
        - "Chart by project" -> create_breakdown_chart(breakdown_type="project")
        - "Pie chart by region" -> create_breakdown_chart(breakdown_type="region", chart_type="pie")
        - "Open tickets by team" -> create_breakdown_chart(breakdown_type="team", metric="OpenTickets")
    """
    if tool_context is None:
        return "<p><span style='color:#dc2626'>Error: No session context available.</span></p>"

    # Get last ticket data from session
    last_data = tool_context.state.get("last_ticket_data")

    if not last_data:
        return """<p><span style='color:#f59e0b'>⚠️ No previous ticket data found.</span></p>
<p>Please ask for ticket data first with include_breakdown=True (e.g., "show tickets by project").</p>"""

    # Normalize breakdown_type
    type_map = {
        "region": "by_region",
        "regions": "by_region",
        "by_region": "by_region",
        "project": "by_project",
        "projects": "by_project",
        "by_project": "by_project",
        "team": "by_team",
        "teams": "by_team",
        "by_team": "by_team",
    }

    key = type_map.get(breakdown_type.lower(), breakdown_type)

    # Get the breakdown data
    breakdown_data = last_data.get(key)

    if not breakdown_data:
        available = [k for k in ["by_region", "by_project", "by_team"] if k in last_data]
        return f"""<p><span style='color:#dc2626'>Error: No '{key}' data found in session.</span></p>
<p>Available breakdowns: {', '.join(available) if available else 'None - call get_ticket_summary with include_breakdown=True'}</p>"""

    # Determine the name key based on breakdown type
    name_key_map = {
        "by_region": "RegionName",
        "by_project": "ProjectName",
        "by_team": "TeamName",
    }
    name_key = name_key_map.get(key, "name")

    # Auto-generate title if not provided
    if not title:
        type_label = key.replace("by_", "").title()
        metric_label = metric.replace("Tickets", " Tickets")
        title = f"{metric_label} by {type_label}"

    print(f"📊 [BREAKDOWN CHART] type={key}, metric={metric}, items={len(breakdown_data)}")

    # Transform data for chart
    chart_data = []
    for item in breakdown_data:
        name = item.get(name_key, "Unknown")
        # Support derived metrics
        if metric.lower() in ("completionrate", "completion_rate"):
            total = item.get("TotalTickets", 0) or 0
            completed = item.get("CompletedTickets", 0) or 0
            value = round((completed / total * 100), 1) if total > 0 else 0.0
        else:
            value = item.get(metric, 0)
        # Handle potential Decimal values
        if hasattr(value, 'as_tuple'):
            value = float(value)
        chart_data.append({
            "category": name,
            "value": value
        })

    # Create the chart
    return create_chart(
        data=chart_data,
        title=title,
        x_key="category",
        y_keys=["value"],
        chart_type=chart_type,
        description=f"{title} ({len(chart_data)} items)",
        tool_context=tool_context,
    )


def create_pm_chart(
    chart_type: str = "bar",
    metric: str = "count",
    title: str = "PM Data",
    tool_context=None,
) -> str:
    """
    Create a chart from PM checklist data stored in the session.

    Reads data from the last get_pm_checklist_data() call automatically.
    Call get_pm_checklist_data() first, then call this tool to visualize.

    Args:
        chart_type: Chart type — "bar", "pie", or "donut" (default: "bar")
        metric: What to measure:
                - "count" — Number of sites per field value or equipment type (default).
                  Best for: "how many sites have each keypad model?"
                - "quantity" — Sum of equipment quantities per site.
                  Best for: "how many door contacts per site?"
                - "count_by_value" — Group records by FieldValue and count sites per group.
                  Best for: "distribution of keypad model types across sites"
        title: Descriptive chart title (e.g., "Keypad Model Distribution")

    Returns:
        str: HTML with <!--CHART_START-->...<!--CHART_END--> chart config,
             or an error/help message if no PM data is in session.

    Example flows:
        1. get_pm_checklist_data(field_name="Keypad Model")
           create_pm_chart(chart_type="pie", metric="count_by_value", title="Keypad Model Distribution")

        2. get_pm_checklist_data(sub_category_name="Door Contact")
           create_pm_chart(chart_type="bar", metric="quantity", title="Door Contacts per Site")

        3. get_pm_checklist_data(field_name="Panel IP")
           create_pm_chart(chart_type="bar", metric="count", title="Panel IPs by Site")
    """
    if tool_context is None:
        return "<p><span style='color:#dc2626'>Error: No session context available.</span></p>"

    last_pm = tool_context.state.get("last_pm_data")
    if not last_pm or not last_pm.get("records"):
        return """<p><span style='color:#f59e0b'>⚠️ No PM checklist data found in this session.</span></p>
<p>Please call get_pm_checklist_data first (e.g., ask about Panel IPs or Door Contacts), then I can chart it.</p>"""

    records = last_pm["records"]
    query_mode = last_pm.get("query_mode", "extension")

    print(f"📊 [PM CHART] mode={query_mode}, metric={metric}, type={chart_type}, records={len(records)}")

    chart_data = []

    if metric == "quantity" and query_mode == "equipment":
        # Bar chart: SiteName vs Quantity (for equipment mode)
        for rec in records:
            site = rec.get("SiteName", "Unknown")
            qty = rec.get("Quantity", 0)
            if isinstance(qty, str):
                try:
                    qty = int(qty)
                except ValueError:
                    qty = 0
            chart_data.append({"category": site, "count": qty})

        return create_chart(
            data=chart_data,
            title=title,
            x_key="category",
            y_keys=["count"],
            chart_type=chart_type,
            description=f"Equipment quantity per site ({len(chart_data)} sites)",
            tool_context=tool_context,
        )

    elif metric == "count_by_value" and query_mode == "extension":
        # Group by FieldValue, count sites per group (pie/donut for distribution)
        from collections import Counter
        value_counts = Counter(rec.get("FieldValue", "Unknown") for rec in records)
        for value, cnt in value_counts.most_common():
            chart_data.append({"category": str(value), "count": cnt})

        return create_chart(
            data=chart_data,
            title=title,
            x_key="category",
            y_keys=["count"],
            chart_type=chart_type if chart_type in ("pie", "donut") else "pie",
            description=f"Distribution of values ({len(chart_data)} distinct values)",
            tool_context=tool_context,
        )

    else:
        # Default "count" metric: count of records per grouping key
        from collections import Counter
        if query_mode == "extension":
            # Count sites per FieldValue
            key_field = "FieldValue"
        elif query_mode == "equipment":
            # Count sites per SubCategoryName
            key_field = "SubCategoryName"
        else:
            # Overview: count per TicketStatus
            key_field = "TicketStatus"

        value_counts = Counter(rec.get(key_field, "Unknown") for rec in records)
        for value, cnt in value_counts.most_common():
            chart_data.append({"category": str(value), "count": cnt})

        return create_chart(
            data=chart_data,
            title=title,
            x_key="category",
            y_keys=["count"],
            chart_type=chart_type,
            description=f"Count by {_humanize_key(key_field)} ({len(chart_data)} groups)",
            tool_context=tool_context,
        )


def create_engineer_chart(
    metric: str = "completed",
    group_by: str = "engineer",
    chart_type: str = "bar",
    title: str = None,
    tool_context=None,
) -> str:
    """
    Create a chart from engineer performance data stored in session.

    Reads data from the last get_engineer_performance() call automatically.
    Call get_engineer_performance() first, then call this tool to visualize.

    Args:
        metric: What to measure. Options:
                - "completed" — Completed tickets per engineer/group (default)
                - "total" — Total tickets
                - "completion_rate" — Completion rate percentage
                - "sla_breached" — SLA breached tickets
                - "task_type" — Stacked bar of TR/PM/Other TICKETS (from ticket data)
                - "activity_log" — Stacked bar of TR/PM/Other from DAILY ACTIVITY LOGS (requires include_activity=True)
                - "hours" — Total working hours per engineer from daily logs
                - "distance" — Total distance travelled per engineer from daily logs
        group_by: How to group data. Options:
                  - "engineer" — Per engineer (default)
                  - "team" — Aggregated by team
                  - "project" — Aggregated by project
        chart_type: "bar", "pie", "donut", or "gauge" (default: "bar")
        title: Custom title. Auto-generated if not provided.

    Returns:
        str: HTML with <!--CHART_START-->...<!--CHART_END--> chart config

    Example flows:
        1. get_engineer_performance(team_names="Central") -> data stored in session
           create_engineer_chart(metric="completed", group_by="engineer", title="Central Team Performance")

        2. get_engineer_performance(month=1, year=2026) -> data in session
           create_engineer_chart(metric="task_type", group_by="engineer", title="Task Type Distribution - January")
    """
    if tool_context is None:
        return "<p><span style='color:#dc2626'>Error: No session context available.</span></p>"

    last_data = tool_context.state.get("last_engineer_data")
    if not last_data or not last_data.get("engineers"):
        return """<p><span style='color:#f59e0b'>No engineer performance data found in this session.</span></p>
<p>Please call get_engineer_performance first, then I can chart it.</p>"""

    engineers = last_data["engineers"]

    print(f"📊 [ENGINEER CHART] metric={metric}, group_by={group_by}, type={chart_type}, engineers={len(engineers)}")

    # Metric to column mapping
    metric_map = {
        "completed": "CompletedTickets",
        "total": "TotalTickets",
        "completion_rate": "CompletionRate",
        "sla_breached": "SLABreached",
        "open": "OpenTickets",
        "suspended": "SuspendedTickets",
    }

    # Aggregate data by group_by
    from collections import defaultdict

    if group_by == "team":
        group_key = "TeamName"
    elif group_by == "project":
        group_key = "ProjectName"
    else:
        group_key = "EngineerName"

    # Handle task_type as stacked bar (TICKET task types — TR/PM/Other from ticket data)
    if metric == "task_type":
        aggregated = defaultdict(lambda: {"TR": 0, "PM": 0, "Other": 0})
        for eng in engineers:
            key = eng.get(group_key, "Unknown")
            aggregated[key]["TR"] += eng.get("TRTickets", 0) or 0
            aggregated[key]["PM"] += eng.get("PMTickets", 0) or 0
            aggregated[key]["Other"] += eng.get("OtherTickets", 0) or 0

        chart_data = []
        for name, values in aggregated.items():
            chart_data.append({"category": name, "TR": values["TR"], "PM": values["PM"], "Other": values["Other"]})

        if not title:
            title = f"Ticket Task Type Distribution by {group_by.title()}"

        return create_chart(
            data=chart_data,
            title=title,
            x_key="category",
            y_keys=["TR", "PM", "Other"],
            chart_type="stackedBar",
            description=f"Ticket task type breakdown by {group_by} ({len(chart_data)} groups)",
            colors=["#3b82f6", "#22c55e", "#f59e0b"],  # Blue=TR, Green=PM, Orange=Other
            tool_context=tool_context,
        )

    # Handle activity_log — daily activity log entries (NOT ticket data)
    if metric == "activity_log":
        activity_log = last_data.get("activity_log", [])
        if not activity_log:
            return ("<p><span style='color:#f59e0b'>No daily activity log data found.</span></p>"
                    "<p>Try calling get_engineer_performance with include_activity=True first.</p>")

        # Aggregate activity types by engineer
        aggregated = defaultdict(lambda: {"TR": 0, "PM": 0, "Other": 0})
        for entry in activity_log:
            key = entry.get("EngineerName", "Unknown")
            activity_type = entry.get("ActivityType") or "Other"
            if activity_type not in ("TR", "PM"):
                activity_type = "Other"
            aggregated[key][activity_type] += 1

        chart_data = []
        for name, values in sorted(aggregated.items(), key=lambda x: sum(x[1].values()), reverse=True):
            chart_data.append({"category": name, "TR": values["TR"], "PM": values["PM"], "Other": values["Other"]})

        if not title:
            title = f"Daily Activity Log Distribution by {group_by.title()}"

        print(f"📊 [ACTIVITY LOG CHART] {len(chart_data)} engineers, {len(activity_log)} log entries")

        return create_chart(
            data=chart_data,
            title=title,
            x_key="category",
            y_keys=["TR", "PM", "Other"],
            chart_type="stackedBar",
            description=f"Daily activity log entries by {group_by} ({len(chart_data)} engineers, {len(activity_log)} total logs)",
            colors=["#3b82f6", "#22c55e", "#f59e0b"],  # Blue=TR, Green=PM, Orange=Other
            tool_context=tool_context,
        )

    # Handle hours — total working hours per engineer from daily logs
    if metric == "hours":
        activity_log = last_data.get("activity_log", [])
        if not activity_log:
            return ("<p><span style='color:#f59e0b'>No daily activity log data found.</span></p>"
                    "<p>Try calling get_engineer_performance with include_activity=True first.</p>")

        aggregated = defaultdict(float)
        for entry in activity_log:
            key = entry.get("EngineerName", "Unknown")
            aggregated[key] += float(entry.get("DurationHours", 0) or 0)

        chart_data = []
        for name, value in sorted(aggregated.items(), key=lambda x: x[1], reverse=True):
            chart_data.append({"category": name, "value": round(value, 1)})

        if not title:
            title = "Total Working Hours by Engineer"

        return create_chart(
            data=chart_data,
            title=title,
            x_key="category",
            y_keys=["value"],
            chart_type=chart_type,
            description=f"Working hours from daily logs ({len(chart_data)} engineers)",
            tool_context=tool_context,
        )

    # Handle distance — total distance travelled per engineer from daily logs
    if metric == "distance":
        activity_log = last_data.get("activity_log", [])
        if not activity_log:
            return ("<p><span style='color:#f59e0b'>No daily activity log data found.</span></p>"
                    "<p>Try calling get_engineer_performance with include_activity=True first.</p>")

        aggregated = defaultdict(float)
        for entry in activity_log:
            key = entry.get("EngineerName", "Unknown")
            aggregated[key] += float(entry.get("DistanceTravelled", 0) or 0)

        chart_data = []
        for name, value in sorted(aggregated.items(), key=lambda x: x[1], reverse=True):
            chart_data.append({"category": name, "value": round(value, 1)})

        if not title:
            title = "Distance Travelled by Engineer (km)"

        return create_chart(
            data=chart_data,
            title=title,
            x_key="category",
            y_keys=["value"],
            chart_type=chart_type,
            description=f"Distance travelled from daily logs ({len(chart_data)} engineers)",
            tool_context=tool_context,
        )

    # Single metric chart
    col_name = metric_map.get(metric, "CompletedTickets")

    # Aggregate
    aggregated = defaultdict(float)
    counts = defaultdict(int)
    for eng in engineers:
        key = eng.get(group_key, "Unknown")
        val = eng.get(col_name, 0) or 0
        if hasattr(val, 'as_tuple'):
            val = float(val)
        aggregated[key] += val
        counts[key] += 1

    # For completion_rate with grouping, compute average
    if metric == "completion_rate" and group_by != "engineer":
        for key in aggregated:
            if counts[key] > 0:
                aggregated[key] = round(aggregated[key] / counts[key], 1)

    chart_data = []
    for name, value in sorted(aggregated.items(), key=lambda x: x[1], reverse=True):
        chart_data.append({"category": name, "value": value})

    if not chart_data:
        return "<p>No data available to chart.</p>"

    # Auto-generate title
    if not title:
        metric_label = _humanize_key(col_name)
        group_label = group_by.title()
        title = f"{metric_label} by {group_label}"

    # For gauge, use single value from summary
    if chart_type == "gauge" and metric == "completion_rate":
        summary = last_data.get("summary", {})
        rate = summary.get("OverallCompletionRate", 0)
        return create_completion_rate_gauge(float(rate), title=title, tool_context=tool_context)

    return create_chart(
        data=chart_data,
        title=title,
        x_key="category",
        y_keys=["value"],
        chart_type=chart_type,
        description=f"{title} ({len(chart_data)} items)",
        tool_context=tool_context,
    )


def create_inventory_chart(
    metric: str = "quantity",
    group_by: str = "item",
    chart_type: str = "bar",
    title: str = None,
    tool_context=None,
) -> str:
    """
    Create a chart from inventory consumption data stored in session.

    Reads data from the last get_inventory_consumption() call automatically.
    Call get_inventory_consumption() first, then call this tool to visualize.

    Args:
        metric: What to measure. Options:
                - "quantity" — Total quantity consumed per group (default)
                - "count" — Number of transactions per group
        group_by: How to group data. Options:
                  - "item" — Per item/part name (default)
                  - "site" — Per site/location
                  - "category" — Per category
                  - "project" — Per project
        chart_type: "bar", "pie", or "donut" (default: "bar")
        title: Custom title. Auto-generated if not provided.

    Returns:
        str: HTML with <!--CHART_START-->...<!--CHART_END--> chart config

    Example flows:
        1. get_inventory_consumption(month=1, year=2026) -> data stored in session
           create_inventory_chart(metric="quantity", group_by="item", title="Parts Consumed - January")

        2. get_inventory_consumption(item_name="cable") -> data in session
           create_inventory_chart(metric="quantity", group_by="site", title="Cable Usage by Site")
    """
    if tool_context is None:
        return "<p><span style='color:#dc2626'>Error: No session context available.</span></p>"

    last_data = tool_context.state.get("last_inventory_data")
    if not last_data or not last_data.get("transactions"):
        return """<p><span style='color:#f59e0b'>No inventory data found in this session.</span></p>
<p>Please call get_inventory_consumption first, then I can chart it.</p>"""

    transactions = last_data["transactions"]

    print(f"📊 [INVENTORY CHART] metric={metric}, group_by={group_by}, type={chart_type}, txns={len(transactions)}")

    # Group key mapping
    group_key_map = {
        "item": "ItemName",
        "site": "SiteName",
        "category": "CategoryName",
        "project": "ProjectName",
    }
    group_key = group_key_map.get(group_by, "ItemName")

    from collections import defaultdict
    aggregated = defaultdict(lambda: {"quantity": 0, "count": 0})

    for txn in transactions:
        key = txn.get(group_key, "Unknown") or "Unknown"
        qty = txn.get("Quantity", 0) or 0
        if hasattr(qty, 'as_tuple'):
            qty = float(qty)
        aggregated[key]["quantity"] += qty
        aggregated[key]["count"] += 1

    # Build chart data
    value_key = "quantity" if metric == "quantity" else "count"
    chart_data = []
    for name, values in sorted(aggregated.items(), key=lambda x: x[1][value_key], reverse=True):
        chart_data.append({"category": name, "value": values[value_key]})

    if not chart_data:
        return "<p>No data available to chart.</p>"

    # Auto-generate title
    if not title:
        metric_label = "Quantity Consumed" if metric == "quantity" else "Transaction Count"
        group_label = group_by.title()
        title = f"{metric_label} by {group_label}"

    return create_chart(
        data=chart_data,
        title=title,
        x_key="category",
        y_keys=["value"],
        chart_type=chart_type,
        description=f"{title} ({len(chart_data)} items)",
        tool_context=tool_context,
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
