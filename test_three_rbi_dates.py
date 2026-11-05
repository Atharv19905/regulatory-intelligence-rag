
import json
import requests

from enrich_rbi_master_direction_dates import extract_dates

INPUT_FILE = "data/versions/rbi_master_directions_discovered.json"
TARGET_IDS = {"11060", "11037", "12427"}

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

records = data["records"]
session = requests.Session()

try:
    found_ids = set()

    for record in records:
        detail_url = record.get("detail_url", "")
        document_id = detail_url.split("id=")[-1].split("&")[0]

        if document_id not in TARGET_IDS:
            continue

        found_ids.add(document_id)

        print(f"\n{'=' * 50}")
        print("ID:", document_id)
        print("Title:", record.get("title"))

        try:
            result = extract_dates(session, record)

            print("Existing publication date:", record.get("publication_date"))
            print("Extracted publication date:", result.get("publication_date_extracted"))
            print("Updated as of:", result.get("updated_as_of_date"))
            print("Review status:", result.get("date_review_status"))
            print("Discrepancy:", result.get("date_discrepancy"))

        except Exception as exc:
            print("ERROR:", repr(exc))

    print("\nTarget IDs found:", sorted(found_ids))
    print("Target IDs missing:", sorted(TARGET_IDS - found_ids))

finally:
    session.close()
