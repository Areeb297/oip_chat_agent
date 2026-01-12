# Ebttikar OIP RAG System - Implementation Plan

## Overview

Build a RAG (Retrieval-Augmented Generation) system for the Ebttikar Operations Intelligence Platform (OIP) using:
- **Google ADK** for agent orchestration
- **FAISS** for local vector storage
- **OpenRouter** for embeddings and LLM calls
- **Pydantic** for data validation
- **Python classes** for clean architecture

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Query                               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Google ADK Agent                              │
│                   (OIP Assistant Agent)                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  System Prompt: Ebttikar OIP Expert                      │    │
│  │  - Answer questions about OIP platform                   │    │
│  │  - Generate charts from data                             │    │
│  │  - Use RAG tool for document retrieval                   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
        ┌─────────────────┐      ┌─────────────────┐
        │   RAG Tool      │      │  Future Tools   │
        │  (FAISS Search) │      │  (Charts, etc.) │
        └─────────────────┘      └─────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FAISS Vector Store                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Documents: SOW.pdf, Ebttikar_OIP_doc.docx               │    │
│  │  Embeddings: OpenRouter text-embedding-ada-002           │    │
│  │  Index: IndexFlatL2 (exact search for small corpus)      │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
Ticketing Chatbot/
├── .env                          # API keys (existing)
├── docs/                         # Knowledge base documents
│   ├── SOW.pdf
│   └── Ebttikar_OIP_doc.docx
├── my_agent/
│   ├── __init__.py
│   ├── agent.py                  # Main OIP agent (to be updated)
│   ├── config.py                 # Configuration and settings
│   ├── models.py                 # Pydantic models
│   ├── helpers/
│   │   ├── __init__.py
│   │   ├── openrouter.py         # OpenRouter helper functions
│   │   └── document_loader.py    # PDF/DOCX loaders
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── embeddings.py         # Embedding generation
│   │   ├── vector_store.py       # FAISS operations
│   │   ├── chunker.py            # Document chunking
│   │   └── retriever.py          # RAG retrieval logic
│   └── tools/
│       ├── __init__.py
│       └── rag_tool.py           # RAG tool for ADK agent
├── data/
│   └── faiss_index/              # Persisted FAISS index
│       ├── index.faiss
│       └── metadata.json
├── scripts/
│   └── ingest_documents.py       # CLI script to ingest docs
├── requirements.txt
└── IMPLEMENTATION_PLAN.md
```

---

## Component Details

### 1. Pydantic Models (`my_agent/models.py`)

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class ChunkMetadata(BaseModel):
    """Metadata for a document chunk"""
    source: str = Field(..., description="Source file name")
    page: Optional[int] = Field(None, description="Page number if applicable")
    chunk_index: int = Field(..., description="Index of chunk in document")
    total_chunks: int = Field(..., description="Total chunks in document")

class DocumentChunk(BaseModel):
    """A chunk of text with metadata"""
    text: str = Field(..., description="The chunk text content")
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")

class SearchResult(BaseModel):
    """Result from RAG search"""
    text: str
    score: float
    metadata: ChunkMetadata

class RAGResponse(BaseModel):
    """Response from RAG tool"""
    query: str
    results: List[SearchResult]
    context: str = Field(..., description="Combined context for LLM")

class EmbeddingRequest(BaseModel):
    """Request for embedding generation"""
    texts: List[str]
    model: str = "openai/text-embedding-ada-002"

class LLMRequest(BaseModel):
    """Request for LLM completion"""
    system_prompt: str
    user_prompt: str
    model: str = "openai/gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 1000
```

---

### 2. OpenRouter Helper Functions (`my_agent/helpers/openrouter.py`)

