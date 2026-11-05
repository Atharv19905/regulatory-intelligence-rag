
import json
import shutil
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent / "data" / "versions"

TARGET = BASE / "rbi_master_directions_verification_batch_02.json"

UPDATES = {
    "10205": {
        "verified_publication_date": "2016-01-01",
        "verified_updated_as_of_date": "2026-10-01",
        "verified_effective_date": None,
        "superseded_by": None,
        "update_date_history": [
            "2016-04-28", "2016-10-20", "2017-05-19",
            "2018-08-31", "2020-09-08", "2022-12-22",
            "2026-10-01"
        ],
        "official_page_evidence": "RBI/FED/2015-16/16, Master Direction No.2/2015-16, dated January 1, 2016; updated through October 1, 2026.",
        "verification_notes": "Dates transcribed from user-provided RBI page excerpt. Effective date and successor ID not established."
    },

    "10404": {
        "verified_publication_date": "2016-01-01",
        "verified_updated_as_of_date": "2021-05-18",
        "verified_effective_date": None,
        "superseded_by": None,
        "update_date_history": [
            "2016-05-17", "2018-05-10", "2019-02-28",
            "2019-03-29", "2021-05-18"
        ],
        "official_page_evidence": "RBI/FED/2015-16/6, Master Direction No.10/2015-16, dated January 1, 2016; updated through May 18, 2021.",
        "verification_notes": "Dates transcribed from user-provided RBI page excerpt. Effective date and successor ID not established."
    },

    "10476": {
        "verified_publication_date": "2016-07-01",
        "verified_updated_as_of_date": "2018-11-22",
        "verified_effective_date": None,
        "superseded_by": None,
        "update_date_history": ["2018-11-22"],
        "official_page_evidence": "RBI/IDMD/2016-17/29, Master Direction dated July 1, 2016; updated November 22, 2018.",
        "verification_notes": "Dates transcribed from user-provided RBI page excerpt. Effective date and successor ID not established."
    },

    "10485": {
        "verified_publication_date": "2016-07-05",
        "verified_updated_as_of_date": "2026-10-01",
        "verified_effective_date": None,
        "superseded_by": None,
        "update_date_history": [
            "2017-02-02", "2017-03-21", "2017-10-13",
            "2017-11-09", "2018-02-28", "2018-04-02",
            "2020-01-07", "2020-06-01", "2020-09-01",
            "2023-06-06", "2024-05-03", "2025-04-16",
            "2025-09-22", "2026-09-22", "2026-10-01"
        ],
        "official_page_evidence": "RBI/FMRD/2016-17/31, FMRD Master Direction dated July 5, 2016; updated through October 1, 2026.",
        "verification_notes": "Dates transcribed from user-provided RBI page excerpt. Effective date and successor ID not established."
    },

    "10738": {
        "verified_publication_date": "2016-01-01",
        "verified_updated_as_of_date": "2021-12-07",
        "verified_effective_date": None,
        "superseded_by": None,
        "update_date_history": ["2016-11-17", "2021-12-07"],
        "official_page_evidence": "RBI/FED/2015-16/5, FED Master Direction No.9/2015-16, dated January 1, 2016; updated December 7, 2021.",
        "verification_notes": "Dates transcribed from user-provided RBI page excerpt. Effective date and successor ID not established."
    },

    "10833": {
        "verified_publication_date": "2017-01-17",
        "verified_updated_as_of_date": "2021-07-28",
        "verified_effective_date": None,
        "superseded_by": None,
        "update_date_history": ["2021-07-28"],
        "official_page_evidence": "RBI/DPSS/2016-17/51, Master Direction dated January 17, 2017; updated July 28, 2021.",
        "verification_notes": "Dates transcribed from user-provided RBI page excerpt. Effective date and successor ID not established."
    },

    "10868": {
        "verified_publication_date": "2017-02-22",
        "verified_updated_as_of_date": "2026-09-29",
        "verified_effective_date": None,
        "superseded_by": None,
        "update_date_history": [
            "2024-02-29", "2025-11-28", "2026-09-29"
        ],
        "official_page_evidence": "RBI/FED/2016-17/52, FED Master Direction No.1/2016-17, dated February 22, 2017; updated September 29, 2026.",
        "verification_notes": "Dates transcribed from user-provided RBI page excerpt. Effective date and successor ID not established."
    },

    "11060": {
        "verified_publication_date": "2017-07-24",
        "verified_updated_as_of_date": "2026-02-09",
        "verified_effective_date": None,
        "superseded_by": None,
        "update_date_history": [
            "2018-04-25", "2022-07-29", "2023-12-28",
            "2024-06-11", "2025-07-23", "2026-02-09"
        ],
        "official_page_evidence": "RBI/FIDD/2017-2018/56, Master Direction dated July 24, 2017; updated through February 9, 2026.",
        "verification_notes": "Dates transcribed from user-provided RBI page excerpt. Effective date and successor ID not established."
    },

    "11322": {
        "verified_publication_date": "2018-07-02",
        "verified_updated_as_of_date": None,
        "verified_effective_date": None,
        "superseded_by": None,
        "update_date_history": [],
        "official_page_evidence": "RBI/IDMD/2018-19/61, IDMD.CDD No.21/13.01.299/2018-19, dated July 2, 2018.",
        "verification_notes": "Publication date transcribed from user-provided excerpt. No separate update date or successor information was provided."
    },

    "11500": {
        "verified_publication_date": "2019-03-15",
        "verified_updated_as_of_date": None,
        "verified_effective_date": None,
        "superseded_by": None,
        "update_date_history": [],
        "official_page_evidence": "RBI/2018-19/141, FMRD.FMSD.11/11.01.012/2018-19, dated March 15, 2019.",
        "verification_notes": "Publication date transcribed from user-provided excerpt. No separate update date or successor information was provided."
    }
}


