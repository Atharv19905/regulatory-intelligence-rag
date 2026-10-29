
import json
from pathlib import Path
from urllib.parse import urlparse, urldefrag

INPUT = Path("data/versions/rbi_source_inspection.json")
OUTPUT = Path("data/versions/rbi_document_candidates.json")

records = json.loads(INPUT.read_text(encoding="utf-8"))
candidates = {}

for record in records:
    if record.get("status_code") != 200:
        continue

    source_id = record["source_id"]

    for link_type in ("pdf_links", "document_links"):
        for item in record.get(link_type, []):
            url = urldefrag(item["url"].strip())[0]
            parsed = urlparse(url)

            host = (parsed.hostname or "").lower()
            if not (
                host == "rbi.org.in"
                or host.endswith(".rbi.org.in")
            ):
                continue

            # Normalize only the URL fragment and trailing slash.
            key = url.rstrip("/").lower()

            if key not in candidates:
                candidates[key] = {
                    "url": url,
                    "title": item["title"],
                    "document_type": (
                        "pdf"
                        if ".pdf" in parsed.path.lower()
                        else "html_or_other"
                    ),
                    "source_ids": [],
                    "review_status": "pending",
                }

            if source_id not in candidates[key]["source_ids"]:
                candidates[key]["source_ids"].append(source_id)

result = list(candidates.values())
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    json.dumps(result, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("Unique candidate URLs:", len(result))
print("PDF candidates:", sum(x["document_type"] == "pdf" for x in result))
print("Other candidates:", sum(x["document_type"] != "pdf" for x in result))
print("Saved:", OUTPUT)
print("\nCandidates by source family:")

for record in records:
    source_id = record["source_id"]
    count = sum(source_id in x["source_ids"] for x in result)
    print(f"{source_id}: {count}")