```python
import requests
import os
from typing import List, Optional
from ..models import EmbeddingRequest, LLMRequest

class OpenRouterClient:
    """Helper class for OpenRouter API calls"""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ebttikar.com",
            "X-Title": "Ebttikar OIP Assistant"
        }

    def get_embeddings(self, texts: List[str], model: str = "openai/text-embedding-ada-002") -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        response = requests.post(
            f"{self.BASE_URL}/embeddings",
            headers=self.headers,
            json={
                "model": model,
                "input": texts,
                "encoding_format": "float"
            }
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]

    def get_embedding(self, text: str, model: str = "openai/text-embedding-ada-002") -> List[float]:
        """Generate embedding for a single text"""
        return self.get_embeddings([text], model)[0]

    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "openai/gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Get chat completion from OpenRouter"""
        response = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers=self.headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
```

---

### 3. Document Loaders (`my_agent/helpers/document_loader.py`)

```python
from pathlib import Path
from typing import List
import fitz  # PyMuPDF for PDFs
from docx import Document  # python-docx for DOCX

class DocumentLoader:
    """Load text from various document formats"""

    @staticmethod
    def load_pdf(file_path: str) -> str:
        """Extract text from PDF"""
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        return text.strip()

    @staticmethod
    def load_docx(file_path: str) -> str:
        """Extract text from DOCX"""
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    @classmethod
    def load(cls, file_path: str) -> str:
        """Load document based on extension"""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            return cls.load_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            return cls.load_docx(file_path)
        elif ext == ".txt":
            return path.read_text(encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file type: {ext}")
```

---

### 4. Document Chunker (`my_agent/rag/chunker.py`)

```python
from typing import List
from ..models import DocumentChunk, ChunkMetadata

class SemanticChunker:
    """Chunk documents with semantic awareness"""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size  # characters
        self.overlap = overlap

    def chunk_text(self, text: str, source: str) -> List[DocumentChunk]:
        """Split text into overlapping chunks"""
        chunks = []

        # Split by paragraphs first
        paragraphs = text.split("\n\n")
        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            if len(current_chunk) + len(para) < self.chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # Convert to DocumentChunk objects
        total_chunks = len(chunks)
        return [
            DocumentChunk(
                text=chunk,
                metadata=ChunkMetadata(
                    source=source,
                    chunk_index=i,
                    total_chunks=total_chunks
                )
            )
            for i, chunk in enumerate(chunks)
        ]
```

---

### 5. FAISS Vector Store (`my_agent/rag/vector_store.py`)

```python
import faiss
import numpy as np
import json
from pathlib import Path
from typing import List, Tuple, Optional
from ..models import DocumentChunk, SearchResult, ChunkMetadata

class FAISSVectorStore:
    """FAISS-based vector storage and retrieval"""

    def __init__(self, dimension: int = 1536, index_path: str = "data/faiss_index"):
        self.dimension = dimension  # ada-002 produces 1536-dim vectors
        self.index_path = Path(index_path)
        self.index: Optional[faiss.Index] = None
        self.metadata: List[dict] = []  # Store chunk metadata
        self.texts: List[str] = []  # Store original texts

    def create_index(self):
        """Create a new FAISS index"""
        # IndexFlatL2 for exact search (good for small datasets)
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata = []
        self.texts = []

    def add_documents(self, chunks: List[DocumentChunk]):
        """Add document chunks with embeddings to index"""
        if self.index is None:
            self.create_index()

        embeddings = []
        for chunk in chunks:
            if chunk.embedding is None:
                raise ValueError("Chunk must have embedding")
            embeddings.append(chunk.embedding)
            self.metadata.append(chunk.metadata.model_dump())
            self.texts.append(chunk.text)

        # Convert to numpy array and add to index
        vectors = np.array(embeddings, dtype=np.float32)
        self.index.add(vectors)

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[SearchResult]:
        """Search for similar documents"""
        if self.index is None or self.index.ntotal == 0:
            return []

        query_vector = np.array([query_embedding], dtype=np.float32)
        distances, indices = self.index.search(query_vector, top_k)

        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx >= 0:  # Valid index
                results.append(SearchResult(
                    text=self.texts[idx],
                    score=float(1 / (1 + dist)),  # Convert distance to similarity
                    metadata=ChunkMetadata(**self.metadata[idx])
                ))

        return results

    def save(self):
        """Persist index to disk"""
        self.index_path.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        faiss.write_index(self.index, str(self.index_path / "index.faiss"))

        # Save metadata and texts
        with open(self.index_path / "metadata.json", "w") as f:
            json.dump({
                "metadata": self.metadata,
                "texts": self.texts
            }, f)

    def load(self) -> bool:
        """Load index from disk"""
        index_file = self.index_path / "index.faiss"
        metadata_file = self.index_path / "metadata.json"

        if not index_file.exists() or not metadata_file.exists():
            return False

        self.index = faiss.read_index(str(index_file))

        with open(metadata_file, "r") as f:
            data = json.load(f)
            self.metadata = data["metadata"]
            self.texts = data["texts"]

        return True
```

