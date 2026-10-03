#!/usr/bin/env python3
"""Seeds sanitized, entirely fictional demo data (spec §20.2):
one profile, three medications, two office cases, one PF email thread,
two blood reports (with differing values so compare_reports has something
to show), and two sample government-order documents for the personal
document index.

Safe to re-run: it's not idempotent by design (the hackathon demo wants a
clean slate), so it refuses to run against a database that already has a
profile — use --reset to wipe first.
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

import fitz  # noqa: E402  (after sys.path insert)

from app.config import settings  # noqa: E402
from app.db.connection import get_db, init_db  # noqa: E402
from app.health.parser import parse_pdf  # noqa: E402
from app.memory.store import index_document  # noqa: E402


def _write_lab_report_pdf(path: Path, title: str, date_str: str, rows: list[tuple]) -> None:
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    page.insert_text((72, y), title, fontsize=14); y += 24
    page.insert_text((72, y), f"Report date: {date_str}", fontsize=10); y += 28
    for test, value, unit, low, high in rows:
        line = f"{test}: {value} {unit} (Reference: {low}-{high})"
        page.insert_text((72, y), line, fontsize=11)
        y += 20
    doc.save(path)
    doc.close()


def _write_office_memo_pdf(path: Path, title: str, body_lines: list[str]) -> None:
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    page.insert_text((72, y), title, fontsize=14); y += 28
    for line in body_lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 20
    doc.save(path)
    doc.close()


def wipe(db) -> None:
    """Deletes every row (all tables), leaving the schema intact. Reminders
    before events before medication_schedules before medications — FK order
    matters here (SQLite enforces it)."""
    for table in (
        "lab_results", "documents", "email_drafts", "case_messages", "cases",
        "reminders", "events", "medication_schedules", "medications", "profile",
        "audit_events",
    ):
        db.execute(f"DELETE FROM {table}")
    db.execute("DELETE FROM personal_fts")
    db.execute("DELETE FROM government_fts")


def wipe_only() -> None:
    """Clears demo data WITHOUT reseeding anything — for switching to real
    data through the Settings screen (profile/medications) instead of
    editing this script. Leaves cases/documents/reports empty too, since
    those accumulate naturally from real use (drafting email, uploading a
    report), not from a one-time setup step.
    """
    init_db()
    with get_db() as db:
        wipe(db)
    print("Wiped. All tables are empty — set up a real profile and medications from the Settings screen.")


def seed(reset: bool = False) -> None:
    init_db()
    now = datetime.now(timezone.utc)

    with get_db() as db:
        existing = db.execute("SELECT id FROM profile LIMIT 1").fetchone()
        if existing and not reset:
            print("Demo data already present (profile exists). Use --reset to wipe and reseed.")
            return

        if reset:
            wipe(db)

        # --- Profile (fictional) ------------------------------------------------
        db.execute(
            """INSERT INTO profile (name, preferred_language, department, designation, office,
               employee_code, ddo_name, ddo_email, signature, family_escalation_enabled)
               VALUES (?, 'te-en', ?, ?, ?, ?, ?, ?, ?, 0)""",
            ("Venkata Rao", "School Education Department", "Senior Assistant",
             "District Education Office, Warangal", "EMP10234", "DDO, Warangal District",
             "ddo.warangal@example-tg.gov.in", "Venkata Rao\nSenior Assistant", ),
        )

        # --- Medications ----------------------------------------------------------
        meds = [
            ("Metformin", "500mg, after breakfast", "08:30", "breakfast"),
            ("Amlodipine", "5mg, once daily", "09:00", None),
            ("Atorvastatin", "10mg, at night after dinner", "21:00", "dinner"),
        ]
        for name, instructions, time_str, meal_dep in meds:
            cur = db.execute(
                "INSERT INTO medications (name, instructions, active) VALUES (?, ?, 1)",
                (name, instructions),
            )
            db.execute(
                """INSERT INTO medication_schedules
                   (medication_id, time, meal_dependency, repeat_minutes, max_followups)
                   VALUES (?, ?, ?, 30, 2)""",
                (cur.lastrowid, time_str, meal_dep),
            )

        # --- Cases + PF email thread (spec §14.4, §20.3) ---------------------------
        follow_up_due = now - timedelta(days=1)   # already overdue, so the demo can show FOLLOW_UP_DUE immediately
        sent_at = now - timedelta(days=8)
        cur = db.execute(
            """INSERT INTO cases (type, title, status, follow_up_due_at, created_at, updated_at)
               VALUES ('PF', 'Pending PF payment', 'WAITING_FOR_REPLY', ?, ?, ?)""",
            (follow_up_due.isoformat(), sent_at.isoformat(), sent_at.isoformat()),
        )
        pf_case_id = cur.lastrowid
        db.execute(
            """INSERT INTO case_messages (case_id, provider, provider_message_id, direction, subject, body, sent_at)
               VALUES (?, 'mock', 'mock-seed-1', 'OUTBOUND', ?, ?, ?)""",
            (pf_case_id,
             "Request for update on PF payment",
             "Respected Sir/Madam,\n\nI am writing to kindly request an update regarding my "
             "Provident Fund payment, employee code EMP10234. Kindly let me know the current "
             "status at your convenience.\n\nThank you,\nVenkata Rao",
             sent_at.isoformat()),
        )

        db.execute(
            """INSERT INTO cases (type, title, status, created_at, updated_at)
               VALUES ('PRC', 'PRC arrears verification', 'OPEN', ?, ?)""",
            (now.isoformat(), now.isoformat()),
        )

        # --- Two blood reports with differing values (older -> newer) -------------
        older_date = (now - timedelta(days=30))
        newer_date = now

        older_pdf = settings.reports_dir / "demo-blood-report-1.pdf"
        newer_pdf = settings.reports_dir / "demo-blood-report-2.pdf"

        _write_lab_report_pdf(older_pdf, "Blood Test Report", older_date.date().isoformat(), [
            ("Hemoglobin", 11.0, "g/dL", 13.0, 17.0),
            ("WBC Count", 7200, "/uL", 4000, 11000),
            ("Fasting Glucose", 98, "mg/dL", 70, 100),
        ])
        _write_lab_report_pdf(newer_pdf, "Blood Test Report", newer_date.date().isoformat(), [
            ("Hemoglobin", 11.2, "g/dL", 13.0, 17.0),
            ("WBC Count", 9500, "/uL", 4000, 11000),
            ("Fasting Glucose", 112, "mg/dL", 70, 100),
        ])

        for pdf_path, uploaded_at in ((older_pdf, older_date), (newer_pdf, newer_date)):
            with fitz.open(pdf_path) as doc:
                page_count = doc.page_count
                pages_text = [page.get_text() for page in doc]
            cur = db.execute(
                "INSERT INTO documents (filename, doc_type, path, page_count, uploaded_at) VALUES (?, 'LAB_REPORT', ?, ?, ?)",
                (pdf_path.name, str(pdf_path), page_count, uploaded_at.isoformat()),
            )
            document_id = cur.lastrowid
            index_document(db, document_id, "LAB_REPORT", pages_text)
            for row in parse_pdf(str(pdf_path)):
                db.execute(
                    """INSERT INTO lab_results (document_id, test, value, unit, reference_low,
                       reference_high, flag, source_page) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (document_id, row["test"], row["value"], row["unit"], row["reference_low"],
                     row["reference_high"], row["flag"], row["source_page"]),
                )

        # --- Sample office/government documents for personal search ---------------
        go_path = settings.documents_dir / "demo-go-prc.pdf"
        _write_office_memo_pdf(go_path, "G.O.Ms.No. 112 (Sample)", [
            "Subject: Revision of Pay Scales - Pay Revision Commission recommendations.",
            "This is sanitized sample content for demo purposes only.",
            "Applies to: State Government employees.",
            "Effective date: 01-07-2026 (sample).",
        ])
        memo_path = settings.documents_dir / "demo-office-memo.pdf"
        _write_office_memo_pdf(memo_path, "Office Memo (Sample)", [
            "Subject: Submission of service verification documents.",
            "All staff are requested to submit pending service verification",
            "documents to the DDO office by the end of the month.",
        ])
        for path, doc_type in ((go_path, "GOVERNMENT"), (memo_path, "OFFICE")):
            with fitz.open(path) as doc:
                page_count = doc.page_count
                pages_text = [page.get_text() for page in doc]
            cur = db.execute(
                "INSERT INTO documents (filename, doc_type, path, page_count, uploaded_at) VALUES (?, ?, ?, ?, ?)",
                (path.name, doc_type, str(path), page_count, now.isoformat()),
            )
            index_document(db, cur.lastrowid, doc_type, pages_text)

    print("Demo data seeded:")
    print("  profile: Venkata Rao (fictional)")
    print("  medications: Metformin, Amlodipine, Atorvastatin")
    print(f"  cases: PF (id={pf_case_id}, already overdue for follow-up), PRC arrears (open)")
    print("  lab reports: demo-blood-report-1.pdf (older), demo-blood-report-2.pdf (newer)")
    print("  documents: demo-go-prc.pdf (GOVERNMENT), demo-office-memo.pdf (OFFICE)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Wipe existing data before reseeding")
    parser.add_argument(
        "--wipe-only", action="store_true",
        help="Wipe demo data and leave the database empty, for switching to a real profile via Settings",
    )
    args = parser.parse_args()
    if args.wipe_only:
        wipe_only()
    else:
        seed(reset=args.reset)
