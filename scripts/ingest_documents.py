#!/usr/bin/env python
"""Ingest documents from docs/ folder into FAISS vector store.

Usage:
    python scripts/ingest_documents.py

This script:
1. Loads all PDF/DOCX files from docs/
2. Chunks them into semantic pieces
3. Generates embeddings via OpenRouter
4. Stores in FAISS index
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from my_agent.config import DOCS_DIR, RAGConfig, validate_config
from my_agent.helpers.document_loader import DocumentLoader
from my_agent.helpers.openrouter import OpenRouterClient
from my_agent.rag.chunker import SemanticChunker
from my_agent.rag.vector_store import FAISSVectorStore


def main():
    """Main ingestion pipeline."""
    print("=" * 60)
    print("OIP Document Ingestion Pipeline")
    print("=" * 60)

    # Validate configuration
    print("\n[1/5] Validating configuration...")
    try:
        validate_config()
        print("  OK - API keys found")
    except ValueError as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    # Initialize components
    print("\n[2/5] Initializing components...")
    loader = DocumentLoader()
    chunker = SemanticChunker(
        chunk_size=RAGConfig.CHUNK_SIZE,
        overlap=RAGConfig.CHUNK_OVERLAP,
    )
    openrouter = OpenRouterClient()
    vector_store = FAISSVectorStore()
    vector_store.create_index()
    print(f"  Chunk size: {RAGConfig.CHUNK_SIZE} chars")
    print(f"  Overlap: {RAGConfig.CHUNK_OVERLAP} chars")

    # Load documents
    print(f"\n[3/5] Loading documents from {DOCS_DIR}...")
    if not DOCS_DIR.exists():
        print(f"  ERROR: Directory not found: {DOCS_DIR}")
        sys.exit(1)

    documents = loader.load_directory(str(DOCS_DIR))

    if not documents:
        print("  ERROR: No documents found in docs/ folder")
        sys.exit(1)

    print(f"  Loaded {len(documents)} documents")

    # Chunk documents
    print("\n[4/5] Chunking documents...")
    all_chunks = chunker.chunk_documents(documents)
    print(f"  Created {len(all_chunks)} chunks")

    # Generate embeddings
    print("\n[5/5] Generating embeddings...")
    batch_size = RAGConfig.EMBEDDING_BATCH_SIZE
    total_batches = (len(all_chunks) + batch_size - 1) // batch_size

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        texts = [chunk.text for chunk in batch]

        # Get embeddings from OpenRouter
        embeddings = openrouter.get_embeddings(texts)

        # Assign embeddings to chunks
        for chunk, embedding in zip(batch, embeddings):
            chunk.embedding = embedding

        batch_num = (i // batch_size) + 1
        print(f"  Batch {batch_num}/{total_batches} complete")

    # Add to vector store
    print("\nAdding to FAISS index...")
    count = vector_store.add_documents(all_chunks)
    print(f"  Added {count} vectors")

    # Save index
    print("\nSaving index...")
    vector_store.save()

    # Summary
    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)
    print(f"Documents processed: {len(documents)}")
    print(f"Chunks created: {len(all_chunks)}")
    print(f"Vectors stored: {vector_store.count}")
    print(f"Index location: {vector_store.index_path}")
    print("\nYou can now use the RAG tool in your agent!")


if __name__ == "__main__":
    main()
