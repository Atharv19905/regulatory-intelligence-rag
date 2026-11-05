
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

INPUT_FILE = Path("data/versions/rbi_master_directions_discovered.json")

SAMPLES = ["13138", "13442", "13272", "11322"]

session = requests.Session()
session.headers.update({
    "User-Agent": "RegulatoryResearchProject/1.0"
})


def get_document_id(url):
    parsed = urlparse(url)
    return parse_qs(parsed.query).get("id", [None])[0]


def parse_date(text):
    text = " ".join(text.split())

    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return None


data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))

# The discovered records are nested under the "records" key.
records = data["records"]

by_id = {
    get_document_id(record.get("detail_url", "")): record
    for record in records
}

for doc_id in SAMPLES:
    record = by_id.get(doc_id)

    print("\n" + "=" * 75)
    print("DOCUMENT ID:", doc_id)

    if not record:
        print("Record not found in discovery JSON.")
        continue

    url = record["detail_url"]

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        print("Request failed:", exc)
        continue

    soup = BeautifulSoup(response.text, "html.parser")

    heading = soup.find(
        "p",
        class_="head",
        string=re.compile(r"Directions|Direction", re.I),
    )

    if heading:
        print("HEADING:", heading.get_text(" ", strip=True))

        content_cell = heading.find_parent("td")

        if content_cell:
            paragraphs = content_cell.find_all(
                "p",
                recursive=False,
            )

            print("DOCUMENT PARAGRAPHS:")

            for paragraph in paragraphs[:8]:
                text = " ".join(
                    paragraph.get_text(" ", strip=True).split()
                )
                print("  ", text[:300])

    print("DISCOVERY PUBLICATION DATE:",
          record.get("publication_date"))
    print("DETAIL URL:", url)

print("\nVerification complete. No files or database records modified.")
