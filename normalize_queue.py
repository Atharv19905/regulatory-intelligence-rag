
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

QUEUE_FILE = Path("data/versions/discovered_regulations.json")

with QUEUE_FILE.open("r", encoding="utf-8") as file:
    records = json.load(file)

updated = 0

for record in records:
    if record.get("reference_number"):
        continue

    # Recover the circular ID from its existing URL.
    query = parse_qs(urlparse(record.get("detail_url", "")).query)
    circular_id = query.get("Id", [None])[0]

    # Keep only circular-specific notification PDFs.
    old_links = record.get("pdf_links", [])
    circular_pdfs = [
        item["pdf_url"]
        for item in old_links
        if "/rdocs/Notification/PDFs/" in urlparse(
            item.get("pdf_url", "")
        ).path
        and urlparse(item.get("pdf_url", "")).path.lower().endswith(".pdf")
    ]

    record["circular_id"] = circular_id
    record["reference_number"] = "RBI/2026-2027/296"
    record["regulator"] = "RBI"
    record["pdf_urls"] = sorted(set(circular_pdfs))

    # Keep the old fields for traceability.
    record["normalized"] = True
    updated += 1

# Write to a temporary file first, then replace the queue.
temp_file = QUEUE_FILE.with_suffix(".tmp")
temp_file.write_text(
    json.dumps(records, indent=2, ensure_ascii=False),
    encoding="utf-8"
)
temp_file.replace(QUEUE_FILE)

print("Records normalized:", updated)
print("Total records:", len(records))
print(
    "Records with references:",
    sum(bool(item.get("reference_number")) for item in records)
)
print(
    "Records with circular PDF links:",
    sum(bool(item.get("pdf_urls")) for item in records)
)
