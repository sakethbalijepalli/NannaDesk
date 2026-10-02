"""Spec §14.2: 'NO SILENT SENDING' — sending requires an explicit,
user-stated confirm=true, enforced at the API boundary.
"""
from fastapi.testclient import TestClient


def _client(db_path):
    from app.main import app
    return TestClient(app)


def test_send_without_confirm_is_rejected(db_path):
    with _client(db_path) as client:
        draft = client.post("/api/emails/draft", json={
            "to_addr": "officer@example-tg.gov.in", "subject": "PF update", "body": "..."
        }).json()

        resp = client.post(f"/api/emails/{draft['id']}/send", json={"confirm": False})
        assert resp.status_code == 400

        stored = client.get(f"/api/emails/{draft['id']}").json()
        assert stored["status"] == "DRAFT"


def test_send_with_confirm_marks_draft_sent(db_path):
    with _client(db_path) as client:
        draft = client.post("/api/emails/draft", json={
            "to_addr": "officer@example-tg.gov.in", "subject": "PF update", "body": "..."
        }).json()

        resp = client.post(f"/api/emails/{draft['id']}/send", json={"confirm": True})
        assert resp.status_code == 200
        assert resp.json()["status"] == "SENT"


def test_sending_a_draft_sets_a_fresh_future_follow_up_date(db_path):
    # Regression: sending a follow-up on an already-overdue case must not
    # leave the old (past) follow_up_due_at in place — the next scheduler
    # tick would immediately flip it straight back to FOLLOW_UP_DUE
    # (caught during manual end-to-end testing).
    from datetime import datetime, timedelta, timezone
    with _client(db_path) as client:
        import sqlite3
        from app.config import settings
        conn = sqlite3.connect(settings.db_path)
        past = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        cur = conn.execute(
            "INSERT INTO cases (type, title, status, follow_up_due_at) VALUES ('PF', 'x', 'WAITING_FOR_REPLY', ?)",
            (past,),
        )
        case_id = cur.lastrowid
        conn.commit()
        conn.close()

        draft = client.post("/api/emails/draft", json={
            "to_addr": "x@example-tg.gov.in", "subject": "s", "body": "b", "case_id": case_id,
        }).json()
        client.post(f"/api/emails/{draft['id']}/send", json={"confirm": True})

        case = client.get("/api/cases").json()
        updated = next(c for c in case if c["id"] == case_id)
        assert updated["status"] == "WAITING_FOR_REPLY"
        due = datetime.fromisoformat(updated["follow_up_due_at"])
        assert due > datetime.now(due.tzinfo)


def test_cannot_send_the_same_draft_twice(db_path):
    with _client(db_path) as client:
        draft = client.post("/api/emails/draft", json={
            "to_addr": "x@example-tg.gov.in", "subject": "s", "body": "b"
        }).json()
        client.post(f"/api/emails/{draft['id']}/send", json={"confirm": True})

        resp = client.post(f"/api/emails/{draft['id']}/send", json={"confirm": True})
        assert resp.status_code == 409
