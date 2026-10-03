"""Profile and medications setup (spec §7.1, §7.2) — the real-data
replacement for scripts/seed_demo_data.py's fictional seed.
"""
from fastapi.testclient import TestClient


def _client(db_path):
    from app.main import app
    return TestClient(app)


def test_get_profile_returns_null_when_none_exists(db_path):
    with _client(db_path) as client:
        resp = client.get("/api/profile")
        assert resp.status_code == 200
        assert resp.json() is None


def test_put_profile_creates_then_updates_the_same_singleton_row(db_path):
    with _client(db_path) as client:
        created = client.put("/api/profile", json={"name": "Dad", "preferred_language": "te-en"}).json()
        assert created["name"] == "Dad"
        first_id = created["id"]

        updated = client.put("/api/profile", json={"name": "Dad V2", "preferred_language": "en"}).json()
        assert updated["id"] == first_id  # same row, not a second profile
        assert updated["name"] == "Dad V2"

        fetched = client.get("/api/profile").json()
        assert fetched["name"] == "Dad V2"


def test_create_medication_appears_in_list(db_path):
    with _client(db_path) as client:
        created = client.post("/api/medications", json={
            "name": "Metformin", "instructions": "after food",
            "schedule": {"time": "08:30", "meal_dependency": "breakfast", "repeat_minutes": 30, "max_followups": 2},
        }).json()
        assert created["name"] == "Metformin"

        listed = client.get("/api/medications").json()
        assert len(listed) == 1
        assert listed[0]["time"] == "08:30"
        assert listed[0]["meal_dependency"] == "breakfast"


def test_update_medication_changes_schedule(db_path):
    with _client(db_path) as client:
        created = client.post("/api/medications", json={
            "name": "Amlodipine", "instructions": None,
            "schedule": {"time": "09:00", "meal_dependency": None, "repeat_minutes": 30, "max_followups": 2},
        }).json()

        client.put(f"/api/medications/{created['id']}", json={
            "name": "Amlodipine", "instructions": "once daily",
            "schedule": {"time": "10:00", "meal_dependency": None, "repeat_minutes": 20, "max_followups": 1},
        })

        listed = client.get("/api/medications").json()
        assert listed[0]["time"] == "10:00"
        assert listed[0]["repeat_minutes"] == 20


def test_deactivated_medication_is_soft_deleted_not_dropped(db_path):
    with _client(db_path) as client:
        created = client.post("/api/medications", json={
            "name": "Atorvastatin", "instructions": None,
            "schedule": {"time": "21:00", "meal_dependency": "dinner", "repeat_minutes": 30, "max_followups": 2},
        }).json()

        resp = client.delete(f"/api/medications/{created['id']}")
        assert resp.json()["active"] is False

        # Gone from the default (active-only) list...
        assert client.get("/api/medications").json() == []
        # ...but still exists as a row, not hard-deleted.
        import sqlite3
        from app.config import settings
        conn = sqlite3.connect(settings.db_path)
        row = conn.execute("SELECT active FROM medications WHERE id = ?", (created["id"],)).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 0


def test_update_medication_404_for_unknown_id(db_path):
    with _client(db_path) as client:
        resp = client.put("/api/medications/999", json={
            "name": "X", "instructions": None,
            "schedule": {"time": "09:00", "meal_dependency": None, "repeat_minutes": 30, "max_followups": 2},
        })
        assert resp.status_code == 404
