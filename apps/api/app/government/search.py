"""Official-source retrieval flow (spec §13.1, §13.2).

FRESHNESS RULE: never answer a "latest" government question from model
memory. This module only ever returns text it just retrieved live from an
allowlisted official source, with a timestamp Dad can see — or an explicit
"internet required" / "could not confirm" response. It never falls back to
the LLM's own training-time knowledge or to the personal document index.

Primary path: the real Telangana Government Order Issue Register
(goir.telangana.gov.in), searched via a headless browser — see
app/government/goir.py's docstring for why a plain HTTP GET can't do this
(it's a JS form postback, and the page a plain fetch used to hit isn't
even a GO listing). Falls back to the old static-page fetch only when the
browser path can't run at all (e.g. Chromium not installed).
"""
import logging
import re
from datetime import datetime, timezone

import httpx

from app.ai.llm import LLMUnavailable, LLMProvider, get_llm_provider
from app.ai.prompts import GOVERNMENT_ANSWER_POLICY
from app.config import settings
from app.db.models import GovernmentAnswer, Source
from app.government.goir import GOIR_URL, search_goir
from app.government.parser import extract_page, extract_search_terms, find_passages
from app.government.sources import is_official, retrieval_timestamp, score_source

logger = logging.getLogger("nannadesk.government")

# Fallback-only starting points, used solely when the GOIR browser search
# can't run at all (see search_government). Kept narrow and allowlisted
# for the same reason as before: never treat an unvetted domain as
# authoritative.
CANDIDATE_URLS: dict[str, list[str]] = {
    "prc": ["https://www.telangana.gov.in/government-orders/"],
    "pf": ["https://tgepfo.cgg.gov.in/"],
    "pension": ["https://tgepfo.cgg.gov.in/"],
    "da": ["https://www.telangana.gov.in/government-orders/"],
    "salary": ["https://treasury.telangana.gov.in/"],
    "_default": ["https://www.telangana.gov.in/government-orders/"],
}


def _candidate_urls(query: str) -> list[str]:
    lowered = query.lower()
    for keyword, urls in CANDIDATE_URLS.items():
        if keyword != "_default" and re.search(rf"\b{re.escape(keyword)}\b", lowered):
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


def _goir_facts_block(rows: list[dict]) -> str:
    lines = ["GOVERNMENT ORDERS FOUND (already retrieved from the official register):"]
    for r in rows:
        lines.append(
            f"- GO {r['go_type']} No.{r['go_number']}, {r['department']}, {r['date']}: {r['subject']}"
        )
    return "\n".join(lines)


def _goir_template_answer(rows: list[dict]) -> str:
    lines = ["WHAT IT SAYS"]
    for r in rows:
        lines.append(f"- {r['subject']}")
    lines += [
        "",
        "SOURCE / ORDER NUMBER",
        "; ".join(f"GO {r['go_type']} No.{r['go_number']} ({r['department']})" for r in rows),
        "",
        "PAGE OR SECTION",
        "; ".join(f"dated {r['date']}" for r in rows),
    ]
    return "\n".join(lines)


async def _search_goir_path(query: str, llm: LLMProvider) -> GovernmentAnswer | None:
    """Returns None (not an answer) when GOIR itself couldn't be searched,
    so the caller can fall back to the static-page path — never when it
    searched successfully and found nothing, which is a real answer.
    """
    terms = extract_search_terms(query)
    if not terms:
        return None

    # GOIR's "Exact Text" search is a literal substring match against the
    # whole phrase, not a tokenized multi-word search — confirmed live:
    # "pay revision prc" (the synonym plus the original acronym, joined)
    # matches nothing, because that exact string never appears anywhere,
    # even though "pay revision" alone returns rich, relevant results.
    # So candidates are tried one at a time, most specific first (a
    # synonym expansion, then each remaining term alone), stopping at the
    # first one that actually matches something — never concatenated.
    now_iso = retrieval_timestamp()
    source = Source(title="Telangana Government Order Issue Register", date=now_iso, url=GOIR_URL, official=True)
    rows: list[dict] = []
    tried_any = False
    for candidate in terms:
        result = await search_goir(candidate)
        if result is None:
            continue  # this attempt failed; still try the next candidate
        tried_any = True
        if result:
            rows = result
            break

    if not tried_any:
        return None  # browser unavailable / every attempt failed outright

    if not rows:
        return GovernmentAnswer(
            answer=(
                f"I searched the official Government Order register for \"{query}\" and found no "
                f"matching orders. You can search yourself at {GOIR_URL}, or try different words."
            ),
            sources=[source],
        )

    facts = _goir_facts_block(rows)
    try:
        answer_text = await llm.chat([
            {"role": "system", "content": GOVERNMENT_ANSWER_POLICY},
            {"role": "user", "content": f"QUESTION: {query}\n\n{facts}"},
        ])
    except LLMUnavailable:
        answer_text = _goir_template_answer(rows)

    return GovernmentAnswer(answer=answer_text, sources=[source])


async def _search_static_fallback(query: str, llm: LLMProvider) -> GovernmentAnswer:
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


async def search_government(query: str, llm: LLMProvider | None = None) -> GovernmentAnswer:
    llm = llm or get_llm_provider()

    goir_result = await _search_goir_path(query, llm)
    if goir_result is not None:
        return goir_result

    logger.info("GOIR search unavailable, falling back to static-page fetch for %r", query)
    return await _search_static_fallback(query, llm)
