import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app import clock as clock_module  # noqa: E402
from app.ai import llm as llm_module  # noqa: E402
from app.config import settings  # noqa: E402
from app.db.connection import get_db, init_db  # noqa: E402


class _StubLLM(llm_module.LLMProvider):
    """Always unavailable. Every call site in this codebase falls back to
    a deterministic template on LLMUnavailable (that's the point of the
    LLM/deterministic split) — so the test suite must never depend on a
    real model being reachable on :8080. Without this, tests silently
    passed or failed depending on whether llama-server happened to be
    running (caught during manual review: README claimed "no model
    required" while a couple of tests quietly called the real thing).
    """
    async def chat(self, messages, temperature=0.2, max_tokens=500):
        raise llm_module.LLMUnavailable("stubbed for tests")


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    # get_llm_provider() reads this module-global itself, so patching it
    # here works regardless of which module imported get_llm_provider by
    # name — the function's closure still looks it up in app.ai.llm.
    monkeypatch.setattr(llm_module, "_default_provider", _StubLLM())


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setattr(settings, "db_path", path)
    init_db(path)
    return path


@pytest.fixture
def db(db_path):
    with get_db(db_path) as conn:
        yield conn


@pytest.fixture
def frozen_clock(monkeypatch):
    fixed = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(clock_module, "now_provider", lambda: fixed)
    return fixed


@pytest.fixture
def seeded_medication(db):
    """One medication + schedule, no meal dependency, due at 09:00."""
    cur = db.execute("INSERT INTO medications (name, instructions, active) VALUES ('TestMed', '1 tablet', 1)")
    med_id = cur.lastrowid
    cur = db.execute(
        """INSERT INTO medication_schedules (medication_id, time, meal_dependency, repeat_minutes, max_followups)
           VALUES (?, '09:00', NULL, 30, 2)""",
        (med_id,),
    )
    return {"medication_id": med_id, "schedule_id": cur.lastrowid}
