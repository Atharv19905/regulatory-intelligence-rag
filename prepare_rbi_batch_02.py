import json
from pathlib import Path

BASE = Path(__file__).resolve().parent / "data" / "versions"

SOURCE = BASE / "rbi_master_directions_review_deduplicated.json"
SAMPLE = BASE / "rbi_date_verifications_sample.json"
BATCH_01 = BASE / "rbi_master_directions_verification_batch_01.json"
OUTPUT = BASE / "rbi_master_directions_verification_batch_02.json"

def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

candidates = load_json(SOURCE)
sample = load_json(SAMPLE)
batch_01 = load_json(BATCH_01)

already_selected = {
    str(r["rbi_direction_id"])
    for r in sample + batch_01
}

remaining = [
    r for r in candidates
    if str(r["rbi_direction_id"]) not in already_selected
    and r.get("review_status") == "pending"
]

if len(remaining) < 10:
    raise ValueError(f"Only {len(remaining)} pending candidates remain.")

batch_02 = remaining[:10]

with OUTPUT.open("w", encoding="utf-8") as f:
    json.dump(batch_02, f, ensure_ascii=False, indent=2)

print("Batch 02 created:", OUTPUT)
print("Selected records:", len(batch_02))
print()

for i, record in enumerate(batch_02, start=1):
    print(
        f"{i}. RBI ID: {record['rbi_direction_id']}\n"
        f"   Title: {record.get('title', 'No title')}\n"
        f"   URL: {record.get('url', 'No URL')}\n"
    )

print("Original candidate and verification files were not modified.")
print("SQLite and Qdrant were not accessed.")