def validate_date(value):
    if value is not None:
        datetime.strptime(value, "%Y-%m-%d")


def main():
    if not TARGET.exists():
        raise FileNotFoundError(TARGET)

    records = json.loads(TARGET.read_text(encoding="utf-8"))

    if not isinstance(records, list) or len(records) != 10:
        raise ValueError("Expected exactly 10 Batch 02 records.")

    ids = [str(r["rbi_direction_id"]) for r in records]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate RBI IDs detected.")

    if set(ids) != set(UPDATES):
        raise ValueError("RBI IDs do not match expected Batch 02 IDs.")

    for rid, update in UPDATES.items():
        for field in [
            "verified_publication_date",
            "verified_updated_as_of_date",
            "verified_effective_date"
        ]:
            validate_date(update[field])

        for date in update["update_date_history"]:
            validate_date(date)

        if update["update_date_history"] != sorted(
            update["update_date_history"]
        ):
            raise ValueError(f"History is not chronological: {rid}")

        latest = update["verified_updated_as_of_date"]
        history = update["update_date_history"]

        if latest is not None and history and history[-1] != latest:
            raise ValueError(f"Latest update mismatch: {rid}")

    # Create backup before changing the original file.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup = TARGET.with_name(
        f"{TARGET.stem}.before_batch02_update_{timestamp}{TARGET.suffix}"
    )

    shutil.copy2(TARGET, backup)

    for record in records:
        rid = str(record["rbi_direction_id"])
        record.update(UPDATES[rid])
        record["verification_status"] = (
            "verified_from_pasted_official_page_text"
        )

    # Write to a temporary file first.
    temp = TARGET.with_suffix(".tmp")

    temp.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Validate temporary output before replacing original.
    check = json.loads(temp.read_text(encoding="utf-8"))

    if len(check) != 10:
        raise ValueError("Output validation failed.")

    for record in check:
        if record["verification_status"] != (
            "verified_from_pasted_official_page_text"
        ):
            raise ValueError("Verification status validation failed.")

    temp.replace(TARGET)

    print("\nBatch 02 updated successfully.")
    print("Updated file:", TARGET)
    print("Backup created:", backup)
    print("Records updated:", len(records))
    print("SQLite and Qdrant were not accessed.")
    print("Evidence basis: RBI page excerpts supplied in this conversation.")


if __name__ == "__main__":
    main()
