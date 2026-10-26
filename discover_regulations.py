
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import requests
from bs4 import BeautifulSoup

INDEX_URL = (
    "https://www.rbi.org.in/scripts/"
    "bs_circularindexdisplay.aspx/Scripts/"
    "BS_CircularIndexDisplay.aspx"
)

OUTPUT_FILE = Path("data/versions/discovered_regulations.json")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

MAX_CIRCULARS = 10

session = requests.Session()

retry_strategy = Retry(
    total=3,
    connect=3,
    read=2,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    respect_retry_after_header=True,
)

adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
    "Connection": "close",
})


def get_soup(url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def get_circular_id(url):
    query = parse_qs(urlparse(url).query)
    return query.get("Id", [None])[0]


def discover_index_rows():
    soup = get_soup(INDEX_URL)
    circulars = []
    seen_ids = set()

    for row in soup.find_all("tr"):
        cells = row.find_all("td")

        if len(cells) < 4:
            continue

        # Circular number links are normally in the first cell.
        anchor = cells[0].find("a", href=True)

        if not anchor:
            continue

        reference_text = anchor.get_text(" ", strip=True)

        # Avoid archive/navigation links and unrelated pages.
        if not re.match(r"RBI/\d{4}-\d{4}/\d+", reference_text):
            continue

        detail_url = urljoin(INDEX_URL, anchor["href"])
        circular_id = get_circular_id(detail_url)

        if not circular_id or circular_id in seen_ids:
            continue

        seen_ids.add(circular_id)

        circulars.append({
            "detail_url": detail_url,
            "reference_number": reference_text,
            "publication_date_raw": cells[1].get_text(" ", strip=True),
            "department": cells[2].get_text(" ", strip=True),
            "title": cells[3].get_text(" ", strip=True),
        })

        if len(circulars) >= MAX_CIRCULARS:
            break

    return circulars


def get_pdf_links(detail_url):
    soup = get_soup(detail_url)
    pdf_urls = []

    for anchor in soup.find_all("a", href=True):
        pdf_url = urljoin(detail_url, anchor["href"])
        path = urlparse(pdf_url).path.lower()

        if (
            "/rdocs/notification/pdfs/" in path
            and path.endswith(".pdf")
        ):
            pdf_urls.append(pdf_url)

    return sorted(set(pdf_urls))


def main():
    print("Reading RBI circular index...")

    try:
        circulars = discover_index_rows()
    except requests.RequestException as error:
        print("Could not read RBI index:", error)
        return

    print("Circulars discovered on index:", len(circulars))

    if OUTPUT_FILE.exists():
        records = json.loads(
            OUTPUT_FILE.read_text(encoding="utf-8")
        )
    else:
        records = []

    # Preserve records already discovered in previous runs.
    records_by_url = {
        item["detail_url"]: item
        for item in records
        if item.get("detail_url")
    }

    for circular in circulars:
        try:
            pdf_urls = get_pdf_links(circular["detail_url"])

            record = {
                **circular,
                "regulator": "RBI",
                "pdf_urls": pdf_urls,
                "discovered_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }

            # Convert DD.MM.YYYY to YYYY-MM-DD when possible.
            try:
                record["publication_date"] = datetime.strptime(
                    circular["publication_date_raw"],
                    "%d.%m.%Y"
                ).date().isoformat()
            except ValueError:
                record["publication_date"] = None

            existing = records_by_url.get(circular["detail_url"], {})
            record["discovered_at"] = existing.get(
                "discovered_at", record["discovered_at"]
            )
            records_by_url[circular["detail_url"]] = {**existing, **record}

            print(
                f"Found: {record['reference_number']} | "
                f"{record['title'][:70]} | "
                f"PDF links: {len(pdf_urls)}"
            )

        except requests.RequestException as error:
            print(
                "Could not inspect:",
                circular["detail_url"],
                error
            )

        # Avoid sending rapid requests to the RBI website.
        time.sleep(1)

    OUTPUT_FILE.write_text(
        json.dumps(
            list(records_by_url.values()),
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("\nDiscovery completed.")
    print("Unique circular records in queue:", len(records_by_url))
    print("Saved to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
