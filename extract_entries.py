import pymupdf
import re
from pathlib import Path

import fitz

BASE_DIR = Path(__file__).resolve().parent
INPUT_FOLDER = BASE_DIR / "data" / "raw"

# Find the RBI sanctions-list amendment PDF.
files = [INPUT_FOLDER / "RBI_2026-2027_296.pdf"]

if not files:
    raise SystemExit(
        "No PDF found matching NOTI296*.pdf in data/raw."
    )


def clean_numbered_name(raw_name):
    """Join numbered name fields and omit fields marked NA."""
    parts = re.findall(
        r"\d+:\s*(.*?)(?=\s+\d+:\s*|$)",
        raw_name
    )

    if not parts:
        return raw_name.strip()

    return " ".join(
        part.strip()
        for part in parts
        if part.strip() and part.strip().lower() != "na"
    )


pattern = re.compile(
    r"(?m)^\s*((?:QDi|QDe)\.\d+)\s+Name:\s*(.+)$",
    re.IGNORECASE
)

with pymupdf.open(files[0]) as document:
    entries = []

    for page_number, page in enumerate(document, start=1):
        page_text = page.get_text("text")

        for match in pattern.finditer(page_text):
            identifier = match.group(1).strip()
            raw_name = match.group(2).strip()

            name = clean_numbered_name(raw_name)

            entries.append({
                "identifier": identifier,
                "name": name,
                "original_text": raw_name,
                "page_number": page_number
            })

if not entries:
    raise SystemExit(
        "No standalone regulatory entries were found."
    )

print(f"PDF: {files[0].name}")
print(f"Found {len(entries)} standalone entries:\n")

for entry in entries:
    print(f"Identifier: {entry['identifier']}")
    print(f"Name: {entry['name']}")
    print(f"Page: {entry['page_number']}")
    print(f"Original extracted text: {entry['original_text']}")
    print("-" * 40)
