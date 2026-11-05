
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REGISTRY = Path("data/versions/rbi_sources.json")

TARGETS = [
    "rbi_circulars",
    "rbi_master_directions",
    "rbi_master_circulars",
    "rbi_amendment_directions",
]

sources = json.loads(REGISTRY.read_text(encoding="utf-8"))
by_id = {item["source_id"]: item for item in sources}

session = requests.Session()
session.headers.update({
    "User-Agent": "RegulatoryResearchProject/1.0"
})

for source_id in TARGETS:
    source = by_id.get(source_id)

    if not source:
        print(f"\nSOURCE NOT FOUND: {source_id}")
        continue

    print("\n" + "=" * 90)
    print(f"SOURCE: {source_id}")
    print(f"URL: {source['url']}")

    try:
        response = session.get(source["url"], timeout=25)
        response.raise_for_status()
    except requests.RequestException as exc:
        print("REQUEST ERROR:", exc)
        continue

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    print("TABLE COUNT:", len(tables))

    for table_index, table in enumerate(tables, start=1):
        rows = table.find_all("tr")
        print(f"\nTABLE {table_index}: {len(rows)} rows")

        for row_index, row in enumerate(rows[:8], start=1):
            cells = row.find_all(["th", "td"], recursive=False)
            cell_text = [
                cell.get_text(" ", strip=True)[:180]
                for cell in cells
            ]

            print(f"  ROW {row_index}: {cell_text}")

            for anchor in row.find_all("a", href=True)[:5]:
                title = anchor.get_text(" ", strip=True)
                print(f"    LINK: {title[:120]}")
                print(f"      HREF: {anchor['href']}")

print("\nProbe completed. No files or database records were modified.")
