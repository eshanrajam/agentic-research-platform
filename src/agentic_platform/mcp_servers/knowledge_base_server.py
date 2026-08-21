"""MCP server exposing the RAG knowledge base to the Analyst agent."""
from __future__ import annotations

from mcp.server import MCPServer

from agentic_platform.rag import vector_store

mcp = MCPServer("knowledge-base")


@mcp.tool()
def search_knowledge_base(query: str, k: int = 4) -> str:
    """Search the ingested-document knowledge base and return the most relevant chunks."""
    try:
        chunks = vector_store.search(query, k=k)
    except RuntimeError as exc:
        return f"Knowledge base unavailable: {exc}"
    if not chunks:
        return "No relevant documents found in the knowledge base."
    return "\n\n---\n\n".join(chunks)


@mcp.tool()
def ingest_text(text: str, source: str = "manual") -> str:
    """Chunk, embed, and add a piece of text to the knowledge base for future retrieval."""
    try:
        count = vector_store.ingest_text(text, source=source)
    except RuntimeError as exc:
        return f"Ingestion failed: {exc}"
    return f"Ingested {count} chunk(s) from source '{source}'."


if __name__ == "__main__":
    mcp.run()
