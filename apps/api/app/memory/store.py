"""Writes into the personal document index (spec §8, §8.2). Kept
completely separate from `government_fts` so a medical-document question
can never retrieve government web content by accident (§8.1).
"""
import sqlite3


def index_document(db: sqlite3.Connection, document_id: int, doc_type: str, pages: list[str]) -> None:
    for page_number, page_text in enumerate(pages, start=1):
        cleaned = " ".join(page_text.split())
        if not cleaned:
            continue
        db.execute(
            "INSERT INTO personal_fts (content, document_id, page, doc_type) VALUES (?, ?, ?, ?)",
            (cleaned, document_id, page_number, doc_type),
        )


def index_government_page(db: sqlite3.Connection, content: str, source_url: str, title: str,
                           department: str | None, pub_date: str | None, retrieved_at: str) -> None:
    db.execute(
        """INSERT INTO government_fts (content, source_url, title, department, pub_date, retrieved_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (content, source_url, title, department, pub_date, retrieved_at),
    )
