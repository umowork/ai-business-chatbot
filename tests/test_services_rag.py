"""
Tests for RAG service — document parsing, text splitting, vector store.
"""

import os
import tempfile

import numpy as np
import pytest

from services.rag import (
    DocumentChunk,
    EmbeddingService,
    PDFParser,
    RAGEngine,
    SimpleVectorStore,
    split_text_into_chunks,
)


class TestTextSplitting:
    """Test text splitting into chunks."""

    def test_split_empty_text(self):
        chunks = split_text_into_chunks("")
        assert chunks == []

    def test_split_short_text(self):
        chunks = split_text_into_chunks("Hello world")
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_split_long_text(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three.\n\nParagraph four."
        chunks = split_text_into_chunks(text, chunk_size=20, chunk_overlap=0)
        assert len(chunks) >= 2

    def test_split_with_overlap(self):
        text = "First paragraph content here.\n\nSecond paragraph here.\n\nThird paragraph."
        chunks = split_text_into_chunks(text, chunk_size=50, chunk_overlap=20)
        assert len(chunks) >= 2


class TestDocumentChunk:
    """Test DocumentChunk model."""

    def test_create_chunk(self):
        chunk = DocumentChunk(
            text="Test content",
            source="test.pdf",
            page=1,
        )
        assert chunk.text == "Test content"
        assert chunk.source == "test.pdf"
        assert chunk.page == 1
        assert chunk.chunk_id is not None

    def test_chunk_to_dict(self):
        chunk = DocumentChunk(
            text="A" * 300,  # Long text
            source="doc.pdf",
            page=5,
        )
        d = chunk.to_dict()
        assert d["source"] == "doc.pdf"
        assert d["page"] == 5
        # Should be truncated
        assert len(d["text"]) <= 203  # 200 + "..."

    def test_chunk_with_embedding(self):
        chunk = DocumentChunk(
            text="Test",
            source="test.pdf",
            embedding=np.array([0.1, 0.2, 0.3]),
        )
        assert chunk.embedding is not None
        assert chunk.embedding.shape == (3,)


class TestSimpleVectorStore:
    """Test in-memory vector store."""

    @pytest.fixture
    def store(self):
        return SimpleVectorStore()

    @pytest.fixture
    def sample_chunks(self):
        return [
            DocumentChunk(
                text="Document about AI",
                source="ai_doc.pdf",
                embedding=np.array([1.0, 0.0, 0.0]),
            ),
            DocumentChunk(
                text="Document about business",
                source="business_doc.pdf",
                embedding=np.array([0.0, 1.0, 0.0]),
            ),
            DocumentChunk(
                text="Document about CRM",
                source="crm_doc.pdf",
                embedding=np.array([0.0, 0.0, 1.0]),
            ),
        ]

    def test_empty_store_search(self, store):
        query = np.array([1.0, 0.0, 0.0])
        results = store.search(query, top_k=3)
        assert results == []

    def test_add_and_search(self, store, sample_chunks):
        store.add_chunks(sample_chunks)

        # Search for AI document
        query = np.array([1.0, 0.0, 0.0])
        results = store.search(query, top_k=1)
        assert len(results) == 1
        assert results[0][0].text == "Document about AI"
        assert results[0][1] > 0.9

    def test_search_multiple_results(self, store, sample_chunks):
        store.add_chunks(sample_chunks)

        # Query with decent similarity to all 3 basis vectors
        query = np.array([0.5, 0.5, 0.5])
        results = store.search(query, top_k=3)
        assert len(results) == 3

    def test_search_min_score_filter(self, store, sample_chunks):
        store.add_chunks(sample_chunks)

        # Very different query
        query = np.array([-1.0, -1.0, -1.0])
        results = store.search(query, top_k=3, min_score=0.9)
        assert len(results) == 0

    def test_save_and_load(self, store, sample_chunks):
        store.add_chunks(sample_chunks)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = f.name
            store.save(path)

        # New store should load the data
        new_store = SimpleVectorStore()
        count = new_store.load(path)
        assert count == 3

        # Search should work
        query = np.array([1.0, 0.0, 0.0])
        results = new_store.search(query, top_k=1)
        assert len(results) == 1

        os.unlink(path)

    def test_load_nonexistent(self):
        store = SimpleVectorStore()
        count = store.load("/tmp/nonexistent_file.pkl")
        assert count == 0


class TestEmbeddingService:
    """Test embedding service in mock mode."""

    @pytest.mark.asyncio
    async def test_embed_text_mock_mode(self, test_config):
        embedder = EmbeddingService(test_config)
        embedding = await embedder.embed_text("Test text")
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape[0] == 384  # Default size in mock mode


class TestPDFParser:
    """Test PDF parser with no actual PDF files."""

    def test_get_pdf_files_empty(self, tmpdir):
        parser = PDFParser(str(tmpdir))
        files = parser.get_pdf_files()
        assert files == []

    def test_parse_no_pdf_fallback(self, tmpdir):
        """Should handle missing PDF gracefully."""
        parser = PDFParser(str(tmpdir))
        chunks = parser.parse_pdf(
            tmpdir / "nonexistent.pdf"
        )
        assert chunks == []


class TestRAGEngine:
    """Test RAG Engine initialization."""

    @pytest.mark.asyncio
    async def test_initialize_empty(self, test_config):
        """RAG engine should initialize without error even with no documents."""
        engine = RAGEngine(test_config)
        await engine.initialize()
        assert engine._initialized is True

    @pytest.mark.asyncio
    async def test_retrieve_context_empty(self, test_config):
        """Retrieving context when no documents should return empty list."""
        engine = RAGEngine(test_config)
        results = await engine.retrieve_context("test query")
        assert results == []

    def test_format_context_empty(self, test_config):
        engine = RAGEngine(test_config)
        formatted = engine.format_context([])
        assert formatted == ""
