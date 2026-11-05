import json
from pathlib import Path

base = Path("data/versions")
preview_path = base / "rbi_master_directions_date_preview_v3.json"
sample_path = base / "rbi_date_verifications_sample.json"
output_path = base / "rbi_master_directions_verification_batch_01.json"

records = json.loads(preview_path.read_text(encoding="utf-8"))
sample = json.loads(sample_path.read_text(encoding="utf-8"))

if isinstance(sample, dict):
    sample = sample.get("records", sample.get("verifications", []))

already_reviewed = {
    str(r.get("rbi_direction_id"))
    for r in sample
    if isinstance(r, dict) and r.get("rbi_direction_id") is not None
}

eligible = [
    r for r in records
    if str(r.get("rbi_direction_id")) not in already_reviewed
]

# Select diverse date patterns in a deterministic order.
categories = [
    ("issue_date", lambda r: bool(r.get("issue_date_hints"))),
    ("effective_date", lambda r: bool(r.get("effective_date_hints"))),
    ("incomplete_date", lambda r: bool(r.get("incomplete_date_hints"))),
    ("multiple_date_types", lambda r: bool(r.get("issue_date_hints"))
        and bool(r.get("updated_as_of_date_hints"))),
    ("update_date", lambda r: bool(r.get("updated_as_of_date_hints"))),
    ("no_title_date_hints", lambda r: not any(
        r.get(k) for k in (
            "issue_date_hints",
            "updated_as_of_date_hints",
            "effective_date_hints",
            "incomplete_date_hints",
            "unspecified_title_date_hints",
        )
    )),
    ("unspecified_date", lambda r: bool(r.get("unspecified_title_date_hints"))),
]

selected = []
selected_ids = set()
selection_reason = {}

for category, predicate in categories:
    for r in eligible:
        rid = str(r.get("rbi_direction_id"))
        if rid not in selected_ids and predicate(r):
            selected.append(r)
            selected_ids.add(rid)
            selection_reason[rid] = category
            break
    if len(selected) >= 10:
        break

# Fill remaining slots with other eligible records, preserving source order.
for r in eligible:
    if len(selected) >= 10:
        break
    rid = str(r.get("rbi_direction_id"))
    if rid not in selected_ids:
        selected.append(r)
        selected_ids.add(rid)
        selection_reason[rid] = "additional_candidate"

batch = []
for r in selected:
    batch.append({
        "rbi_direction_id": r.get("rbi_direction_id"),
        "title": r.get("title"),
        "url": r.get("url"),
        "issue_date_hints": r.get("issue_date_hints", []),
        "updated_as_of_date_hints": r.get("updated_as_of_date_hints", []),
        "effective_date_hints": r.get("effective_date_hints", []),
        "incomplete_date_hints": r.get("incomplete_date_hints", []),
        "selection_reason": selection_reason[str(r.get("rbi_direction_id"))],
        "verification_status": "not_yet_verified",
        "verified_publication_date": None,
        "verified_updated_as_of_date": None,
        "verified_effective_date": None,
        "superseded_by": None,
        "official_page_evidence": None,
        "verification_notes": None,
    })

if len(batch) != 10:
    raise RuntimeError(
        f"Expected 10 candidates, but selected {len(batch)}. "
        "Review the input and sample file formats."
    )

output_path.write_text(
    json.dumps(batch, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"Created: {output_path}")
print(f"Records selected: {len(batch)}")
print(f"Previously sampled IDs excluded: {len(already_reviewed)}")
print("\nSelected candidates:")
for r in batch:
    print(
        f"ID {r['rbi_direction_id']} | "
        f"{r['selection_reason']} | {r['title']}"
    )
