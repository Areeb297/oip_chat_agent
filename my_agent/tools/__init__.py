"""Agent tools - RAG search, database queries, chart visualization, etc."""
from .rag_tool import search_oip_documents
from .db_tools import get_ticket_summary, get_current_date, create_chart_from_session, get_lookups
from .chart_tools import (
    create_chart,
    create_ticket_status_chart,
    create_completion_rate_gauge,
    create_tickets_over_time_chart,
    create_project_comparison_chart,
    create_breakdown_chart,
)

__all__ = [
    # RAG tools
    "search_oip_documents",
    # Database tools
    "get_ticket_summary",
    "get_current_date",
    "get_lookups",
    # Session-aware chart tools (uses stored data)
    "create_chart_from_session",
    "create_breakdown_chart",
    # Chart tools (Recharts-compatible)
    "create_chart",
    "create_ticket_status_chart",
    "create_completion_rate_gauge",
    "create_tickets_over_time_chart",
    "create_project_comparison_chart",
]
