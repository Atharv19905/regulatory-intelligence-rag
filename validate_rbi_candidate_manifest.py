
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

path = Path("data/versions/rbi_document_candidates.json")
items = json.loads(path.read_text(encoding="utf-8"))

print("Total candidates:", len(items))
print("Document types:", dict(Counter(
    item.get("document_type", "missing") for item in items
)))

print("\nCandidate title examples:")
for item in items[:20]:
    print("-", item.get("title", "(no title)"))
    print(" ", item["url"])

print("\nPDF candidates:")
pdfs = [
    item for item in items
    if item.get("document_type") == "pdf"
]
for item in pdfs[:30]:
    print("-", item.get("title", "(no title)"))
    print(" ", item["url"])

print("\nMost common source memberships:")
membership_counts = Counter()
for item in items:
    for source_id in item.get("source_ids", []):
        membership_counts[source_id] += 1

for source_id, count in membership_counts.most_common():
    print(f"{source_id}: {count}")

print("\nURL host distribution:")
hosts = Counter(
    (urlparse(item["url"]).hostname or "").lower()
    for item in items
)
for host, count in hosts.most_common(15):
    print(f"{host}: {count}")
