"""Read side of the personal memory index (spec §8, §9.2 search_personal_memory
/ search_documents tools). Structured profile facts and event history come
from relational tables; free-text document content comes from `personal_fts`
— two different retrieval paths behind one simple interface, as the memory
architecture calls for (§8: "three different memory types instead of one
undifferentiated vector store").
"""
import re
import sqlite3

from app.clock import today_str


def _fts_query(raw: str) -> str:
    """Turn free text into a safe FTS5 MATCH expression: quote each token
    so punctuation in the user's question can't break FTS5 query syntax.
    """
    terms = re.findall(r"[A-Za-z0-9]+", raw)
    if not terms:
        return '""'
    return " OR ".join(f'"{t}"' for t in terms)


def search_documents(db: sqlite3.Connection, query: str, limit: int = 5) -> list[dict]:
    rows = db.execute(
        """SELECT content, document_id, page, doc_type, rank
           FROM personal_fts WHERE personal_fts MATCH ? ORDER BY rank LIMIT ?""",
        (_fts_query(query), limit),
    ).fetchall()
    return [dict(row) for row in rows]


def search_personal_memory(db: sqlite3.Connection, query: str) -> dict:
    """Combines structured profile facts, recent event history, and
    matching document chunks — the three memory types from spec §8 — into
    one result the chat layer can hand to the LLM for phrasing.
    """
    profile = db.execute("SELECT * FROM profile LIMIT 1").fetchone()
    today = today_str()
    recent_events = db.execute(
        "SELECT * FROM events WHERE event_date = ? ORDER BY updated_at DESC", (today,)
    ).fetchall()
    documents = search_documents(db, query)

    return {
        "profile": dict(profile) if profile else None,
        "recent_events": [dict(r) for r in recent_events],
        "documents": documents,
    }
