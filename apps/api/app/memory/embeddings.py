"""Placeholder for semantic search (spec §8.2: "Later, embeddings can be
added behind the same retrieval interface if semantic search improves the
experience"). Not needed for the SQLite FTS5 MVP — kept as an explicit stub
so the seam is visible rather than silently absent.
"""


def embed(text: str) -> list[float]:
    raise NotImplementedError(
        "Embeddings are not part of the MVP. Start with FTS5 "
        "(app/memory/retrieval.py); add a vector index here only if "
        "keyword search proves insufficient."
    )
