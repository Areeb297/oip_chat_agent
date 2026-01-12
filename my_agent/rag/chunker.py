"""Document chunking strategies for RAG"""
from typing import List
from ..models import Document, DocumentChunk, ChunkMetadata
from ..config import RAGConfig


class SemanticChunker:
    """Split documents into semantic chunks with overlap"""

    def __init__(
        self,
        chunk_size: int = RAGConfig.CHUNK_SIZE,
        overlap: int = RAGConfig.CHUNK_OVERLAP,
    ):
        """Initialize chunker.

        Args:
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks in characters
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(self, document: Document) -> List[DocumentChunk]:
        """Chunk a document into semantic pieces.

        Args:
            document: Document to chunk

        Returns:
            List of DocumentChunk objects
        """
        text = document.content
        source = document.source

        # Split by paragraphs first (respects semantic boundaries)
        paragraphs = self._split_paragraphs(text)

        # Merge small paragraphs, split large ones
        raw_chunks = self._merge_and_split(paragraphs)

        # Create DocumentChunk objects
        total_chunks = len(raw_chunks)
        chunks = []

        for i, chunk_text in enumerate(raw_chunks):
            chunk = DocumentChunk(
                text=chunk_text.strip(),
                metadata=ChunkMetadata(
                    source=source,
                    chunk_index=i,
                    total_chunks=total_chunks,
                    doc_type=document.doc_type,
                ),
            )
            chunks.append(chunk)

        return chunks

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        # Split on double newlines (paragraph breaks)
        paragraphs = text.split("\n\n")
        # Filter empty paragraphs
        return [p.strip() for p in paragraphs if p.strip()]

    def _merge_and_split(self, paragraphs: List[str]) -> List[str]:
        """Merge small paragraphs and split large ones."""
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            # If paragraph alone exceeds chunk size, split it
            if len(para) > self.chunk_size:
                # Save current chunk if exists
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""

                # Split large paragraph with overlap
                para_chunks = self._split_with_overlap(para)
                chunks.extend(para_chunks)

            # If adding paragraph exceeds chunk size, save current and start new
            elif len(current_chunk) + len(para) + 2 > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para

            # Otherwise, add to current chunk
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _split_with_overlap(self, text: str) -> List[str]:
        """Split long text with overlap."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # If not at end, try to break at sentence boundary
            if end < len(text):
                # Look for sentence end near chunk boundary
                for sep in [". ", "! ", "? ", "\n"]:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start + self.chunk_size // 2:
                        end = last_sep + 1
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start with overlap
            start = end - self.overlap

        return chunks

    def chunk_documents(self, documents: List[Document]) -> List[DocumentChunk]:
        """Chunk multiple documents.

        Args:
            documents: List of documents to chunk

        Returns:
            List of all chunks from all documents
        """
        all_chunks = []
        for doc in documents:
            chunks = self.chunk_document(doc)
            all_chunks.extend(chunks)
        return all_chunks
