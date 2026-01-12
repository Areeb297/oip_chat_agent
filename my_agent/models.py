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
