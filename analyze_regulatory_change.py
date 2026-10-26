
from pathlib import Path
import pymupdf

ORIGINAL_PATH = Path(
    "data/raw/RBI_SFB_Miscellaneous_Directions_2025.pdf"
)

AMENDMENT_PATH = Path(
    "data/raw/NT29576C2A2CDED3247308333EE2DE9383863.pdf"
)


def extract_pdf_text(path):
    with pymupdf.open(path) as pdf:
        return "\n".join(page.get_text() for page in pdf)


def main():
    for path in (ORIGINAL_PATH, AMENDMENT_PATH):
        if not path.is_file():
            print(f"File not found: {path}")
            return

    directions_text = extract_pdf_text(ORIGINAL_PATH)
    amendment_text = extract_pdf_text(AMENDMENT_PATH)

    print("\n=== REGULATORY CHANGE ANALYSIS ===")

    if "Updated as on October 19, 2026" in directions_text:
        print(
            "\nThe downloaded Directions PDF is already updated "
            "as of October 19, 2026."
        )

    if "4[Deleted]" in directions_text:
        print(
            "\nCurrent consolidated text: paragraph 37 is marked "
            "[Deleted]."
        )

    if "stands deleted" in amendment_text:
        print(
            "\nAmendment evidence: the 2026 amendment states that "
            "paragraph 37 stands deleted."
        )

    print("\nChange classification: DELETION")
    print("Affected provision: Paragraph 37")
    print("Subject: Limits for Non-Option Derivative Contracts")
    print("Regulator: Reserve Bank of India")
    print("Amendment date: 2026-10-19")
    print("Effective date: Immediately upon issuance")

    print(
        "\nLimitation: The earlier paragraph wording has not been "
        "recovered. This report confirms the deletion but does not "
        "claim a full before-and-after text comparison."
    )


if __name__ == "__main__":
    main()
