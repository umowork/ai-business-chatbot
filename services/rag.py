"""
RAG (Retrieval-Augmented Generation) Service.
Processes PDF documents, creates embeddings, and retrieves relevant context.
Uses lazy imports for heavy libraries.
"""

import hashlib
import logging
import os
import pickle
import re
from pathlib import Path
from typing import Any

import numpy as np

from config import Config

logger = logging.getLogger(__name__)


# ── Document chunk model ────────────────────────────────────────────────


class DocumentChunk:
    """A chunk of text from a document with metadata."""

    def __init__(
        self,
        text: str,
        source: str,
        page: int = 0,
        chunk_id: str = "",
        embedding: np.ndarray | None = None,
    ):
        self.text = text
        self.source = source
        self.page = page
        self.chunk_id = chunk_id or hashlib.md5(text.encode()).hexdigest()[:12]
        self.embedding = embedding

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text[:200] + "..." if len(self.text) > 200 else self.text,
            "source": self.source,
            "page": self.page,
            "chunk_id": self.chunk_id,
        }


# ── Text splitting ──────────────────────────────────────────────────────


def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """Split text into overlapping chunks by paragraphs and sentences."""
    if not text.strip():
        return []

    # Split by paragraphs first
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = ""
    current_size = 0

    for para in paragraphs:
        if current_size + len(para) <= chunk_size:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
            current_size += len(para)
        else:
            if current_chunk:
                chunks.append(current_chunk)

            # If a single paragraph is too long, split by sentences
            if len(para) > chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                temp_chunk = ""
                for sent in sentences:
                    if len(temp_chunk) + len(sent) <= chunk_size:
                        temp_chunk += (" " if temp_chunk else "") + sent
                    else:
                        if temp_chunk:
                            chunks.append(temp_chunk)
                        temp_chunk = sent
                if temp_chunk:
                    chunks.append(temp_chunk)
                current_chunk = ""
                current_size = 0
            else:
                current_chunk = para
                current_size = len(para)

    if current_chunk:
        chunks.append(current_chunk)

    # Apply overlap: add trailing sentences from previous chunk
    if chunk_overlap > 0 and len(chunks) > 1:
        overlapped = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                prev_chunk = chunks[i - 1]
                # Take the last ~overlap characters from prev chunk
                overlap_text = (
                prev_chunk[-chunk_overlap:] if len(prev_chunk) > chunk_overlap else prev_chunk
            )
                # Try to find a sentence boundary
                last_period = overlap_text.rfind(".")
                if last_period > 0:
                    overlap_text = overlap_text[last_period + 1:].strip()
                chunk = (overlap_text + "\n" + chunk).strip() if overlap_text else chunk
            overlapped.append(chunk)
        chunks = overlapped

    return chunks


# ── PDF Parser ──────────────────────────────────────────────────────────


