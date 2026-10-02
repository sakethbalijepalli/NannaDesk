"""Mock mailbox, used until Outlook/Graph credentials are configured
(spec §14.1). Rather than keeping its own in-memory inbox that would reset
every restart, it reads/writes through the same `case_messages` table the
rest of the app already uses for case tracking — so `seed_demo_data.py`'s
seeded PF thread is what `search`/`get_thread` actually find, and a sent
message is immediately visible to a later "did they reply" search.
"""
import itertools
import uuid
from datetime import datetime, timezone

from app.db.connection import get_db
from app.email.base import EmailMessage, EmailProvider

_id_counter = itertools.count(1)


class MockProvider(EmailProvider):
    async def search(self, query: str) -> list[EmailMessage]:
        like = f"%{query}%"
        with get_db() as db:
            rows = db.execute(
                """SELECT * FROM case_messages WHERE subject LIKE ? OR body LIKE ?
                   ORDER BY sent_at DESC""",
                (like, like),
            ).fetchall()
        return [self._to_message(r) for r in rows]

    async def get_thread(self, thread_id: str) -> list[EmailMessage]:
        case_id = thread_id.removeprefix("case-")
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM case_messages WHERE case_id = ? ORDER BY sent_at ASC", (case_id,)
            ).fetchall()
        return [self._to_message(r) for r in rows]

    async def create_draft(self, to_addr: str, subject: str, body: str) -> EmailMessage:
        return {
            "id": f"draft-{next(_id_counter)}", "thread_id": f"thread-{uuid.uuid4().hex[:8]}",
            "to_addr": to_addr, "subject": subject, "body": body, "direction": "OUTBOUND",
        }

    async def send(self, to_addr: str, subject: str, body: str) -> EmailMessage:
        return {
            "id": f"mock-{uuid.uuid4().hex[:10]}", "thread_id": f"thread-{uuid.uuid4().hex[:8]}",
            "to_addr": to_addr, "subject": subject, "body": body, "direction": "OUTBOUND",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _to_message(row) -> EmailMessage:
        return {
            "id": str(row["provider_message_id"] or row["id"]),
            "thread_id": f"case-{row['case_id']}" if row["case_id"] else "",
            "subject": row["subject"], "body": row["body"],
            "direction": row["direction"], "sent_at": row["sent_at"],
        }


_mock_provider = MockProvider()


def get_mock_provider() -> MockProvider:
    return _mock_provider
