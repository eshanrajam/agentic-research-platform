"""Tests for the RAG vector store, using a fake embedding function so no API key is needed."""
from __future__ import annotations

from dataclasses import replace

import pytest

from agentic_platform.rag import vector_store


class _FakeEmbeddingFunction:
    """Deterministic bag-of-words embedding, good enough to test add/search wiring."""

    def __call__(self, input):  # noqa: A002 - matches chromadb's EmbeddingFunction protocol
        return [[float(len(text)), float(text.count(" ") + 1)] for text in input]

    def embed_query(self, input):  # noqa: A002 - chromadb calls this separately for query-time embedding
        return self(input)

    @staticmethod
    def name() -> str:
        return "fake"


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
    monkeypatch.setattr(vector_store, "settings", replace(vector_store.settings, chroma_persist_dir=str(tmp_path)))
    monkeypatch.setattr(vector_store, "_embedding_function", lambda: _FakeEmbeddingFunction())
    yield


def test_chunk_text_splits_long_text():
    chunks = vector_store.chunk_text("a" * 2000, chunk_size=800, overlap=100)
    assert len(chunks) > 1
    assert all(chunks)


def test_chunk_text_rejects_bad_overlap():
    with pytest.raises(ValueError):
        vector_store.chunk_text("hello", chunk_size=10, overlap=10)


def test_search_returns_empty_when_kb_is_empty():
    assert vector_store.search("anything") == []


def test_ingest_then_search_round_trip():
    count = vector_store.ingest_text("Contoso's Q3 revenue was $42 million.", source="q3-report")
    assert count >= 1

    results = vector_store.search("Contoso revenue")
    assert results, "expected at least one matching chunk"
    assert "Contoso" in results[0]
