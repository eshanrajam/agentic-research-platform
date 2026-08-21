"""Lightweight persistent vector store for RAG, backed by Chroma.

Kept deliberately simple (single collection, OpenAI-compatible embeddings) so
it's easy to swap for Azure AI Search in production - see README > Roadmap.
"""
from __future__ import annotations

from ..config import settings

_COLLECTION_NAME = "knowledge_base"
_client = None
_collection = None


def _embedding_function():
    from chromadb.utils import embedding_functions

    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=settings.azure_openai_api_key,
            api_base=settings.azure_openai_endpoint,
            api_type="azure",
            model_name=settings.azure_openai_embedding_deployment,
        )
    if settings.openai_api_key:
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=settings.openai_api_key,
            model_name="text-embedding-3-small",
        )
    raise RuntimeError(
        "Configure OPENAI_API_KEY or AZURE_OPENAI_API_KEY/AZURE_OPENAI_ENDPOINT to use the knowledge base."
    )


def get_collection():
    """Return the (lazily created) persistent Chroma collection."""
    global _client, _collection
    if _collection is None:
        import chromadb

        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        _collection = _client.get_or_create_collection(_COLLECTION_NAME, embedding_function=_embedding_function())
    return _collection


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Naive fixed-size sliding-window chunking - good enough for a demo knowledge base."""
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks


def ingest_text(text: str, source: str) -> int:
    """Chunk, embed, and upsert `text` into the knowledge base. Returns chunk count."""
    collection = get_collection()
    chunks = chunk_text(text)
    if not chunks:
        return 0
    ids = [f"{source}-{i}" for i in range(len(chunks))]
    collection.upsert(documents=chunks, ids=ids, metadatas=[{"source": source} for _ in chunks])
    return len(chunks)


def search(query: str, k: int = 4) -> list[str]:
    """Return the top-k most relevant chunks for `query`, or [] if the KB is empty."""
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []
    results = collection.query(query_texts=[query], n_results=min(k, count))
    documents = results.get("documents") or []
    return documents[0] if documents else []
