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
class Models:
    """Available models organized by provider and use case"""

    # -------------------------------------------------------------------------
    # EMBEDDINGS (via OpenRouter)
    # -------------------------------------------------------------------------
    EMBEDDING_ADA = "openai/text-embedding-ada-002"      # 1536 dims, good quality
    EMBEDDING_SMALL = "openai/text-embedding-3-small"    # 1536 dims, cheaper

    # -------------------------------------------------------------------------
    # LLMs via OpenRouter (for helper functions, prompt chaining)
    # -------------------------------------------------------------------------
    GPT4O_MINI = "openai/gpt-4o-mini"          # Fast, cheap, good for chaining
    GPT4O = "openai/gpt-4o"                    # Best quality
    CLAUDE_SONNET = "anthropic/claude-3.5-sonnet"

    # -------------------------------------------------------------------------
    # AGENT MODELS (for Google ADK - uses Google API directly)
    # -------------------------------------------------------------------------
    GEMINI_FLASH = "gemini-2.5-flash"          # Fast, good for agents
    GEMINI_PRO = "gemini-2.5-pro"              # Better reasoning


# =============================================================================
# DEFAULT MODEL CHOICES
# =============================================================================

# For embeddings (via OpenRouter)
DEFAULT_EMBEDDING_MODEL = Models.EMBEDDING_ADA

# For OpenRouter helper LLM calls (prompt chaining, summarization)
DEFAULT_LLM_MODEL = Models.GPT4O_MINI

# For Google ADK agents (uses Google API, not OpenRouter)
DEFAULT_AGENT_MODEL = Models.GEMINI_FLASH

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
