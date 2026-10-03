"""Spec §13.1 freshness rule: never answer from model memory. When no
official source can be reached, say so plainly instead of guessing.

GOIR (app.government.goir) is the primary path — see that module's
docstring for why a plain HTTP GET can't drive it. These tests mock
`search_goir` directly rather than depending on whether a real browser
happens to be running in the test process; the "falls through to the
static-page fallback" tests simulate GOIR being unavailable by having it
return None, exactly as it does when Chromium isn't installed.
"""
from app.government import search as gov_search
from app.government.sources import is_official


def _goir_unavailable(monkeypatch):
    async def fake(search_text):
        return None
    monkeypatch.setattr(gov_search, "search_goir", fake)


def test_is_official_matches_allowlisted_domains_only():
    assert is_official("https://www.telangana.gov.in/government-orders/")
    assert is_official("https://tgepfo.cgg.gov.in/status")
    assert not is_official("https://example.com/telangana.gov.in")
    assert not is_official("https://not-telangana.gov.in.evil.com/")


# --- GOIR path (primary) ---

async def test_goir_match_cites_the_register_with_structured_facts(monkeypatch):
    async def fake_search_goir(search_text):
        assert search_text  # a real term was built, not the whole sentence
        return [{
            "department": "FINANCE", "go_type": "MS", "go_number": "54",
            "date": "11/06/2021 20:01:52",
            "subject": "ALLOWANCES – Recommendations of First Pay Revision Commission – Accepted.",
        }]
    monkeypatch.setattr(gov_search, "search_goir", fake_search_goir)

    result = await gov_search.search_government("Any update on PRC?")

    assert len(result.sources) == 1
    assert result.sources[0].official is True
    assert "goir.telangana.gov.in" in result.sources[0].url


async def test_goir_zero_results_is_a_specific_not_found_not_a_guess(monkeypatch):
    async def fake_search_goir(search_text):
        return []  # searched successfully, found nothing — not the same as "unavailable"

    monkeypatch.setattr(gov_search, "search_goir", fake_search_goir)

    result = await gov_search.search_government("PRC update")

    assert "no matching orders" in result.answer.lower()
    assert len(result.sources) == 1  # still cites the register it searched


async def test_goir_unavailable_falls_back_to_static_fetch(monkeypatch):
    _goir_unavailable(monkeypatch)

    async def fake_fetch(url):
        return "<html><title>Sample GO</title><body>PRC order details here</body></html>"
    monkeypatch.setattr(gov_search, "_fetch", fake_fetch)

    result = await gov_search.search_government("PRC update")

    assert "didn't find" not in result.answer
    assert len(result.sources) == 1


# --- Static-page fallback (only reached when GOIR is unavailable) ---

async def test_network_failure_returns_internet_required_not_a_guess(monkeypatch):
    _goir_unavailable(monkeypatch)

    async def always_fails(url):
        return None
    monkeypatch.setattr(gov_search, "_fetch", always_fails)

    result = await gov_search.search_government("latest PRC update")

    assert result.sources == []
    assert "internet" in result.answer.lower() or "connection" in result.answer.lower()


async def test_trailing_punctuation_on_the_query_does_not_block_a_match(monkeypatch):
    # "Any update on PRC?" — the trailing "?" on "PRC?" must be stripped
    # before matching, or it never finds "prc" in plain page text (caught
    # during manual end-to-end testing).
    _goir_unavailable(monkeypatch)

    async def fake_fetch(url):
        return "<html><title>Sample GO</title><body>PRC order details here</body></html>"
    monkeypatch.setattr(gov_search, "_fetch", fake_fetch)

    result = await gov_search.search_government("Any update on PRC?")

    assert "didn't find" not in result.answer
    assert len(result.sources) == 1


def test_candidate_url_keyword_matches_word_boundaries_not_substrings():
    # Code review: "da" as a bare `in` check matched inside "update",
    # routing a salary question to the generic GO page instead of treasury.
    from app.government.search import _candidate_urls
    assert _candidate_urls("Any salary update?") == ["https://treasury.telangana.gov.in/"]
    assert _candidate_urls("is this helpful") != ["https://tgepfo.cgg.gov.in/"]


async def test_short_acronym_does_not_match_as_a_substring_of_another_word(monkeypatch):
    # "da" as a plain substring matches inside "upDAted" — regression test
    # for find_passages, exercised through the full search_government path.
    _goir_unavailable(monkeypatch)

    async def fake_fetch(url):
        return "<html><title>T</title><body>Page last updated recently. Nothing else here.</body></html>"
    monkeypatch.setattr(gov_search, "_fetch", fake_fetch)

    result = await gov_search.search_government("Latest DA update")

    assert "didn't find" in result.answer


async def test_successful_fetch_cites_an_official_source(monkeypatch):
    _goir_unavailable(monkeypatch)

    async def fake_fetch(url):
        return "<html><title>Sample GO</title><body>PRC order details here</body></html>"
    monkeypatch.setattr(gov_search, "_fetch", fake_fetch)

    result = await gov_search.search_government("PRC update")

    assert len(result.sources) == 1
    assert result.sources[0].official is True
