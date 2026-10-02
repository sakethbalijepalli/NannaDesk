"""End-to-end /api/chat tests through the real FastAPI app (LLM stubbed
unavailable by conftest's autouse fixture — these exercise the
deterministic paths and template fallbacks, not model phrasing).
"""
from fastapi.testclient import TestClient


def _client(db_path):
    from app.main import app
    return TestClient(app)


def _seed_profile_and_case(client):
    with client:
        import sqlite3
        from app.config import settings
        conn = sqlite3.connect(settings.db_path)
        conn.execute(
            "INSERT INTO profile (name, ddo_email, employee_code) VALUES ('Venkata Rao', 'ddo@example-tg.gov.in', 'E1')"
        )
        conn.execute(
            "INSERT INTO cases (type, title, status) VALUES ('PF', 'Pending PF payment', 'OPEN')"
        )
        conn.commit()
        conn.close()


def test_did_i_take_it_never_invents_a_confirmation(db_path):
    # Spec §19.1/§19.2: no confirmation on record -> exact status, never a
    # guess, and never routed to the free-form LLM.
    with _client(db_path) as client:
        import sqlite3
        from app.config import settings
        conn = sqlite3.connect(settings.db_path)
        cur = conn.execute("INSERT INTO medications (name, instructions, active) VALUES ('TestMed', '', 1)")
        med_id = cur.lastrowid
        conn.execute(
            "INSERT INTO medication_schedules (medication_id, time, repeat_minutes, max_followups) VALUES (?, '09:00', 30, 2)",
            (med_id,),
        )
        conn.commit()
        conn.close()

        resp = client.post("/api/chat", json={"message": "Did I take it?"})
        assert resp.status_code == 200
        body = resp.json()
        assert "not confirmed yet" in body["message"]
        assert "TestMed" in body["message"]


def test_write_to_officer_about_pf_creates_a_real_draft_tied_to_the_case(db_path):
    client = _client(db_path)
    _seed_profile_and_case(client)

    with client:
        resp = client.post("/api/chat", json={"message": "Write to my officer asking about my PF payment."})
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "needs_confirmation"
        draft_id = body["actions"][0]["payload"]["id"]

        draft = client.get(f"/api/emails/{draft_id}").json()
        assert draft["to_addr"] == "ddo@example-tg.gov.in"
        assert draft["case_id"] is not None


def test_urgent_symptom_escalates_instead_of_chatting(db_path):
    with _client(db_path) as client:
        resp = client.post("/api/chat", json={"message": "I have chest pain"})
        assert "108" in resp.json()["message"] or "doctor" in resp.json()["message"].lower()


def test_question_and_negation_phrases_never_record_a_confirmation(db_path):
    # Spec §16.3: "invent a medication confirmation" is one of the things
    # NannaDesk must never do. These four phrases all name a real,
    # pending medicine alongside a confirming verb somewhere in the
    # sentence — none of them are an actual confirmation.
    with _client(db_path) as client:
        import sqlite3
        from app.config import settings
        conn = sqlite3.connect(settings.db_path)
        cur = conn.execute("INSERT INTO medications (name, instructions, active) VALUES ('Metformin', '', 1)")
        med_id = cur.lastrowid
        conn.execute(
            "INSERT INTO medication_schedules (medication_id, time, repeat_minutes, max_followups) VALUES (?, '09:00', 30, 2)",
            (med_id,),
        )
        conn.commit()
        conn.close()

        for phrase in [
            "Have I taken Metformin?",
            "I haven't taken Metformin yet",
            "I had lunch but not Metformin",
            "Metformin had side effects",
        ]:
            client.post("/api/chat", json={"message": phrase})

        conn = sqlite3.connect(settings.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT status FROM events WHERE kind = 'MEDICATION'").fetchone()
        conn.close()
        assert row["status"] == "SCHEDULED", f"a confirmation was recorded from a non-confirming phrase: {row['status']}"


def test_ambiguous_medication_statement_asks_which_one_with_options(db_path):
    with _client(db_path) as client:
        import sqlite3
        from app.config import settings
        conn = sqlite3.connect(settings.db_path)
        for name in ("Metformin", "Amlodipine"):
            cur = conn.execute("INSERT INTO medications (name, instructions, active) VALUES (?, '', 1)", (name,))
            conn.execute(
                "INSERT INTO medication_schedules (medication_id, time, repeat_minutes, max_followups) VALUES (?, '09:00', 30, 2)",
                (cur.lastrowid,),
            )
        conn.commit()
        conn.close()

        resp = client.post("/api/chat", json={"message": "I took my medicine"})
        body = resp.json()
        assert body["type"] == "needs_confirmation"
        options = body["actions"][0]["payload"]["options"]
        assert {o["name"] for o in options} == {"Metformin", "Amlodipine"}
