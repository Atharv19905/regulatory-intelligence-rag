"""Discover RBI Master Directions without guessing publication dates.

Dates are taken only from the title row or its immediately preceding row.
A date is recorded only when a cell contains a recognizable date string.
The original date text is retained for auditability.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.rbi.org.in/scripts/BS_ViewMasterDirections.aspx"
OUTPUT_PATH = Path("data/versions/rbi_master_directions_discovered.json")
HEADERS = {"User-Agent": "RegulatoryResearchProject/1.0"}

DATE_FORMATS = (
    "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",
    "%d %b %Y", "%d %B %Y",
    "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
    "%Y-%m-%d", "%m/%d/%Y",
)
DATE_PATTERNS = (
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b", re.I),
    re.compile(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b", re.I),
    re.compile(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
)


def clean_text(element):
    return " ".join(element.get_text(" ", strip=True).split())


def parse_date_text(text):
    """Return (ISO date, original matched text), or (None, None)."""
    text = " ".join((text or "").split())
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            candidate = match.group(0)
            for fmt in DATE_FORMATS:
                try:
                    return datetime.strptime(candidate, fmt).date().isoformat(), match.group(0)
                except ValueError:
                    continue
    return None, None


def row_date(row):
    # Check individual cells first; avoids parsing unrelated row text as a date.
    cells = row.find_all(["td", "th"], recursive=False)
    for cell in cells:
        iso_date, raw = parse_date_text(clean_text(cell))
        if iso_date:
            return iso_date, raw
    return parse_date_text(clean_text(row))


def extract_detail_publication_date(detail_url):
    """Read the date printed in the official RBI Master Direction header.

    The listing table does not reliably expose dates. On RBI detail pages, the
    issue date normally appears near the RBI reference number in the header.
    Return (ISO date, raw text, status); never infer a date from body content.
    """
    try:
        response = requests.get(detail_url, headers=HEADERS, timeout=25)
        response.raise_for_status()
        page = BeautifulSoup(response.text, "html.parser")
        lines = [" ".join(x.split()) for x in page.get_text("\n", strip=True).splitlines()]
        lines = [x for x in lines if x]

        # Prefer the short header region immediately after the RBI reference.
        for i, line in enumerate(lines[:100]):
            if re.search(r"\bRBI\s*/", line, re.I):
                header = " ".join(lines[i:i + 5])
                iso, raw = parse_date_text(header)
                if iso:
                    return iso, raw, "detail_header"

        # Fallback: inspect only the page's opening metadata, never the full
        # document body where unrelated dates could be mistaken for issue date.
        opening = " ".join(lines[:35])
        iso, raw = parse_date_text(opening)
        if iso:
            return iso, raw, "detail_header_fallback_review"
        return None, None, "date_not_found"
    except Exception as exc:
        return None, None, f"fetch_error:{type(exc).__name__}"


def discover_master_directions():
    response = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    records = []
    seen = set()
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for index, row in enumerate(rows):
            title_link = None
            for anchor in row.find_all("a", href=True):
                href = anchor["href"].strip()
                if "BS_ViewMasDirections.aspx?id=" in href:
                    title_link = anchor
                    break
            if title_link is None:
                continue

            detail_url = urljoin(SOURCE_URL, title_link["href"])
            if detail_url in seen:
                continue
            seen.add(detail_url)

            # Search the title row, then only its immediate predecessor.
            # Do not scan distant rows: that could attach another document's date.
            publication_date, publication_date_raw = row_date(row)
            date_source_row = "title_row" if publication_date else None
            if not publication_date and index > 0:
                publication_date, publication_date_raw = row_date(rows[index - 1])
                if publication_date:
                    date_source_row = "previous_row"

            pdf_url = None
            for anchor in row.find_all("a", href=True):
                href = anchor["href"].strip()
                if ".pdf" in href.lower():
                    pdf_url = urljoin(SOURCE_URL, href)
                    break

            records.append({
                "source_id": "rbi_master_directions",
                "title": clean_text(title_link),
                "publication_date": publication_date,
                "publication_date_raw": publication_date_raw,
                "publication_date_source_row": date_source_row,
                "detail_url": detail_url,
                "pdf_url": pdf_url,
                "discovery_url": SOURCE_URL,
                "review_status": "pending",
            })

    # Listing rows often have no dates. Enrich from each official detail page.
    # Four concurrent requests keep this reasonably quick without a large burst.
    needs_detail_date = [r for r in records if not r["publication_date"]]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(extract_detail_publication_date, r["detail_url"]): r
                   for r in needs_detail_date}
        for future in as_completed(futures):
            record = futures[future]
            iso, raw, status = future.result()
            if iso:
                record["publication_date"] = iso
                record["publication_date_raw"] = raw
                record["publication_date_source_row"] = status
            record["date_extraction_status"] = status

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_id": "rbi_master_directions",
        "source_url": SOURCE_URL,
        "discovered_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "records": records,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    dated = sum(bool(record["publication_date"]) for record in records)
    print(f"Discovered records: {len(records)}")
    print(f"Records with parsed dates: {dated}/{len(records)}")
    print(f"Saved to: {OUTPUT_PATH}")
    for record in records[:10]:
        print(f"\nTitle: {record['title']}\nDate: {record['publication_date']} "
              f"(raw: {record['publication_date_raw']})\nDetail: {record['detail_url']}\nPDF: {record['pdf_url']}")


if __name__ == "__main__":
    discover_master_directions()
