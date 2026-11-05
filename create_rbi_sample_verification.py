import json
from pathlib import Path

SOURCE = Path("data/versions/rbi_master_directions_date_preview_v3.json")
OUTPUT = Path("data/versions/rbi_date_verifications_sample.json")

items = json.loads(SOURCE.read_text(encoding="utf-8"))

verified = {
    "12839": {
        "publication_date_verified": "2025-04-22",
        "updated_as_of_date_verified": "2025-04-24",
        "effective_date_verified": None,
        "superseded_by": None,
        "verification_status": "verified_sample",
        "verification_source_url": "https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=12839",
        "verification_notes": "Page evidence reported in the sample review. Confirm legal effective date separately if needed."
    },
    "13399": {
        "publication_date_verified": "2026-04-27",
        "updated_as_of_date_verified": None,
        "effective_date_verified": "2027-04-01",
        "superseded_by": None,
        "verification_status": "verified_sample",
        "verification_source_url": "https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=13399",
        "verification_notes": "Issue and effective dates reported in the sample review."
    },
    "10204": {
        "publication_date_verified": "2016-01-01",
        "updated_as_of_date_verified": "2018-11-22",
        "effective_date_verified": None,
        "superseded_by": None,
        "verification_status": "verified_sample",
        "verification_source_url": "https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=10204",
        "verification_notes": "The sample review reported the full update date as November 22, 2018."
    },
    "11959": {
        "publication_date_verified": "2020-09-04",
        "updated_as_of_date_verified": None,
        "effective_date_verified": None,
        "superseded_by": None,
        "verification_status": "partial_verification",
        "verification_source_url": "https://rbi.org.in/Scripts/NotificationUser.aspx?Id=11959&Mode=0",
        "verification_notes": "Issue date and supersession were reported in the sample review. The successor document ID and legal effective date have not been recorded here."
    },
    "11200": {
        "publication_date_verified": None,
        "updated_as_of_date_verified": None,
        "effective_date_verified": None,
        "superseded_by": None,
        "verification_status": "needs_confirmation",
        "verification_source_url": "https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=11200",
        "verification_notes": "The title suggests an update through 2026-06-15, but the indexed page result conflicted. Do not treat the title date as verified."
    }
}

records = []
for direction_id, details in verified.items():
    matching = [
        item for item in items
        if item.get("rbi_direction_id") == direction_id
    ]

    if not matching:
        raise ValueError(f"RBI ID {direction_id} not found in source preview")

    records.append({
        "rbi_direction_id": direction_id,
        "title": matching[0].get("title"),
        **details
    })

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    json.dumps(records, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print("Verification records:", len(records))
print("Verified sample records:", sum(
    x["verification_status"] == "verified_sample" for x in records
))
print("Partial verification:", sum(
    x["verification_status"] == "partial_verification" for x in records
))
print("Needs confirmation:", sum(
    x["verification_status"] == "needs_confirmation" for x in records
))
print("Saved:", OUTPUT)
print("Source preview, SQLite, and Qdrant unchanged.")
