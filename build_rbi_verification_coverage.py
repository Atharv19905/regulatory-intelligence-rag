import json
from pathlib import Path
from collections import Counter

BASE = Path("data/versions")
PREVIEW = BASE / "rbi_master_directions_date_preview_v3.json"
SAMPLE = BASE / "rbi_date_verifications_sample.json"
OUTPUT = BASE / "rbi_verification_coverage_report.json"

items = json.loads(PREVIEW.read_text(encoding="utf-8"))
sample = json.loads(SAMPLE.read_text(encoding="utf-8"))

sample_by_id = {x["rbi_direction_id"]: x for x in sample}
status_counts = Counter()
needs_verification = []

for item in items:
    direction_id = item["rbi_direction_id"]
    verification = sample_by_id.get(direction_id)

    if verification:
        status = verification["verification_status"]
    else:
        status = "not_yet_reviewed"

    status_counts[status] += 1

    if status != "verified_sample":
        needs_verification.append({
            "rbi_direction_id": direction_id,
            "title": item.get("title"),
            "url": item.get("url"),
            "verification_status": status,
        })

report = {
    "total_candidates": len(items),
    "sample_verification_records": len(sample),
    "verification_status_counts": dict(status_counts),
    "unresolved_or_unreviewed_count": len(needs_verification),
    "unresolved_or_unreviewed": needs_verification,
    "note": (
        "Coverage report only. Existing sample statuses reflect the earlier "
        "review and are not independently reverified by this script."
    ),
}

OUTPUT.write_text(
    json.dumps(report, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("Total candidates:", report["total_candidates"])
print("Sample records:", report["sample_verification_records"])
print("Status counts:")
for status, count in sorted(status_counts.items()):
    print(f"  {status}: {count}")
print("Unresolved or unreviewed:", len(needs_verification))
print("Saved:", OUTPUT)
print("Preview, verification file, SQLite, and Qdrant unchanged.")
