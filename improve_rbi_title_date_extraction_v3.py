import json
import re
from pathlib import Path
from datetime import datetime

SOURCE = Path("data/versions/rbi_master_directions_review_deduplicated.json")
OUTPUT = Path("data/versions/rbi_master_directions_date_preview_v3.json")

MONTH = (
    r"January|February|March|April|May|June|July|August|September|"
    r"October|November|December"
)

DATE_PATTERN = re.compile(
    rf"\b(?:({MONTH})\s+\d{{1,2}},?\s+\d{{4}}|"
    rf"\d{{1,2}}\s+({MONTH})\s+\d{{4}})\b",
    re.IGNORECASE,
)

INCOMPLETE_PATTERN = re.compile(
    rf"\b(?:{MONTH})\s+\d{{1,2}},?(?!\s*\d{{4}})",
    re.IGNORECASE,
)

UPDATE_PATTERN = re.compile(
    r"\bupdated\s+(?:as\s+on|up\s+to)\b", re.IGNORECASE
)
EFFECTIVE_PATTERN = re.compile(
    r"\beffective\s+(?:from|on|as\s+of)\b", re.IGNORECASE
)
ISSUE_PATTERN = re.compile(r"\bdated\b", re.IGNORECASE)

def parse_date(value):
    value = re.sub(r"\s+", " ", value.strip())
    for fmt in ("%B %d, %Y", "%B %d %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None

items = json.loads(SOURCE.read_text(encoding="utf-8"))
result = []

for item in items:
    record = dict(item)
    title = record.get("title", "")

    record["issue_date_hints"] = []
    record["updated_as_of_date_hints"] = []
    record["effective_date_hints"] = []
    record["unspecified_title_date_hints"] = []
    record["incomplete_date_hints"] = []

    for match in DATE_PATTERN.finditer(title):
        parsed = parse_date(match.group(0))
        if not parsed:
            continue

        # Use the nearest applicable date-label phrase before this date.
        preceding = title[:match.start()]
        triggers = []

        for pattern, label in (
            (UPDATE_PATTERN, "update"),
            (EFFECTIVE_PATTERN, "effective"),
            (ISSUE_PATTERN, "issue"),
        ):
            matches = list(pattern.finditer(preceding))
            if matches:
                triggers.append((matches[-1].start(), label))

        label = max(triggers)[1] if triggers else "unspecified"

        field = {
            "update": "updated_as_of_date_hints",
            "effective": "effective_date_hints",
            "issue": "issue_date_hints",
            "unspecified": "unspecified_title_date_hints",
        }[label]

        if parsed not in record[field]:
            record[field].append(parsed)

    # Flag date fragments that lack a four-digit year.
    for match in INCOMPLETE_PATTERN.finditer(title):
        fragment = match.group(0).rstrip(",").strip()

        # Ignore a fragment if a complete date begins at this position.
        if DATE_PATTERN.match(title, match.start()):
            continue

        if fragment not in record["incomplete_date_hints"]:
            record["incomplete_date_hints"].append(fragment)

    record["title_date_verified"] = False

    if record["incomplete_date_hints"]:
        record["date_review_status_v3"] = "needs_manual_date_review"
    elif any(record[field] for field in (
        "issue_date_hints",
        "updated_as_of_date_hints",
        "effective_date_hints",
        "unspecified_title_date_hints",
    )):
        record["date_review_status_v3"] = "needs_official_verification"
    else:
        record["date_review_status_v3"] = "no_title_date_found"

    result.append(record)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    json.dumps(result, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("Input records:", len(items))
for field in (
    "issue_date_hints",
    "updated_as_of_date_hints",
    "effective_date_hints",
    "unspecified_title_date_hints",
    "incomplete_date_hints",
):
    print(f"Records with {field}: {sum(bool(x[field]) for x in result)}")

print("All title dates unverified:", all(
    x["title_date_verified"] is False for x in result
))
print("Output:", OUTPUT)
print("Original files and database unchanged.")
