"""Spec §13.1 freshness rule: never answer from model memory. When no
official source can be reached, say so plainly instead of guessing.
"""
from app.government import search as gov_search
from app.government.sources import is_official


def test_is_official_matches_allowlisted_domains_only():
    assert is_official("https://www.telangana.gov.in/government-orders/")
    assert is_official("https://tgepfo.cgg.gov.in/status")
    assert not is_official("https://example.com/telangana.gov.in")
    assert not is_official("https://not-telangana.gov.in.evil.com/")


async def test_network_failure_returns_internet_required_not_a_guess(monkeypatch):
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
    async def fake_fetch(url):
        return "<html><title>Sample GO</title><body>PRC order details here</body></html>"

    monkeypatch.setattr(gov_search, "_fetch", fake_fetch)

    result = await gov_search.search_government("Any update on PRC?")

    assert "didn't find" not in result.answer
    assert len(result.sources) == 1


async def test_short_acronym_does_not_match_as_a_substring_of_another_word(monkeypatch):
    # "da" as a plain substring matches inside "upDAted" — regression test
    # for find_passages, exercised through the full search_government path.
    async def fake_fetch(url):
        return "<html><title>T</title><body>Page last updated recently. Nothing else here.</body></html>"

    monkeypatch.setattr(gov_search, "_fetch", fake_fetch)

    result = await gov_search.search_government("Latest DA update")

    assert "didn't find" in result.answer


async def test_successful_fetch_cites_an_official_source(monkeypatch):
    async def fake_fetch(url):
        return "<html><title>Sample GO</title><body>PRC order details here</body></html>"

    monkeypatch.setattr(gov_search, "_fetch", fake_fetch)

    result = await gov_search.search_government("PRC update")

    assert len(result.sources) == 1
    assert result.sources[0].official is True
