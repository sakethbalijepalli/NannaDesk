"""PDF -> structured lab rows (spec §12.1, §12.2).

Expects one lab line per row in the form:
    "<Test Name>: <value> <unit> (Reference: <low>-<high>)"
e.g. "Hemoglobin: 11.2 g/dL (Reference: 13.0-17.0)"

This is the layout `scripts/seed_demo_data.py` generates for the two demo
reports, so the parser has a real, exact target rather than a guess at
real-world lab PDF layouts (which vary enormously by lab).
"""
import re

import fitz  # PyMuPDF

from app.health.labs import flag

LINE_PATTERN = re.compile(
    r"^(?P<test>[A-Za-z0-9/ ]+?):\s*"
    r"(?P<value>-?\d+(?:\.\d+)?)\s*"
    r"(?P<unit>[A-Za-z/%µ]+)?\s*"
    r"\(Reference:\s*(?P<low>-?\d+(?:\.\d+)?)\s*-\s*(?P<high>-?\d+(?:\.\d+)?)\)"
)


def parse_pdf(path: str) -> list[dict]:
    """Extract structured lab rows from a PDF, with the page each row came
    from recorded for later citation.
    """
    results = []
    with fitz.open(path) as doc:
        for page_index, page in enumerate(doc, start=1):
            text = page.get_text()
            for line in text.splitlines():
                match = LINE_PATTERN.match(line.strip())
                if not match:
                    continue
                value = float(match.group("value"))
                low = float(match.group("low"))
                high = float(match.group("high"))
                results.append({
                    "test": match.group("test").strip(),
                    "value": value,
                    "unit": (match.group("unit") or "").strip() or None,
                    "reference_low": low,
                    "reference_high": high,
                    "flag": flag(value, low, high),
                    "source_page": page_index,
                })
    return results
