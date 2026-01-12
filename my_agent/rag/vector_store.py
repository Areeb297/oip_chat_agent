"""FAISS vector store for document embeddings"""
import json
from pathlib import Path
from typing import List, Optional

import numpy as np

from ..models import DocumentChunk, SearchResult, ChunkMetadata
from ..config import FAISS_INDEX_DIR, RAGConfig


class FAISSVectorStore:
    """FAISS-based vector storage and retrieval"""

    def __init__(
        self,
        dimension: int = RAGConfig.EMBEDDING_DIMENSION,
        index_path: Optional[str] = None,
    ):
        """Initialize vector store.

        Args:
            dimension: Embedding vector dimension (1536 for ada-002)
            index_path: Path to store/load index
        """
        try:
            import faiss
            self.faiss = faiss
        except ImportError:
            raise ImportError("FAISS required: pip install faiss-cpu")

        self.dimension = dimension
        self.index_path = Path(index_path) if index_path else FAISS_INDEX_DIR

        self.index: Optional[object] = None
        self.metadata: List[dict] = []
        self.texts: List[str] = []

    def create_index(self) -> None:
        """Create a new empty FAISS index."""
        # IndexFlatL2 for exact search (good for small-medium datasets)
        self.index = self.faiss.IndexFlatL2(self.dimension)
        self.metadata = []
        self.texts = []

    def add_documents(self, chunks: List[DocumentChunk]) -> int:
        """Add document chunks with embeddings to index.

        Args:
            chunks: List of DocumentChunk objects with embeddings

        Returns:
            Number of documents added
        """
        if self.index is None:
            self.create_index()

        embeddings = []
        for chunk in chunks:
            if chunk.embedding is None:
                raise ValueError(
                    f"Chunk missing embedding: {chunk.text[:50]}..."
                )

            embeddings.append(chunk.embedding)
            self.metadata.append(chunk.metadata.model_dump())
            self.texts.append(chunk.text)

        # Convert to numpy and add to index
        if embeddings:
            vectors = np.array(embeddings, dtype=np.float32)
            self.index.add(vectors)

        return len(embeddings)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = RAGConfig.DEFAULT_TOP_K,
        threshold: float = RAGConfig.SIMILARITY_THRESHOLD,
    ) -> List[SearchResult]:
        """Search for similar documents.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            threshold: Minimum similarity score (0-1)

        Returns:
            List of SearchResult objects
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        # Search
        query_vector = np.array([query_embedding], dtype=np.float32)
        distances, indices = self.index.search(query_vector, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:  # Invalid index
                continue

            # Convert L2 distance to similarity score (0-1)
            # Lower distance = higher similarity
            score = 1 / (1 + float(dist))

            if score < threshold:
                continue

            results.append(
                SearchResult(
                    text=self.texts[idx],
                    score=score,
                    metadata=ChunkMetadata(**self.metadata[idx]),
                )
            )

        return results

    def save(self) -> None:
        """Persist index to disk."""
        if self.index is None:
            raise ValueError("No index to save")

        self.index_path.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        index_file = self.index_path / "index.faiss"
        self.faiss.write_index(self.index, str(index_file))

        # Save metadata and texts
        data_file = self.index_path / "metadata.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "metadata": self.metadata,
                    "texts": self.texts,
                    "dimension": self.dimension,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(f"Index saved to {self.index_path}")

    def load(self) -> bool:
        """Load index from disk.

        Returns:
            True if loaded successfully, False if files don't exist
        """
        index_file = self.index_path / "index.faiss"
        data_file = self.index_path / "metadata.json"

        if not index_file.exists() or not data_file.exists():
            return False

        # Load FAISS index
        self.index = self.faiss.read_index(str(index_file))

        # Load metadata and texts
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.metadata = data["metadata"]
            self.texts = data["texts"]
            self.dimension = data.get("dimension", self.dimension)

        print(f"Loaded index with {self.index.ntotal} vectors")
        return True

    @property
    def count(self) -> int:
        """Number of vectors in index."""
        return self.index.ntotal if self.index else 0

    def clear(self) -> None:
        """Clear the index."""
        self.create_index()
