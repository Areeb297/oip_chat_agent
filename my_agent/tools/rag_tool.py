"""RAG tool for Google ADK agent - searches OIP knowledge base"""
from typing import Optional
from ..rag.vector_store import FAISSVectorStore
from ..helpers.openrouter import OpenRouterClient
from ..prompts.templates import Prompts
from ..config import RAGConfig


# =============================================================================
# SINGLETON INSTANCES (lazy initialization)
# =============================================================================
_vector_store: Optional[FAISSVectorStore] = None
_openrouter: Optional[OpenRouterClient] = None


def _get_vector_store() -> FAISSVectorStore:
    """Get or create vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = FAISSVectorStore()
        if not _vector_store.load():
            raise RuntimeError(
                "FAISS index not found. Run: python scripts/ingest_documents.py"
            )
    return _vector_store


def _get_openrouter() -> OpenRouterClient:
    """Get or create OpenRouter client instance."""
    global _openrouter
    if _openrouter is None:
        _openrouter = OpenRouterClient()
    return _openrouter


# =============================================================================
# RAG TOOL FUNCTION (for Google ADK)
# =============================================================================

def search_oip_documents(query: str, top_k: int = 5) -> dict:
    """Search the Ebttikar OIP knowledge base for relevant information.

    Use this tool to find information about the Operations Intelligence Platform (OIP),
    including features, architecture, implementation details, and workflows.

    Args:
        query: The search query about OIP platform. Be specific for better results.
        top_k: Number of results to return (default 5, max 10)

    Returns:
        dict containing:
        - status: "success", "no_results", or "error"
        - query: The original query
        - results: List of matching documents with text, score, and source
        - context: Combined context string for answering questions
        - message: Status message (for no_results or error)
    """
    try:
        # Validate top_k
        top_k = min(max(1, top_k), 10)

        # Get instances
        vector_store = _get_vector_store()
        openrouter = _get_openrouter()

        # Generate query embedding
        query_embedding = openrouter.get_embedding(query)

        # Search FAISS index
        results = vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            threshold=RAGConfig.SIMILARITY_THRESHOLD,
        )

        # Handle no results
        if not results:
            return {
                "status": "no_results",
                "query": query,
                "results": [],
                "context": "",
                "message": Prompts.no_results_response(query),
            }

        # Format results for output
        formatted_results = []
        for i, result in enumerate(results, 1):
            formatted_results.append({
                "rank": i,
                "text": result.text,
                "score": round(result.score, 3),
                "source": result.metadata.source,
                "chunk_index": result.metadata.chunk_index,
            })

        # Use prompt template for structured context formatting
        context = Prompts.format_rag_context(
            results=formatted_results,
            query=query,
            include_scores=True,
        )

        return {
            "status": "success",
            "query": query,
            "results": formatted_results,
            "context": context,
            "message": f"Found {len(results)} relevant documents.",
        }

    except RuntimeError as e:
        # Index not found
        return {
            "status": "error",
            "query": query,
            "results": [],
            "context": "",
            "message": str(e),
        }

    except Exception as e:
        # Other errors
        return {
            "status": "error",
            "query": query,
            "results": [],
            "context": "",
            "message": Prompts.error_response("Search Error", str(e)),
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def reload_index() -> bool:
    """Reload the FAISS index from disk.

    Call this after re-ingesting documents.

    Returns:
        True if reload successful
    """
    global _vector_store
    _vector_store = FAISSVectorStore()
    return _vector_store.load()


def get_index_stats() -> dict:
    """Get statistics about the current index.

    Returns:
        dict with index statistics
    """
    try:
        vs = _get_vector_store()
        return {
            "status": "loaded",
            "total_vectors": vs.count,
            "dimension": vs.dimension,
            "index_path": str(vs.index_path),
        }
    except RuntimeError:
        return {
            "status": "not_loaded",
            "message": "Index not found. Run ingest_documents.py first.",
        }
