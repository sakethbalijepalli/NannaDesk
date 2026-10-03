"""Searches the real Telangana Government Order Issue Register (GOIR) —
the actual authoritative repository for government orders.

This replaced the original approach of fetching `telangana.gov.in/
government-orders/` with plain httpx. Investigated directly (both with
and without JS rendering): that page is not a GO listing at all — it's a
generic "Order of precedence" info page. The real repository, found by
searching for how GOs are actually published, is goir.telangana.gov.in,
an ASP.NET WebForms site whose search is a form postback (`__doPostBack`,
view state) that only a real browser can drive — httpx can't fill a form
and click a button. Confirmed live: searching "Pay Revision" here returns
real, current GO rows (department, GO number, date, subject) — the thing
the original implementation could never produce.
"""
import logging

from playwright.async_api import Browser, async_playwright

logger = logging.getLogger("nannadesk.goir")

GOIR_URL = "https://goir.telangana.gov.in/Default.aspx"
RESULTS_GRID_ID = "#FileMoveList2"

_playwright = None
_browser: Browser | None = None


async def start_browser() -> None:
    """Launches one headless Chromium for the process lifetime (FastAPI
    lifespan calls this) — a fresh launch per request was observed to add
    1-2s of pure startup overhead on top of the actual search.
    """
    global _playwright, _browser
    if _browser is not None:
        return
    try:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch()
        logger.info("GOIR browser started")
    except Exception as exc:  # pragma: no cover - environment-dependent
        # Chromium not installed (`playwright install chromium`), or no
        # display/sandbox support. Government search degrades to the
        # static-page fallback in search.py rather than crashing startup.
        logger.warning("Could not start browser for GOIR search: %s", exc)
        _playwright = None
        _browser = None


async def stop_browser() -> None:
    global _playwright, _browser
    if _browser is not None:
        await _browser.close()
        _browser = None
    if _playwright is not None:
        await _playwright.stop()
        _playwright = None


async def search_goir(search_text: str, timeout_ms: int = 20000, max_results: int = 3) -> list[dict] | None:
    """Fills the real search form and returns up to `max_results` GO rows.

    Returns None when the portal itself couldn't be searched (browser not
    available, network/timeout, or the site's structure changed under us)
    — callers must treat that as "could not confirm", never fall back to a
    guess. Returns [] (not None) when the search succeeded but matched
    nothing, which is a different, more specific kind of "not found".
    """
    if _browser is None:
        return None

    page = await _browser.new_page()
    try:
        await page.goto(GOIR_URL, wait_until="networkidle", timeout=timeout_ms)
        await page.fill("#txtSearchText", search_text)
        await page.click("#BtnSearch")
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        # The postback re-renders the grid; networkidle alone sometimes
        # lands a beat before the DOM update is painted.
        await page.wait_for_timeout(1000)

        grid = await page.query_selector(RESULTS_GRID_ID)
        if grid is None:
            return []

        rows = []
        for tr in await grid.query_selector_all("tr"):
            cells = await tr.query_selector_all("td")
            if len(cells) < 8:
                continue  # header/empty rows
            texts = [(await c.inner_text()).strip() for c in cells]
            # Column order confirmed by direct inspection (see this
            # module's docstring): index, dept, section, go_type, go_no,
            # date, category, subject, Download, View, (trailing blank).
            rows.append({
                "department": texts[1],
                "go_type": texts[3],
                "go_number": texts[4],
                "date": texts[5],
                "subject": texts[7],
            })
            if len(rows) >= max_results:
                break
        return rows
    except Exception as exc:
        logger.warning("GOIR search failed for %r: %s", search_text, exc)
        return None
    finally:
        await page.close()
