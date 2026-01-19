"""Pydantic models for data validation and typing"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================
class DocumentType(str, Enum):
    """Supported document types"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


class SearchStatus(str, Enum):
    """Status of search operations"""
    SUCCESS = "success"
    NO_RESULTS = "no_results"
    ERROR = "error"


# =============================================================================
# DOCUMENT MODELS
# =============================================================================
class ChunkMetadata(BaseModel):
    """Metadata for a document chunk"""
    source: str = Field(..., description="Source file name")
    page: Optional[int] = Field(None, description="Page number if applicable")
    chunk_index: int = Field(..., description="Index of chunk in document")
    total_chunks: int = Field(..., description="Total chunks in document")
    doc_type: Optional[DocumentType] = Field(None, description="Document type")


class DocumentChunk(BaseModel):
    """A chunk of text with metadata and optional embedding"""
    text: str = Field(..., description="The chunk text content")
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")

    class Config:
        arbitrary_types_allowed = True


class Document(BaseModel):
    """A full document before chunking"""
    content: str = Field(..., description="Full document text")
    source: str = Field(..., description="Source file path")
    doc_type: DocumentType


# =============================================================================
# SEARCH MODELS
# =============================================================================
class SearchResult(BaseModel):
    """Single result from RAG search"""
    text: str = Field(..., description="Retrieved text chunk")
    score: float = Field(..., description="Similarity score (0-1)")
    metadata: ChunkMetadata


class RAGSearchResponse(BaseModel):
    """Complete response from RAG search"""
    status: SearchStatus
    query: str
    results: List[SearchResult] = Field(default_factory=list)
    context: str = Field(default="", description="Combined context for LLM")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if failed")


# =============================================================================
# API REQUEST/RESPONSE MODELS
# =============================================================================
class EmbeddingRequest(BaseModel):
    """Request for embedding generation"""
    texts: List[str] = Field(..., description="Texts to embed")
    model: str = Field(default="openai/text-embedding-ada-002")


class EmbeddingResponse(BaseModel):
    """Response from embedding API"""
    embeddings: List[List[float]]
    model: str
    usage: Optional[Dict[str, int]] = None


class LLMRequest(BaseModel):
    """Request for LLM completion"""
    system_prompt: str
    user_prompt: str
    model: str = Field(default="openai/gpt-4o-mini")
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1000, ge=1)


class LLMResponse(BaseModel):
    """Response from LLM completion"""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None


# =============================================================================
# TOOL RESPONSE MODELS
# =============================================================================
class ToolResponse(BaseModel):
    """Generic tool response structure"""
    status: str
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# TICKET ANALYTICS MODELS
# =============================================================================
class TicketQueryParams(BaseModel):
    """Parameters for ticket summary queries.

    Used by the ticket_analytics agent to validate and structure
    query parameters before calling the database stored procedure.
    """
    username: str = Field(..., description="The logged-in user's username (required)")
    project_name: Optional[str] = Field(None, description="Filter by project name (e.g., 'ANB', 'Barclays')")
    team_name: Optional[str] = Field(None, description="Filter by team name (e.g., 'Maintenance', 'Test Team')")
    month: Optional[int] = Field(None, ge=1, le=12, description="Filter by month (1-12)")
    year: Optional[int] = Field(None, ge=2020, le=2030, description="Filter by year")
    date_from: Optional[str] = Field(None, description="Start date in YYYY-MM-DD format")
    date_to: Optional[str] = Field(None, description="End date in YYYY-MM-DD format")


class TicketSummary(BaseModel):
    """Ticket summary returned from the database stored procedure.

    This model validates the response from usp_Chatbot_GetTicketSummary
    and provides type safety for downstream processing.
    """
    TotalTickets: int = Field(default=0, description="Total count of tickets")
    OpenTickets: int = Field(default=0, description="Number of open tickets")
    SuspendedTickets: int = Field(default=0, description="Number of suspended tickets")
    CompletedTickets: int = Field(default=0, description="Number of completed tickets")
    PendingApproval: int = Field(default=0, description="Tickets awaiting approval")
    SLABreached: int = Field(default=0, description="Tickets that breached SLA")
    CompletionRate: float = Field(default=0.0, description="Percentage of completed tickets")
    Username: Optional[str] = Field(None, description="The queried username")
    UserRole: Optional[str] = Field(None, description="User's role (Engineer/Supervisor/Admin)")
    ProjectFilter: Optional[str] = Field(None, description="Applied project filter")
    TeamFilter: Optional[str] = Field(None, description="Applied team filter")
    DateRange: Optional[str] = Field(None, description="Applied date range")
    Message: str = Field(default="Success", description="Status message")

    @property
    def has_sla_issues(self) -> bool:
        """Check if there are any SLA breaches."""
        return self.SLABreached > 0

    @property
    def is_on_track(self) -> bool:
        """Determine if user is on track with tickets.

        Criteria:
        - Completion rate >= 50%
        - No SLA breaches
        - Less than 3 tickets pending approval
        """
        return (
            self.CompletionRate >= 50.0
            and self.SLABreached == 0
            and self.PendingApproval < 3
        )

    def get_status_summary(self) -> str:
        """Generate a brief status summary."""
        if self.TotalTickets == 0:
            return "No tickets found for the specified criteria."

        parts = []
        parts.append(f"{self.TotalTickets} total tickets")

        if self.CompletedTickets > 0:
            parts.append(f"{self.CompletedTickets} completed ({self.CompletionRate:.1f}%)")

        if self.OpenTickets > 0:
            parts.append(f"{self.OpenTickets} open")

        if self.SuspendedTickets > 0:
            parts.append(f"{self.SuspendedTickets} suspended")

        if self.SLABreached > 0:
            parts.append(f"{self.SLABreached} SLA breached")

        return ", ".join(parts)


def validate_ticket_summary(data: dict) -> TicketSummary:
    """Validate raw database response and convert to TicketSummary.

    Args:
        data: Raw dictionary from database stored procedure

    Returns:
        TicketSummary: Validated and typed model instance

    Raises:
        ValidationError: If data doesn't match expected schema
    """
    return TicketSummary(**data)
