
from pathlib import Path
from metadata_db import register_document

pdf_path = Path(
    "data/raw/NT29576C2A2CDED3247308333EE2DE9383863.pdf"
).resolve()

register_document(
    source_url="https://rbi.org.in/scripts/NotificationUser.aspx?Mode=0&Id=13741",
    title="Reserve Bank of India (Small Finance Banks - Miscellaneous) Amendment Directions, 2026",
    regulator="RBI",
    file_path=str(pdf_path),
    publication_date="2026-10-19",
    effective_date="2026-10-19"
)
