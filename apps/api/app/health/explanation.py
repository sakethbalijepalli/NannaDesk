"""Turns already-computed lab facts into Dad-facing language (spec §12.1,
§18.3: "the LLM writes a human-readable explanation from those
already-computed facts" — it never recomputes a flag or a diff itself).
"""
import re

from app.ai.llm import LLMUnavailable, LLMProvider, get_llm_provider
from app.ai.prompts import HEALTH_EXPLANATION_POLICY
from app.db.models import LabResult, ReportExplainResponse


def _facts_block(results: list[dict], diffs: list[dict] | None) -> str:
    lines = ["LAB RESULTS (already validated against the report's own reference range):"]
    for r in results:
        lines.append(
            f"- {r['test']}: {r['value']} {r.get('unit') or ''} "
            f"(reference {r.get('reference_low')}-{r.get('reference_high')}) -> {r['flag']}"
        )
    if diffs:
        lines.append("\nCHANGES SINCE PREVIOUS REPORT:")
        for d in diffs:
            if d["change"] == "new":
                lines.append(f"- {d['test']}: no previous value on record")
            else:
                lines.append(f"- {d['test']}: {d['change']} from {d['previous_value']} to {d['current_value']}")
    return "\n".join(lines)


async def explain_report(results: list[dict], diffs: list[dict] | None = None,
                          llm: LLMProvider | None = None) -> ReportExplainResponse:
    llm = llm or get_llm_provider()
    facts = _facts_block(results, diffs)

    try:
        text = await llm.chat([
            {"role": "system", "content": HEALTH_EXPLANATION_POLICY},
            {"role": "user", "content": facts},
        ], max_tokens=900)
        return _parse_sectioned_response(text, results, diffs)
    except LLMUnavailable:
        return _template_fallback(results, diffs)


def _parse_sectioned_response(text: str, results: list[dict], diffs: list[dict] | None) -> ReportExplainResponse:
    sections = {
        "WHAT THE REPORT SAYS": [], "WHAT IT MAY MEAN": [], "WHAT CHANGED": [],
        "QUESTIONS FOR YOUR DOCTOR": [], "WHEN TO SEEK HELP": [],
    }
    current = None
    for line in text.splitlines():
        # Strip markdown noise (#, *, _) before matching/storing — the
        # desired response shape (spec §12.5) is plain text, but a small
        # model asked for plain headers still sometimes renders markdown
        # ("# WHAT IT MAY MEAN", "**Hemoglobin:**").
        cleaned = re.sub(r"[#*_]", "", line).strip()
        matched_header = next((h for h in sections if cleaned.upper().startswith(h)), None)
        if matched_header:
            current = matched_header
            continue
        if current and cleaned:
            sections[current].append(cleaned.lstrip("-•").strip())

    # A small model will sometimes loop on one line until it hits the
    # token limit (observed during development); drop exact repeats
    # deterministically rather than trusting the model not to.
    for key, lines in sections.items():
        seen: set[str] = set()
        deduped = [l for l in lines if not (l in seen or seen.add(l))]
        sections[key] = deduped[:8]

    # what_it_says and what_changed are always the deterministic facts —
    # never the model's phrasing. The model rewriting "WBC increased within
    # normal range" into "suggesting an immune response or infection" was
    # observed during development; §18.3 only asks the LLM to narrate
    # already-computed facts, not reinterpret them.
    what_it_says = [
        f"{r['test']}: {r['value']} {r.get('unit') or ''} ({r['flag']})" for r in results
    ]
    what_changed = _diff_lines(diffs)

    return ReportExplainResponse(
        what_it_says=what_it_says,
        what_it_may_mean=" ".join(sections["WHAT IT MAY MEAN"]) or "No additional explanation available.",
        what_changed=what_changed,
        questions_for_doctor=sections["QUESTIONS FOR YOUR DOCTOR"] or ["Ask your doctor to review this report."],
        when_to_seek_help=sections["WHEN TO SEEK HELP"],
        results=[LabResult(**r) for r in results],
    )


def _diff_lines(diffs: list[dict] | None) -> list[str]:
    if not diffs:
        return ["No previous report on file to compare against."]
    return [
        f"{d['test']}: no previous value" if d["change"] == "new"
        else f"{d['test']} {d['change']} ({d['previous_value']} -> {d['current_value']})"
        for d in diffs
    ]


def _template_fallback(results: list[dict], diffs: list[dict] | None) -> ReportExplainResponse:
    """Used when llama-server isn't running. Built entirely from
    deterministic facts so /api/reports/{id}/explain still works and is
    testable without a model.
    """
    abnormal = [r for r in results if r["flag"] != "NORMAL"]
    what_it_may_mean = (
        "All values shown are within the lab's reference range."
        if not abnormal else
        "Some values fall outside the lab's reference range (shown above as LOW or HIGH). "
        "This is general information, not a diagnosis — your doctor can explain what it means for you."
    )
    when_to_seek_help = (
        ["Share these results with your doctor at your next visit, or sooner if you feel unwell."]
        if abnormal else []
    )
    return ReportExplainResponse(
        what_it_says=[f"{r['test']}: {r['value']} {r.get('unit') or ''} ({r['flag']})" for r in results],
        what_it_may_mean=what_it_may_mean,
        what_changed=_diff_lines(diffs),
        questions_for_doctor=[f"What does my {r['test']} result mean for me?" for r in abnormal] or
                              ["Are all my results normal for my age and health?"],
        when_to_seek_help=when_to_seek_help,
        results=[LabResult(**r) for r in results],
    )
