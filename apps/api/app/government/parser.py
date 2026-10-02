"""Extract readable text + passages from a fetched government HTML page."""
import re

from bs4 import BeautifulSoup


def extract_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled page"
    text = " ".join(soup.get_text(separator=" ").split())
    return {"title": title, "text": text}


# Words too generic to count as a real topic match on their own — matching
# only on these produced a nonsense answer grounded in page footer text
# ("Last updated on …") during manual testing, because "update"/"latest"
# are common boilerplate on any government page.
GENERIC_TERMS = {
    "the", "any", "new", "latest", "update", "updates", "updated", "about",
    "please", "what", "when", "where", "does", "say", "tell", "government",
    "telangana", "information", "order", "orders",
}

# Short government acronyms that are real topic words despite their
# length (the `len(w) > 2` cutoff below would otherwise drop them).
# Matched on word boundaries, not substring `.find()` — "da" as a plain
# substring matches inside "upDAte", which defeated the point of filtering
# "update" out as generic in the first place.
SHORT_ACRONYMS = {"pf", "da", "go"}

# A spec term that rarely appears verbatim on the page that names it — real
# GO pages say "Pay Revision Commission", not "PRC".
SYNONYMS = {"prc": ["pay revision"]}


def find_passages(text: str, query: str, window: int = 240, max_passages: int = 3) -> list[str] | None:
    """Naive keyword-window passage extraction — enough to ground an LLM
    summary in real retrieved text without adding a ranking model.

    Returns None (not a fallback slice of the page) when the query has no
    specific-enough terms to search for — callers must treat that as "not
    enough information", never silently summarize unrelated page text.
    """
    # Strip punctuation per word ("PRC?" -> "prc") — a trailing "?" on the
    # question's last word otherwise never matches plain page text (caught
    # during manual end-to-end testing of "Any update on PRC?").
    words = [re.sub(r"[^\w]", "", w).lower() for w in query.split()]
    terms = [w for w in words if (len(w) > 2 or w in SHORT_ACRONYMS) and w not in GENERIC_TERMS]
    for term in list(terms):
        terms.extend(SYNONYMS.get(term, []))
    if not terms:
        return None

    lowered = text.lower()
    passages = []
    seen_spans = set()
    for term in terms:
        pattern = rf"\b{re.escape(term)}\b" if (len(term) <= 2 or " " in term) else re.escape(term)
        match = re.search(pattern, lowered)
        if not match:
            continue
        start = match.start()
        span_start = max(0, start - window // 2)
        span_end = min(len(text), start + window // 2)
        if any(abs(span_start - s) < window // 2 for s in seen_spans):
            continue
        seen_spans.add(span_start)
        passages.append(text[span_start:span_end].strip())
        if len(passages) >= max_passages:
            break

    return passages or None
