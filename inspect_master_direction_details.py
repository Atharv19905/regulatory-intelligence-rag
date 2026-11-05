
import json
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

INPUT = Path("data/versions/rbi_master_directions_discovered.json")

data = json.loads(INPUT.read_text(encoding="utf-8"))
records = data["records"]

# Inspect three known records with missing dates.
targets = {
    "13442",
    "13272",
    "13138",
}

session = requests.Session()
session.headers.update({
    "User-Agent": "RegulatoryResearchProject/1.0"
})

for record in records:
    url = record.get("detail_url", "")

    if not any(f"id={item}" in url for item in targets):
        continue

    print("\n" + "=" * 80)
    print("DISCOVERED TITLE:", record.get("title"))
    print("DETAIL URL:", url)

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        print("REQUEST ERROR:", exc)
        continue

    soup = BeautifulSoup(response.text, "html.parser")

    # Print likely metadata and date-related text without
    # changing any project files.
    for tag in soup.find_all(["title", "h1", "h2", "h3"]):
        text = " ".join(tag.get_text(" ", strip=True).split())
        if text:
            print("HEADING:", text[:300])

    for line in soup.stripped_strings:
        lowered = line.lower()
        if any(word in lowered for word in (
            "dated", "date of issue", "issued on",
            "effective from", "updated as on",
            "master direction", "notification no."
        )):
            print("MATCH:", line[:300])

    print("PDF links:")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if ".pdf" in href.lower():
            print(" ", urljoin(url, href))

print("\nInspection complete. No files or database records modified.")
