"""Spec §8.1: personal and government content must stay in separate
indexes so a medical-document question can't accidentally surface
government web content, and vice versa.
"""
from app.memory.retrieval import search_documents
from app.memory.store import index_document, index_government_page


def test_search_documents_never_returns_government_content(db):
    index_document(db, document_id=1, doc_type="LAB_REPORT", pages=["Hemoglobin 11.2 low result"])
    index_government_page(
        db, content="Hemoglobin pricing circular unrelated government text",
        source_url="https://www.telangana.gov.in/x", title="X",
        department=None, pub_date=None, retrieved_at="2026-01-01",
    )

    results = search_documents(db, "Hemoglobin")

    assert len(results) == 1
    assert results[0]["doc_type"] == "LAB_REPORT"