class PDFParser:
    """Parse PDF documents into text chunks."""

    def __init__(self, documents_dir: str):
        self.documents_dir = Path(documents_dir)
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    def get_pdf_files(self) -> list[Path]:
        """Get all PDF files from the documents directory."""
        return list(self.documents_dir.glob("*.pdf")) + list(
            self.documents_dir.glob("*.PDF")
        )

    def parse_pdf(
        self, pdf_path: Path, chunk_size: int = 500, chunk_overlap: int = 50
    ) -> list[DocumentChunk]:
        """Parse a single PDF file into document chunks."""
        try:
            # Lazy import for PyMuPDF (fitz)
            import fitz
        except ImportError:
            logger.warning(
                "PyMuPDF not installed. Install with: pip install PyMuPDF"
            )
            return self._parse_pdf_fallback(pdf_path, chunk_size, chunk_overlap)

        chunks: list[DocumentChunk] = []
        try:
            doc = fitz.open(str(pdf_path))
            for page_num, page in enumerate(doc):
                text = page.get_text()
                if not text.strip():
                    continue
                page_chunks = split_text_into_chunks(text, chunk_size, chunk_overlap)
                for chunk_text in page_chunks:
                    chunk = DocumentChunk(
                        text=chunk_text,
                        source=pdf_path.name,
                        page=page_num + 1,
                    )
                    chunks.append(chunk)
            doc.close()
            logger.info(
                f"Parsed {pdf_path.name}: {len(chunks)} chunks from {len(doc)} pages"
            )
        except Exception as e:
            logger.error("Error parsing %s: %s", pdf_path, e)

        return chunks

    def _parse_pdf_fallback(
        self, pdf_path: Path, chunk_size: int, chunk_overlap: int
    ) -> list[DocumentChunk]:
        """Fallback parser using PyPDF2 or pdfminer."""
        chunks: list[DocumentChunk] = []
        try:
            from pdfminer.high_level import extract_text

            text = extract_text(str(pdf_path))
            text_chunks = split_text_into_chunks(text, chunk_size, chunk_overlap)
            for i, chunk_text in enumerate(text_chunks):
                chunk = DocumentChunk(
                    text=chunk_text,
                    source=pdf_path.name,
                    page=0,
                )
                chunks.append(chunk)
            logger.info(
                f"Parsed {pdf_path.name} (fallback): {len(chunks)} chunks"
            )
        except ImportError:
            logger.error(
                "No PDF parser available. Install PyMuPDF or pdfminer.six"
            )
        except Exception as e:
            logger.error("Fallback parse error for %s: %s", pdf_path, e)

        return chunks


# ── Embedding Service ───────────────────────────────────────────────────


