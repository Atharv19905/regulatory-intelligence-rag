
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

REGISTRY = Path("data/versions/rbi_sources.json")
OUTPUT = Path("data/versions/rbi_source_inspection.json")

HEADERS = {
    "User-Agent": "RegulatoryResearchProject/1.0 (polite source inspection)"
}

session = requests.Session()
session.headers.update(HEADERS)

sources = json.loads(REGISTRY.read_text(encoding="utf-8"))
results = []

for index, source in enumerate(sources, start=1):
    url = source["url"]
    record = {
        "source_id": source["source_id"],
        "name": source.get("name", source["source_id"]),
        "url": url,
        "status_code": None,
        "page_title": None,
        "content_type": None,
        "table_count": 0,
        "row_count": 0,
        "pdf_links": [],
        "document_links": [],
        "error": None,
    }

    try:
        response = session.get(url, timeout=25)
        record["status_code"] = response.status_code
        record["content_type"] = response.headers.get("Content-Type", "")

        if response.ok and "html" in record["content_type"].lower():
            soup = BeautifulSoup(response.text, "html.parser")

            if soup.title:
                record["page_title"] = soup.title.get_text(" ", strip=True)

            tables = soup.find_all("table")
            record["table_count"] = len(tables)
            record["row_count"] = sum(
                len(table.find_all("tr")) for table in tables
            )

            for anchor in soup.find_all("a", href=True):
                href = anchor["href"].strip()
                text = anchor.get_text(" ", strip=True)
                absolute_url = requests.compat.urljoin(url, href)

                if not text:
                    continue

                parsed = urlparse(absolute_url)
                if not (
                    parsed.hostname
                    and (
                        parsed.hostname.lower() == "rbi.org.in"
                        or parsed.hostname.lower().endswith(".rbi.org.in")
                    )
                ):
                    continue

                item = {"title": text[:200], "url": absolute_url}

                if ".pdf" in parsed.path.lower():
                    if item not in record["pdf_links"]:
                        record["pdf_links"].append(item)
                elif any(
                    word in (text + " " + absolute_url).lower()
                    for word in (
                        "circular", "notification", "direction",
                        "report", "bulletin", "guideline", "faq",
                        "publication", "download"
                    )
                ):
                    if item not in record["document_links"]:
                        record["document_links"].append(item)

        print(
            f"[{index}/{len(sources)}] {record['source_id']}: "
            f"HTTP {record['status_code']}, "
            f"tables={record['table_count']}, "
            f"PDFs={len(record['pdf_links'])}, "
            f"links={len(record['document_links'])}"
        )

    except requests.RequestException as exc:
        record["error"] = str(exc)
        print(f"[{index}/{len(sources)}] {record['source_id']}: ERROR {exc}")

    results.append(record)

    # Keep the inspection gentle on the RBI website.
    time.sleep(1.0)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    json.dumps(results, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print(f"\nSaved inspection results to: {OUTPUT}")
print(f"Sources inspected: {len(results)}")
print(
    "HTTP 200 sources:",
    sum(item["status_code"] == 200 for item in results),
)
print(
    "Sources with errors:",
    sum(item["error"] is not None for item in results),
)
