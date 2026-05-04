"""Centralized configuration for the OIP Agent system"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# PATHS
# =============================================================================
BASE_DIR = Path(__file__).parent.parent
DOCS_DIR = BASE_DIR / "docs"
DATA_DIR = BASE_DIR / "data"
FAISS_INDEX_DIR = DATA_DIR / "faiss_index"

# =============================================================================
# API KEYS
# =============================================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# =============================================================================
# OPENROUTER SETTINGS
# =============================================================================
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://ebttikar.com",
    "X-Title": "Ebttikar OIP Assistant"
}

# =============================================================================
# MODEL SETTINGS
# =============================================================================

# Whether to use OpenRouter (via LiteLLM) instead of Google Gemini directly
USE_OPENROUTER = os.getenv("USE_OPENROUTER", "false").lower() == "true"

class Models:
    """Available models organized by provider and use case"""

    # -------------------------------------------------------------------------
    # EMBEDDINGS (via OpenRouter)
    # -------------------------------------------------------------------------
    EMBEDDING_ADA = "openai/text-embedding-ada-002"      # 1536 dims, good quality
    EMBEDDING_SMALL = "openai/text-embedding-3-small"    # 1536 dims, cheaper

    # -------------------------------------------------------------------------
    # LLMs — read from .env for easy switching (OpenRouter now → Ollama later)
    # -------------------------------------------------------------------------
    # Agent model: used by all ADK agents (root, ticket_analytics, etc.)
    DEFAULT_LLM = os.getenv("DEFAULT_LLM_MODEL", "qwen/qwen3-32b")
    FALLBACK_LLM = os.getenv("FALLBACK_LLM_MODEL", "x-ai/grok-4.3")
    # Helper model: used for titles, suggestions, prompt chaining
    HELPER_LLM = os.getenv("HELPER_LLM_MODEL", "openai/gpt-4o-mini")
    # Google native model (when USE_OPENROUTER=false)
    GOOGLE_AGENT = os.getenv("GOOGLE_AGENT_MODEL", "gemini-2.5-flash")


# =============================================================================
# CENTRALIZED AGENT MODEL (import this in all agent files)
# =============================================================================

def get_agent_model(use_fallback: bool = False):
    """Return the configured agent model for ADK agents.

    Args:
        use_fallback: If True, use FALLBACK_LLM_MODEL instead of DEFAULT_LLM_MODEL.
    """
    if USE_OPENROUTER:
        from google.adk.models.lite_llm import LiteLlm
        model_id = Models.FALLBACK_LLM if use_fallback else Models.DEFAULT_LLM
        return LiteLlm(model=f"openrouter/{model_id}")
    else:
        return Models.GOOGLE_AGENT

# Pre-built instance — all agents import this
AGENT_MODEL = get_agent_model()

_model_label = f"openrouter/{Models.DEFAULT_LLM}" if USE_OPENROUTER else Models.GOOGLE_AGENT
print(f"[config] Agent model: {_model_label}")


# =============================================================================
# DEFAULT MODEL CHOICES
# =============================================================================

# For embeddings (via OpenRouter)
DEFAULT_EMBEDDING_MODEL = Models.EMBEDDING_ADA

# For OpenRouter helper LLM calls (prompt chaining, summarization)
DEFAULT_HELPER_MODEL = Models.HELPER_LLM

# =============================================================================
# RAG SETTINGS
# =============================================================================
class RAGConfig:
    """RAG system configuration"""
    # Chunking
    CHUNK_SIZE = 500  # characters
    CHUNK_OVERLAP = 50

    # Embeddings
    EMBEDDING_DIMENSION = 1536  # ada-002 dimension
    EMBEDDING_BATCH_SIZE = 20

    # Retrieval
    DEFAULT_TOP_K = 5
    SIMILARITY_THRESHOLD = 0.3  # minimum similarity score

# =============================================================================
# AGENT SETTINGS
# =============================================================================
class AgentConfig:
    """Agent configuration"""
    MAX_TOKENS = 1000
    TEMPERATURE = 0.7


class SuggestionsConfig:
    """Follow-up suggestion generation settings"""
    ENABLED = True
    LLM_MODEL = Models.HELPER_LLM
    LLM_TIMEOUT = 3.0          # seconds before falling back to rule-based
    MAX_SUGGESTIONS = 4
    LLM_MAX_TOKENS = 150
    LLM_TEMPERATURE = 0.7
    USE_LLM = True             # False = rule-based only, skip LLM call

# =============================================================================
# VALIDATION
# =============================================================================
def validate_config():
    """Validate required configuration"""
    missing = []

    if not OPENROUTER_API_KEY:
        missing.append("OPENROUTER_API_KEY")
    if not GOOGLE_API_KEY:
        missing.append("GOOGLE_API_KEY")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return True
