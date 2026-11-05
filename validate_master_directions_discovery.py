
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

path = Path("data/versions/rbi_master_directions_discovered.json")
data = json.loads(path.read_text(encoding="utf-8"))
records = data["records"]

print("Total records:", len(records))
print("Unique detail URLs:", len({
    r.get("detail_url") for r in records if r.get("detail_url")
}))
print("Missing titles:", sum(not r.get("title") for r in records))
print("Missing detail URLs:", sum(not r.get("detail_url") for r in records))
print("Missing publication dates:", sum(
    not r.get("publication_date") for r in records
))
print("Missing PDF URLs:", sum(not r.get("pdf_url") for r in records))

print("\nPDF URL host counts:")
hosts = Counter(
    urlparse(r["pdf_url"]).netloc
    for r in records if r.get("pdf_url")
)
for host, count in hosts.most_common():
    print(f"{host}: {count}")

print("\nRecords with missing dates (first 15):")
missing_dates = [
    r for r in records if not r.get("publication_date")
]
for r in missing_dates[:15]:
    print(f"- {r.get('title')}")
    print(f"  Detail: {r.get('detail_url')}")

print("\nDuplicate detail URLs:")
url_counts = Counter(
    r.get("detail_url") for r in records if r.get("detail_url")
)
duplicates = [(url, count) for url, count in url_counts.items() if count > 1]
print("Duplicate URL groups:", len(duplicates))
for url, count in duplicates[:10]:
    print(f"{count} occurrences: {url}")
