"""Official-source allowlist and ranking heuristic (spec §13.3, §13.4).

The score is a ranking convenience, not a legal authority claim — the UI
always shows the real source so Dad can check it himself.
"""
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.config import settings


def is_official(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith(f".{d}") for d in settings.government_allowlist)


def score_source(url: str, department_match: bool, recency_days: int | None, topic_match: bool) -> int:
    score = 0
    if is_official(url):
        score += 100
    if department_match:
        score += 40
    if recency_days is not None:
        # Full recency credit within 30 days, decaying to 0 by 365 days.
        recency_fraction = max(0.0, 1 - (recency_days / 365))
        score += round(30 * recency_fraction)
    if topic_match:
        score += 20
    return score


def retrieval_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