class EmbeddingService:
    """Generate embeddings for text chunks using various providers."""

    def __init__(self, config: Config):
        self.config = config
        self._model = None

    def _get_openai_client(self):
        """Lazy import for openai."""
        import openai

        kwargs = {"api_key": self.config.openai_api_key}
        if self.config.openai_base_url:
            kwargs["base_url"] = self.config.openai_base_url
        return openai.OpenAI(**kwargs)

    async def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text string."""
        if self.config.mock_mode:
            # Return random embedding for mock mode
            return np.random.randn(384).astype(np.float32)

        if self.config.embedding_provider == "openai":
            client = self._get_openai_client()
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return np.array(response.data[0].embedding, dtype=np.float32)
        else:
            # Local sentence-transformers
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(
                        "all-MiniLM-L6-v2", device="cpu"
                    )
                except ImportError:
                    logger.error("sentence-transformers not installed")
                    return np.random.randn(384).astype(np.float32)

            return self._model.encode(text).astype(np.float32)

    async def embed_chunks(
        self, chunks: list[DocumentChunk]
    ) -> list[DocumentChunk]:
        """Generate embeddings for a list of chunks."""
        for chunk in chunks:
            chunk.embedding = await self.embed_text(chunk.text)
        return chunks


# ── Vector Store ────────────────────────────────────────────────────────


class SimpleVectorStore:
    """In-memory vector store with cosine similarity search."""

    def __init__(self):
        self.chunks: list[DocumentChunk] = []
        self._index_path: Path | None = None

    def add_chunks(self, chunks: list[DocumentChunk]):
        """Add chunks to the store."""
        self.chunks.extend(chunks)

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 3,
        min_score: float = 0.3,
    ) -> list[tuple[DocumentChunk, float]]:
        """Search for most similar chunks by cosine similarity."""
        if not self.chunks:
            return []

        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        scores: list[tuple[int, float]] = []

        for i, chunk in enumerate(self.chunks):
            if chunk.embedding is None:
                continue
            chunk_norm = chunk.embedding / (np.linalg.norm(chunk.embedding) + 1e-10)
            similarity = float(np.dot(query_norm, chunk_norm))
            scores.append((i, similarity))

        # Sort by similarity descending
        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scores[:top_k]:
            if score >= min_score:
                results.append((self.chunks[idx], score))

        return results

    def save(self, path: str):
        """Persist vector store to disk."""
        with open(path, "wb") as f:
            pickle.dump([c for c in self.chunks if c.embedding is not None], f)
        logger.info("Vector store saved to %s (%d chunks)", path, len(self.chunks))

    def load(self, path: str) -> int:
        """Load vector store from disk."""
        if not os.path.exists(path):
            logger.warning("Vector store not found at %s", path)
            return 0

        with open(path, "rb") as f:
            chunks = pickle.load(f)
        self.chunks = chunks
        logger.info("Vector store loaded from %s (%d chunks)", path, len(chunks))
        return len(chunks)


# ── RAG Engine ──────────────────────────────────────────────────────────


class RAGEngine:
    """
    Retrieval-Augmented Generation engine.
    Loads documents, creates embeddings, retrieves relevant context,
    and generates answers using an LLM.
    """

    def __init__(self, config: Config):
        self.config = config
        self.pdf_parser = PDFParser(config.documents_dir)
        self.embedder = EmbeddingService(config)
        self.vector_store = SimpleVectorStore()
        self._initialized = False

    async def initialize(self, force_reload: bool = False):
        """Load or build the document index."""
        index_path = os.path.join(self.config.documents_dir, ".vector_store.pkl")

        if not force_reload:
            loaded = self.vector_store.load(index_path)
            if loaded > 0:
                self._initialized = True
                logger.info("RAG initialized from cache (%d chunks)", loaded)
                return

        # Parse documents
        pdf_files = self.pdf_parser.get_pdf_files()
        all_chunks: list[DocumentChunk] = []
        for pdf_path in pdf_files:
            chunks = self.pdf_parser.parse_pdf(
                pdf_path, self.config.chunk_size, self.config.chunk_overlap
            )
            all_chunks.extend(chunks)

        if not all_chunks:
            logger.warning("No documents found for RAG")
            self._initialized = True
            return

        # Generate embeddings
        all_chunks = await self.embedder.embed_chunks(all_chunks)

        # Store
        self.vector_store.add_chunks(all_chunks)
        self.vector_store.save(index_path)
        self._initialized = True
        logger.info(
            f"RAG initialized with {len(all_chunks)} chunks from {len(pdf_files)} PDFs"
        )

    async def retrieve_context(
        self, query: str, top_k: int | None = None
    ) -> list[tuple[DocumentChunk, float]]:
        """Retrieve relevant document chunks for a query."""
        if not self._initialized:
            await self.initialize()

        query_embedding = await self.embedder.embed_text(query)
        top_k = top_k or self.config.top_k
        return self.vector_store.search(query_embedding, top_k=top_k)

    def format_context(self, results: list[tuple[DocumentChunk, float]]) -> str:
        """Format retrieved chunks into a context string for the LLM."""
        if not results:
            return ""

        parts = []
        for chunk, score in results:
            page = chunk.page
            src = chunk.source
            source_info = (
                f"[Источник: {src}, стр. {page}]" if page else f"[Источник: {src}]"
            )
            parts.append(f"{source_info}\n{chunk.text}")

        return "\n\n---\n\n".join(parts)

    async def answer_with_context(
        self,
        query: str,
        llm_provider: Any,  # BaseLLMProvider
        system_prompt: str | None = None,
    ) -> str:
        """Answer a query using RAG context."""
        results = await self.retrieve_context(query)
        context = self.format_context(results)

        if not context:
            # No context found, answer without RAG
            response = await llm_provider.chat_with_history(
                system_prompt=system_prompt or "Ты полезный AI-ассистент.",
                user_message=query,
            )
            return response.content

        rag_prompt = (
            f"{system_prompt or 'Ты полезный AI-ассистент компании.'}\n\n"
            f"Используй информацию из документов компании для ответа. "
            f"Если информации недостаточно, честно скажи об этом.\n\n"
            f"Контекст из документов:\n{context}"
        )

        response = await llm_provider.chat_with_history(
            system_prompt=rag_prompt,
            user_message=query,
        )
        return response.content
