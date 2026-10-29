
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCE_URL = (
    "https://www.rbi.org.in/scripts/BS_ViewMasterDirections.aspx"
)
OUTPUT_PATH = Path("data/versions/rbi_master_directions_discovered.json")

HEADERS = {
    "User-Agent": "RegulatoryResearchProject/1.0"
}


def clean_text(element):
    return " ".join(element.get_text(" ", strip=True).split())


def discover_master_directions():
    response = requests.get(
        SOURCE_URL,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    records = []
    seen = set()

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        for index, row in enumerate(rows):
            title_link = None
            pdf_url = None

            for anchor in row.find_all("a", href=True):
                href = anchor["href"].strip()
                absolute_url = urljoin(SOURCE_URL, href)

                if not clean_text(anchor):
                    if ".pdf" in href.lower():
                        pdf_url = absolute_url
                    continue

                if "BS_ViewMasDirections.aspx?id=" in href:
                    title_link = anchor
                    break

            if title_link is None:
                continue

            title = clean_text(title_link)
            detail_url = urljoin(SOURCE_URL, title_link["href"])

            # Avoid duplicate records from repeated page structures.
            if detail_url in seen:
                continue
            seen.add(detail_url)

            # RBI listing rows commonly place a date row immediately
            # before the row containing the title.
            publication_date = None
            if index > 0:
                previous_row = rows[index - 1]
                previous_text = clean_text(previous_row)

                try:
                    publication_date = datetime.strptime(
                        previous_text, "%b %d, %Y"
                    ).date().isoformat()
                except ValueError:
                    pass

            # Capture the PDF from the title row.
            for anchor in row.find_all("a", href=True):
                href = anchor["href"].strip()
                if ".pdf" in href.lower():
                    pdf_url = urljoin(SOURCE_URL, href)
                    break

            records.append({
                "source_id": "rbi_master_directions",
                "title": title,
                "publication_date": publication_date,
                "detail_url": detail_url,
                "pdf_url": pdf_url,
                "discovery_url": SOURCE_URL,
                "review_status": "pending",
            })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_id": "rbi_master_directions",
        "source_url": SOURCE_URL,
        "discovered_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "record_count": len(records),
        "records": records,
    }

    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Discovered records: {len(records)}")
    print(f"Saved to: {OUTPUT_PATH}")

    for record in records[:10]:
        print(f"\nTitle: {record['title']}")
        print(f"Date: {record['publication_date']}")
        print(f"Detail: {record['detail_url']}")
        print(f"PDF: {record['pdf_url']}")


if __name__ == "__main__":
    discover_master_directions()
