import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "data" / "versions" / "rbi_master_directions_verification_batch_01.json"

UPDATES = {
    "10190": {
        "verified_publication_date": None,
        "verified_updated_as_of_date": "2022-05-24",
        "verified_effective_date": None,
        "superseded_by": "12736",
        "verification_status": "verified_from_pasted_official_page_text",
        "official_page_evidence": "Pasted RBI text identifies the May 24, 2022 version as superseded by Directions dated October 1, 2024, RBI ID 12736.",
        "verification_notes": "October 1, 2024 belongs to successor ID 12736, not the older direction. Original publication date for ID 10190 was not present in the pasted excerpt.",
        "update_date_history": ["2022-05-24"],
    },
    "11037": {
        "verified_publication_date": "2017-07-03",
        "verified_updated_as_of_date": None,
        "verified_effective_date": None,
        "superseded_by": None,
        "verification_status": "verified_from_pasted_official_page_text",
        "official_page_evidence": "Pasted RBI text shows RBI/FIDD/2017-2018/55 and July 03, 2017.",
        "verification_notes": "July 3, 2017 is the issue date shown. No update history or supersession notice was included; current status is not established.",
        "update_date_history": [],
    },
    "10192": {
        "verified_publication_date": "2016-01-01",
        "verified_updated_as_of_date": "2024-09-06",
        "verified_effective_date": None,
        "superseded_by": None,
        "verification_status": "verified_from_pasted_official_page_text",
        "official_page_evidence": "Pasted RBI text shows January 1, 2016 and update history through September 06, 2024.",
        "verification_notes": "Dates transcribed from the user's pasted RBI excerpt; whether the direction remains current is not established.",
        "update_date_history": ["2016-02-11", "2017-04-12", "2017-08-02", "2018-06-20", "2022-08-23", "2022-08-24", "2023-12-22", "2024-09-06"],
    },
    "10196": {
        "verified_publication_date": "2016-01-01",
        "verified_updated_as_of_date": "2022-09-01",
        "verified_effective_date": None,
        "superseded_by": None,
        "verification_status": "verified_from_pasted_official_page_text",
        "official_page_evidence": "Pasted RBI text shows January 1, 2016 and update history through September 01, 2022.",
        "verification_notes": "Dates transcribed from the user's pasted RBI excerpt; whether the direction remains current is not established.",
        "update_date_history": ["2016-02-04", "2018-04-11", "2022-06-06", "2022-09-01"],
    },
    "10203": {
        "verified_publication_date": "2016-01-01",
        "verified_updated_as_of_date": "2026-05-13",
        "verified_effective_date": None,
        "superseded_by": None,
        "verification_status": "verified_from_pasted_official_page_text",
        "official_page_evidence": "Pasted RBI text shows January 1, 2016 and update history through May 13, 2026.",
        "verification_notes": "Dates transcribed from the user's pasted RBI excerpt; whether the direction remains current is not established.",
        "update_date_history": ["2017-06-16", "2017-07-28", "2018-09-10", "2018-11-12", "2026-05-13"],
    },
}

def validate_date(value, field, rid):
    if value is not None:
        if not isinstance(value, str):
            raise ValueError(f"{rid}: {field} must be a date string or null")
        datetime.strptime(value, "%Y-%m-%d")

def main():
    if not TARGET.is_file():
        raise FileNotFoundError(
            f"Could not find target JSON:\n{TARGET}\n"
            "Place this script in your regulatory-intelligence project root."
        )

    with TARGET.open("r", encoding="utf-8") as f:
        records = json.load(f)
    if not isinstance(records, list):
        raise TypeError("Expected a top-level JSON list; no changes made.")

    by_id = {}
    for rec in records:
        if not isinstance(rec, dict):
            raise TypeError("Every record must be a JSON object.")
        rid = str(rec.get("rbi_direction_id", ""))
        if rid in by_id:
            raise ValueError(f"Duplicate RBI ID found: {rid}")
        by_id[rid] = rec

    missing = sorted(set(UPDATES) - set(by_id))
    if missing:
        raise ValueError(f"Missing expected RBI IDs: {missing}; no changes made.")

    for rid, fields in UPDATES.items():
        for field in ("verified_publication_date", "verified_updated_as_of_date", "verified_effective_date"):
            validate_date(fields[field], field, rid)
        for date_value in fields["update_date_history"]:
            validate_date(date_value, "update_date_history", rid)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = TARGET.with_name(f"{TARGET.stem}.before_batch01_update_{stamp}{TARGET.suffix}")
    shutil.copy2(TARGET, backup)

    for rid, fields in UPDATES.items():
        by_id[rid].update(fields)

    temp = TARGET.with_suffix(TARGET.suffix + ".tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
            f.write("\n")
        with temp.open("r", encoding="utf-8") as f:
            check_records = json.load(f)
        check_by_id = {str(rec["rbi_direction_id"]): rec for rec in check_records}
        for rid, fields in UPDATES.items():
            for field, expected in fields.items():
                if check_by_id[rid].get(field) != expected:
                    raise ValueError(f"Validation failed: RBI {rid}, field {field}")
        temp.replace(TARGET)
    finally:
        if temp.exists():
            temp.unlink()

    print("Update completed successfully.")
    print(f"Updated JSON: {TARGET}")
    print(f"Backup created: {backup}")
    print("Updated IDs: " + ", ".join(UPDATES))
    print("SQLite and Qdrant were not accessed.")

if __name__ == "__main__":
    main()
