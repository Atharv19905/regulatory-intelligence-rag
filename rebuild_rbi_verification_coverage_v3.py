import json
from pathlib import Path
from collections import Counter

BASE = Path(__file__).resolve().parent / "data" / "versions"

PREVIEW = BASE / "rbi_master_directions_date_preview_v3.json"
SAMPLE = BASE / "rbi_date_verifications_sample.json"
BATCH = BASE / "rbi_master_directions_verification_batch_01.json"
OUTPUT = BASE / "rbi_verification_coverage_report_v3.json"


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


preview = load_json(PREVIEW)
sample = load_json(SAMPLE)
batch = load_json(BATCH)

# Build the unique candidate ID set.
candidate_ids = {
    str(record["rbi_direction_id"])
    for record in preview
}

# Merge verification records by RBI ID.
verification_records = {}

for source_name, records in [
    ("sample", sample),
    ("batch_01", batch),
]:
    for record in records:
        rid = str(record["rbi_direction_id"])

        if rid not in candidate_ids:
            continue

        if rid in verification_records:
            raise ValueError(
                f"Duplicate verification entry for RBI ID {rid}"
            )

        verification_records[rid] = {
            **record,
            "verification_source": source_name,
        }

# Count verification statuses.
status_counts = Counter(
    record.get("verification_status", "unknown")
    for record in verification_records.values()
)

unreviewed_ids = sorted(
    candidate_ids - set(verification_records)
)

report = {
    "total_unique_candidates": len(candidate_ids),
    "matched_verification_records": len(verification_records),
    "status_counts": dict(status_counts),
    "not_yet_reviewed_count": len(unreviewed_ids),
    "not_yet_reviewed_ids": unreviewed_ids,
    "verification_records": [
        verification_records[rid]
        for rid in sorted(verification_records)
    ],
    "notes": [
        "Coverage counts verification entries, not independently confirmed facts.",
        "Records marked verified_from_pasted_official_page_text rely on user-provided RBI page excerpts.",
        "No SQLite or Qdrant data was accessed.",
    ],
}

# Validate arithmetic before writing.
if len(candidate_ids) != (
    len(verification_records) + len(unreviewed_ids)
):
    raise ValueError("Coverage totals do not reconcile.")

with OUTPUT.open("w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("Coverage report created:", OUTPUT)
print("Unique candidates:", len(candidate_ids))
print("Verification entries:", len(verification_records))
print("Not yet reviewed:", len(unreviewed_ids))
print("Status counts:", dict(status_counts))
print("Coverage totals reconcile.")