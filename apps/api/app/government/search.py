"""Official-source retrieval flow (spec §13.1, §13.2).

FRESHNESS RULE: never answer a "latest" government question from model
memory. This module only ever returns text it just fetched from an
allowlisted official page, with a timestamp Dad can see — or an explicit
"internet required" / "could not confirm" response. It never falls back to
the LLM's own training-time knowledge or to the personal document index.
"""
import logging
from datetime import datetime, timezone

import httpx

from app.ai.llm import LLMUnavailable, LLMProvider, get_llm_provider
from app.ai.prompts import GOVERNMENT_ANSWER_POLICY
from app.config import settings
from app.db.models import GovernmentAnswer, Source
from app.government.parser import extract_page, find_passages
from app.government.sources import is_official, retrieval_timestamp, score_source

logger = logging.getLogger("nannadesk.government")

# Curated starting points per topic (spec §13.3: "prioritize official
# Telangana government domains ... including the state portal and relevant
# financial/employee systems"). A real deployment would add a proper
# site-search step in front of this; for the hackathon MVP this fixed,
# allowlisted candidate set keeps the freshness rule honest without
# depending on a third-party search API.
CANDIDATE_URLS: dict[str, list[str]] = {
    "prc": ["https://www.telangana.gov.in/government-orders/"],
    "pf": ["https://tgepfo.cgg.gov.in/"],
    "pension": ["https://tgepfo.cgg.gov.in/"],
    "da": ["https://www.telangana.gov.in/government-orders/"],
    "salary": ["https://treasury.telangana.gov.in/"],
    "_default": ["https://www.telangana.gov.in/government-orders/"],
}


class GovernmentRetrievalError(Exception):
    """Raised when no official source could be reached. Callers must
    surface this as 'internet required', never as a hallucinated answer.
    """


def _candidate_urls(query: str) -> list[str]:
    lowered = query.lower()
    for keyword, urls in CANDIDATE_URLS.items():
        if keyword != "_default" and keyword in lowered:
            return urls
    return CANDIDATE_URLS["_default"]


async def _fetch(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=settings.government_fetch_timeout_seconds, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPError as exc:
        logger.warning("Government fetch failed for %s: %s", url, exc)
        return None


async def search_government(query: str, llm: LLMProvider | None = None) -> GovernmentAnswer:
    llm = llm or get_llm_provider()
    candidates = _candidate_urls(query)

    fetched = []
    for url in candidates:
        if not is_official(url):
            continue  # never treat a non-allowlisted domain as authoritative
        html = await _fetch(url)
        if html:
            fetched.append((url, html))

    if not fetched:
        return GovernmentAnswer(
            answer=(
                "I could not reach an official government source just now, so I'm not going to "
                "guess. This needs internet access to the official site — please check your "
                "connection and try again."
            ),
            sources=[],
        )

    url, html = fetched[0]
    page = extract_page(html)
    passages = find_passages(page["text"], query)
    now_iso = retrieval_timestamp()
    score = score_source(url, department_match=True, recency_days=None, topic_match=True)

    source = Source(title=page["title"], date=now_iso, url=url, official=is_official(url))

    if passages is None:
        # §19.2 hallucination test: no specific match on the fetched page
        # is "I don't have enough information", never a summary of
        # unrelated page text (footer boilerplate, nav links, ...).
        return GovernmentAnswer(
            answer=(
                f"I checked the official page but didn't find anything specifically about "
                f"\"{query}\" on it. You can look yourself here, or try asking a different way."
            ),
            sources=[source],
        )

    passages_block = "\n\n".join(passages)
    try:
        answer_text = await llm.chat([
            {"role": "system", "content": GOVERNMENT_ANSWER_POLICY},
            {"role": "user", "content": f"QUESTION: {query}\n\nRETRIEVED TEXT:\n{passages_block}"},
        ])
    except LLMUnavailable:
        answer_text = (
            "WHAT IT SAYS\n" + passages_block +
            "\n\nSOURCE / ORDER NUMBER\n" + page["title"] +
            f"\n(retrieved {now_iso}, score {score})"
        )

    return GovernmentAnswer(answer=answer_text, sources=[source])
