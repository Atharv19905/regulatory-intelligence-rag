
from pathlib import Path
from metadata_db import register_document

pdf_path = Path("data/raw/RBI_second_circular.pdf").resolve()

register_document(
    source_url="https://rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63839",
    title="Minutes of the Monetary Policy Committee Meeting, October 5 to 7, 2026",
    regulator="RBI",
    file_path=str(pdf_path),
    publication_date="2026-10-21"
)
