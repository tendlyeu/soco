"""
Tendly.eu SPA scraper using Playwright.

Renders a single tender page with headless Chromium and extracts
structured data matching the shape expected by build_tender_dict()
and import_tender_source().
"""
import re
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def extract_procurement_id(url: str) -> str:
    """Extract the numeric procurement ID from a tendly.eu URL.

    URL format: https://tendly.eu/[locale/]tender/{id}-{slug}
    """
    path = urlparse(url).path
    m = re.search(r"/tender/(\d+)", path)
    if not m:
        raise ValueError(f"Cannot extract procurement ID from URL: {url}")
    return m.group(1)


def scrape_tender(url: str, timeout_ms: int = 30_000) -> dict:
    """Scrape a single tender page from tendly.eu.

    Args:
        url: Full tendly.eu tender URL.
        timeout_ms: Max time (ms) to wait for content to render.

    Returns:
        dict with keys matching the DB row shape used by
        build_tender_dict() and import_tender_source().
    """
    procurement_id = extract_procurement_id(url)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_selector(".td-header-title", timeout=timeout_ms)
        except PlaywrightTimeout:
            browser.close()
            raise TimeoutError(
                f"Timed out waiting for tender content to load at {url}"
            )

        title = _text(page, ".td-header-title") or ""
        description = _text(page, ".td-description-text") or ""

        # Extract metadata from .td-meta-item elements
        organization = ""
        budget_raw = None
        cpv_id = None
        reference_nr = None
        meta_items = page.query_selector_all(".td-meta-item")
        for item in meta_items:
            label_el = item.query_selector(".td-meta-label")
            value_el = item.query_selector(".td-meta-value, .td-meta-value-mono")
            if not label_el or not value_el:
                continue
            label = (label_el.inner_text() or "").strip().lower()
            value = (value_el.inner_text() or "").strip()
            if label == "organization":
                organization = value
            elif label == "value":
                budget_raw = value
            elif label == "cpv code":
                cpv_id = value
            elif label == "category":
                category = value
            elif label == "reference":
                reference_nr = value

        # Deadline
        deadline = _text(page, ".td-deadline-date")

        # Category from meta or summary
        category_val = None
        for item in meta_items:
            label_el = item.query_selector(".td-meta-label")
            if label_el and (label_el.inner_text() or "").strip().lower() == "category":
                value_el = item.query_selector(".td-meta-value")
                if value_el:
                    category_val = value_el.inner_text().strip()
                break

        # Parse estimated cost number from budget string
        estimated_cost = _parse_cost(budget_raw)

        browser.close()

    # Extract reference nr from the URL path segment (id-slug)
    path_segment = urlparse(url).path.split("/")[-1]

    return {
        "procurement_id": procurement_id,
        "procurement_reference_nr": reference_nr or path_segment,
        "procurement_name": title,
        "contracting_authority_name": organization,
        "short_description": description,
        "main_cpv_name": category_val,
        "main_cpv_id": cpv_id,
        "proc_process_submit_date": deadline,
        "created_at": None,
        "estimated_cost": estimated_cost,
        "document_url": url,
    }


def _text(page, selector: str) -> str | None:
    """Return inner text of the first element matching selector, or None."""
    el = page.query_selector(selector)
    if el:
        t = el.inner_text()
        if t:
            return t.strip()
    return None


def _parse_cost(value: str | None) -> float | None:
    """Try to extract a numeric cost from a budget string like 'EUR 1,234,567'."""
    if not value:
        return None
    digits = re.sub(r"[^\d.]", "", value.replace(",", ""))
    try:
        return float(digits)
    except ValueError:
        return None
