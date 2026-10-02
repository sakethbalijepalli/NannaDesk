from app.email.draft import _match_case


def test_match_case_keyword_matches_word_boundaries_not_substrings(db):
    # Code review: "pf" as a bare `in` check matched inside "helpful",
    # misattributing an unrelated draft to the PF case. Seed a second,
    # more-recently-updated case so the "most recent open case" fallback
    # can't coincidentally also land on PF and mask the bug.
    db.execute(
        "INSERT INTO cases (type, title, status, updated_at) VALUES ('PF', 'Pending PF payment', 'OPEN', '2026-01-01')"
    )
    db.execute(
        "INSERT INTO cases (type, title, status, updated_at) VALUES ('GENERAL', 'Service verification', 'OPEN', '2026-06-01')"
    )
    result = _match_case(db, "Can you write a helpful note to my DDO")
    assert result is not None
    assert result["type"] != "PF"