---

### 6. RAG Tool for ADK Agent (`my_agent/tools/rag_tool.py`)

```python
from typing import List
from ..rag.vector_store import FAISSVectorStore
from ..helpers.openrouter import OpenRouterClient
from ..models import RAGResponse, SearchResult

# Global instances (initialized on first use)
_vector_store: FAISSVectorStore = None
_openrouter: OpenRouterClient = None

def _get_vector_store() -> FAISSVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = FAISSVectorStore()
        if not _vector_store.load():
            raise RuntimeError("FAISS index not found. Run ingest_documents.py first.")
    return _vector_store

def _get_openrouter() -> OpenRouterClient:
    global _openrouter
    if _openrouter is None:
        _openrouter = OpenRouterClient()
    return _openrouter

def search_oip_documents(query: str, top_k: int = 5) -> dict:
    """Search the Ebttikar OIP knowledge base for relevant information.

    Args:
        query: The search query about OIP platform
        top_k: Number of results to return (default 5)

    Returns:
        dict with search results including text chunks and relevance scores
    """
    try:
        vector_store = _get_vector_store()
        openrouter = _get_openrouter()

        # Generate query embedding
        query_embedding = openrouter.get_embedding(query)

        # Search FAISS index
        results = vector_store.search(query_embedding, top_k)

        if not results:
            return {
                "status": "no_results",
                "query": query,
                "message": "No relevant documents found for this query."
            }

        # Format results
        formatted_results = []
        context_parts = []

        for i, result in enumerate(results, 1):
            formatted_results.append({
                "rank": i,
                "text": result.text,
                "score": result.score,
                "source": result.metadata.source
            })
            context_parts.append(f"[Source: {result.metadata.source}]\n{result.text}")

        return {
            "status": "success",
            "query": query,
            "results": formatted_results,
            "context": "\n\n---\n\n".join(context_parts)
        }

    except Exception as e:
        return {
            "status": "error",
            "query": query,
            "error": str(e)
        }
```

---

### 7. Main OIP Agent (`my_agent/agent.py` - Updated)

```python
from google.adk.agents import LlmAgent
from .tools.rag_tool import search_oip_documents

# System prompt for OIP Assistant
OIP_SYSTEM_PROMPT = """You are an expert assistant for the Ebttikar Operations Intelligence Platform (OIP).

Your capabilities:
1. Answer questions about the OIP platform features, architecture, and functionality
2. Explain the Statement of Work (SOW) details for OIP implementation
3. Help users understand OIP workflows and integrations
4. Provide technical guidance on OIP usage

Guidelines:
- ALWAYS use the search_oip_documents tool to retrieve relevant information before answering
- Base your answers ONLY on the retrieved documents - do not make up information
- If the documents don't contain relevant information, say so honestly
- Cite the source document when providing information
- Be concise but thorough in your explanations
- Support both English and Arabic queries

When you don't know something or the documents don't have the answer, be honest and say:
"I don't have specific information about that in the OIP documentation."
"""

# Main OIP Assistant Agent
root_agent = LlmAgent(
    name="oip_assistant",
    model="gemini-2.5-flash",
    instruction=OIP_SYSTEM_PROMPT,
    description="Ebttikar OIP platform expert assistant with document retrieval capabilities",
    tools=[search_oip_documents]
)
```

