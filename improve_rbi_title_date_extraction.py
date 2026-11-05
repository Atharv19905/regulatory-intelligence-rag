import json
import re
from pathlib import Path
from datetime import datetime

SOURCE = Path("data/versions/rbi_master_directions_review_deduplicated.json")
OUTPUT = Path("data/versions/rbi_master_directions_date_preview_v2.json")

MONTH = (
    r"January|February|March|April|May|June|July|August|September|"
    r"October|November|December"
)

COMPLETE_DATE = re.compile(
    rf"\b(?:({MONTH})\s+\d{{1,2}},?\s+\d{{4}}|"
    rf"\d{{1,2}}\s+({MONTH})\s+\d{{4}})\b",
    re.IGNORECASE,
)

INCOMPLETE_DATE = re.compile(
    rf"\b({MONTH})\s+\d{{1,2}}(?:,)?(?=\s*(?:\)|$))",
    re.IGNORECASE,
)

UPDATE_MARKER = re.compile(r"\bupdated\s+as\s+on\b", re.IGNORECASE)

def normalize_date(value):
    value = re.sub(r"\s+", " ", value.strip())
    for fmt in ("%B %d, %Y", "%B %d %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None

items = json.loads(SOURCE.read_text(encoding="utf-8"))
result = []

for item in items:
    record = dict(item)
    title = record.get("title", "")

    update_match = UPDATE_MARKER.search(title)
    update_start = update_match.start() if update_match else len(title)

    issue_hints = []
    update_hints = []

    for match in COMPLETE_DATE.finditer(title):
        parsed = normalize_date(match.group(0))
        if not parsed:
            continue

        target = update_hints if match.start() >= update_start else issue_hints
        if parsed not in target:
            target.append(parsed)

    incomplete = []
    for match in INCOMPLETE_DATE.finditer(title):
        fragment = match.group(0).rstrip(",").strip()
        if not re.search(rf"{re.escape(fragment)}\s+\d{{4}}", title, re.IGNORECASE):
            incomplete.append(fragment)

    record["issue_date_hints"] = issue_hints
    record["updated_as_of_date_hints"] = update_hints
    record["incomplete_date_hints"] = sorted(set(incomplete))
    record["title_date_verified"] = False

    if issue_hints or update_hints:
        record["date_review_status_v2"] = "needs_official_verification"
    elif incomplete:
        record["date_review_status_v2"] = "needs_manual_date_review"
    else:
        record["date_review_status_v2"] = "no_title_date_found"

    result.append(record)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    json.dumps(result, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("Input records:", len(items))
print("Issue-date hints:", sum(bool(x["issue_date_hints"]) for x in result))
print("Update-date hints:", sum(bool(x["updated_as_of_date_hints"]) for x in result))
print("Incomplete date hints:", sum(bool(x["incomplete_date_hints"]) for x in result))
print("No complete or incomplete title dates:", sum(
    not x["issue_date_hints"]
    and not x["updated_as_of_date_hints"]
    and not x["incomplete_date_hints"]
    for x in result
))
print("All dates remain unverified:", all(
    x["title_date_verified"] is False for x in result
))
print("Output:", OUTPUT)
print("Original files and database unchanged.")
