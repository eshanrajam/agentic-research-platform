"""Bulk-ingest every .txt/.md file in data/docs/ into the RAG knowledge base.

Usage:
    python scripts/ingest_docs.py [directory]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentic_platform.rag import vector_store  # noqa: E402

_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"
_EXTENSIONS = {".txt", ".md"}


def main() -> None:
    docs_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_DIR
    files = [p for p in docs_dir.glob("**/*") if p.suffix.lower() in _EXTENSIONS]

    if not files:
        print(f"No .txt/.md files found in {docs_dir}")
        return

    total_chunks = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        count = vector_store.ingest_text(text, source=path.name)
        total_chunks += count
        print(f"Ingested {path.name}: {count} chunk(s)")

    print(f"\nDone. {len(files)} file(s), {total_chunks} chunk(s) total.")


if __name__ == "__main__":
    main()
