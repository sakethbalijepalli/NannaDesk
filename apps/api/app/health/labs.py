"""Deterministic range flagging and report comparison (spec §12.3). The
application — never the LLM — decides whether a value is inside the
laboratory's own printed reference range.
"""
from typing import Literal, Optional

Flag = Literal["LOW", "NORMAL", "HIGH"]


def flag(value: float, low: Optional[float], high: Optional[float]) -> Flag:
    if low is not None and value < low:
        return "LOW"
    if high is not None and value > high:
        return "HIGH"
    return "NORMAL"


def compare(current: list[dict], previous: list[dict]) -> list[dict]:
    """Deterministic diff between two sets of lab results, matched by test
    name. The LLM only narrates these pre-computed facts — it never
    recomputes a delta itself.
    """
    previous_by_test = {row["test"].lower(): row for row in previous}
    diffs = []
    for row in current:
        prev = previous_by_test.get(row["test"].lower())
        if prev is None:
            diffs.append({"test": row["test"], "change": "new", "previous_value": None, "current_value": row["value"]})
            continue
        delta = row["value"] - prev["value"]
        if delta == 0:
            change = "unchanged"
        elif delta > 0:
            change = "increased"
        else:
            change = "decreased"
        diffs.append({
            "test": row["test"], "change": change,
            "previous_value": prev["value"], "current_value": row["value"], "delta": delta,
        })
    return diffs
