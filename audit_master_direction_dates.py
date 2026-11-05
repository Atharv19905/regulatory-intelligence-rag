
import json
from pathlib import Path

path = Path(
    "data/versions/rbi_master_directions_enriched.json"
)

data = json.loads(path.read_text(encoding="utf-8"))
records = data["records"]

conflicts = [
    r for r in records
    if r.get("date_discrepancy")
]

missing = [
    r for r in records
    if not r.get("publication_date_extracted")
]

print("\n=== DATE CONFLICTS ===")
for r in conflicts:
    print("\nTitle:", r.get("title"))
    print("Existing date:", r.get("publication_date"))
    print("Extracted date:", r.get("publication_date_extracted"))
    print("Detail URL:", r.get("detail_url"))

print("\n=== MISSING EXTRACTED DATES ===")
print("Total:", len(missing))

for r in missing[:15]:
    print("\nTitle:", r.get("title"))
    print("Existing date:", r.get("publication_date"))
    print("Status:", r.get("date_review_status"))
    print("Error:", r.get("date_extraction_error"))
    print("Detail URL:", r.get("detail_url"))

print("\nAudit complete. No files modified.")
