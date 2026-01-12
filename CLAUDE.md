# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Claude's Expertise

Claude is an expert in **Google Agent Development Kit (ADK)** - the SDK used to build this chatbot. This includes:
- Agent creation and orchestration using `google.adk.agents.Agent`
- Multi-agent architectures with sub-agents and tool delegation
- ADK tool definitions and function annotations
- Session management and conversation flows
- Integration with Gemini models via ADK
- ADK CLI commands (`adk web`, `adk run`, etc.)

Refer to ADK documentation and patterns when extending or debugging this project.

## Project Overview

This is the **Ebttikar OIP Assistant** - a RAG-powered chatbot for the Operations Intelligence Platform (OIP) built with Google Agent Development Kit (ADK). It uses FAISS for vector storage and OpenRouter for embeddings/LLM calls.

## Common Commands

```bash
# Activate virtual environment (Windows)
venv\Scripts\activate

# Activate virtual environment (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Ingest documents into FAISS vector store (required before first run)
python scripts/ingest_documents.py

# Run the agent web interface (specify folder to avoid listing other dirs)
adk web my_agent

# Test agent import
python -c "from my_agent import root_agent; print(root_agent)"
```

## Architecture

```
User Query
    │
    ▼
root_agent (Coordinator) ─── gemini-2.5-flash
    │
    ├──► greeter (Greetings Agent)
    │
    └──► oip_expert (RAG Q&A Agent)
              │
              ▼
         search_oip_documents (Tool)
              │
              ▼
         FAISS Index + OpenRouter Embeddings
```

### Agent Flow
- `root_agent`: Routes requests to sub-agents based on intent (greetings vs OIP questions)
- `greeter`: Handles greetings in English/Arabic
- `oip_expert`: Uses `search_oip_documents` tool to query FAISS, then answers based on retrieved context

### RAG Pipeline
1. Documents in `docs/` are chunked by `SemanticChunker` (500 chars, 50 overlap)
2. Embeddings generated via OpenRouter (`text-embedding-ada-002`)
3. Stored in FAISS index at `data/faiss_index/`
4. At query time: embed query → search FAISS → format context → LLM generates answer

## Key Files

| File | Purpose |
|------|---------|
| `my_agent/agent.py` | Agent definitions (root_agent, greeter, oip_expert) |
| `my_agent/config.py` | All configuration (paths, API keys, model settings) |
| `my_agent/tools/rag_tool.py` | `search_oip_documents` function for ADK |
| `my_agent/rag/vector_store.py` | FAISSVectorStore class |
| `my_agent/prompts/templates.py` | All prompt templates (Prompts class) |
| `scripts/ingest_documents.py` | CLI to ingest docs into FAISS |

## Configuration Reference

Edit `my_agent/config.py` to change:
- `RAGConfig.CHUNK_SIZE`: Characters per chunk (default 500)
- `RAGConfig.DEFAULT_TOP_K`: Number of results to retrieve (default 5)
- `RAGConfig.SIMILARITY_THRESHOLD`: Minimum score to include (default 0.3)
- `Models.GEMINI_FLASH`: Agent model (default gemini-2.5-flash)

## Adding New Documents

1. Add PDF/DOCX files to `docs/` folder
2. Re-run: `python scripts/ingest_documents.py`

## Adding New Tools

1. Create function in `my_agent/tools/new_tool.py`
2. Export from `my_agent/tools/__init__.py`
3. Add to agent's `tools=[]` list in `my_agent/agent.py`

## Environment Variables

Required in `.env`:
```
GOOGLE_API_KEY=...      # For Gemini agent models
OPENROUTER_API_KEY=...  # For embeddings and LLM calls
TAVILY_API_KEY=...      # Optional
```

## Dependencies

- **google-adk**: Agent orchestration framework
- **faiss-cpu**: Vector similarity search
- **PyMuPDF**: PDF text extraction
- **python-docx**: DOCX text extraction
- **pydantic**: Data validation