---

### 8. Document Ingestion Script (`scripts/ingest_documents.py`)

```python
#!/usr/bin/env python
"""Ingest documents into FAISS vector store"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from my_agent.helpers.document_loader import DocumentLoader
from my_agent.helpers.openrouter import OpenRouterClient
from my_agent.rag.chunker import SemanticChunker
from my_agent.rag.vector_store import FAISSVectorStore

def main():
    docs_dir = Path("docs")

    # Initialize components
    loader = DocumentLoader()
    chunker = SemanticChunker(chunk_size=500, overlap=50)
    openrouter = OpenRouterClient()
    vector_store = FAISSVectorStore()
    vector_store.create_index()

    # Process each document
    doc_files = list(docs_dir.glob("*.pdf")) + list(docs_dir.glob("*.docx"))

    print(f"Found {len(doc_files)} documents to process")

    all_chunks = []
    for doc_path in doc_files:
        print(f"\nProcessing: {doc_path.name}")

        # Load document
        text = loader.load(str(doc_path))
        print(f"  - Extracted {len(text)} characters")

        # Chunk document
        chunks = chunker.chunk_text(text, doc_path.name)
        print(f"  - Created {len(chunks)} chunks")

        all_chunks.extend(chunks)

    # Generate embeddings in batches
    print(f"\nGenerating embeddings for {len(all_chunks)} chunks...")
    batch_size = 20

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        texts = [chunk.text for chunk in batch]
        embeddings = openrouter.get_embeddings(texts)

        for chunk, embedding in zip(batch, embeddings):
            chunk.embedding = embedding

        print(f"  - Processed {min(i + batch_size, len(all_chunks))}/{len(all_chunks)}")

    # Add to vector store
    print("\nAdding to FAISS index...")
    vector_store.add_documents(all_chunks)

    # Save index
    print("Saving index...")
    vector_store.save()

    print(f"\nDone! Index saved with {vector_store.index.ntotal} vectors")

if __name__ == "__main__":
    main()
```

---

## Requirements (`requirements.txt`)

```
# Google ADK
google-adk>=0.1.0

# Vector Store
faiss-cpu>=1.7.4

# Document Processing
PyMuPDF>=1.23.0
python-docx>=1.0.0

# Data Validation
pydantic>=2.0.0

# HTTP Client
requests>=2.31.0

# Environment
python-dotenv>=1.0.0

# Utilities
numpy>=1.24.0
```

---

## Setup Instructions

### 1. Create Virtual Environment

```bash
cd "Ticketing Chatbot"
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Ingest Documents

```bash
python scripts/ingest_documents.py
```

### 4. Run Agent

```bash
adk web
# Or test directly:
python -c "from my_agent.agent import root_agent; print(root_agent)"
```

---

## Usage Example

```python
from my_agent.tools.rag_tool import search_oip_documents

# Search for information
result = search_oip_documents("What is the OIP platform?")
print(result["context"])

# Or use via the agent
from google.adk.runners import InMemoryRunner
from my_agent.agent import root_agent

runner = InMemoryRunner(agent=root_agent, app_name="oip_assistant")
# ... run queries through the agent
```

---

## Future Enhancements

1. **Hybrid Search**: Add BM25 keyword search alongside vector search
2. **Chart Generation Tool**: Add tool for generating visualizations from data
3. **Conversational Memory**: Add conversation history for context
4. **Multi-Agent Setup**: Specialized agents for different OIP modules
5. **Evaluation Framework**: Add metrics for retrieval quality

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| FAISS IndexFlatL2 | Exact search is fine for small document corpus |
| ada-002 embeddings | Good balance of quality and cost via OpenRouter |
| 500 char chunks | Reasonable size for semantic coherence |
| Pydantic models | Type safety and validation throughout |
| Separate ingestion script | Clean separation of concerns |
| Global singletons for tools | Efficient resource usage in ADK |
