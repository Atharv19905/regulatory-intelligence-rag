
import re
import requests
from bs4 import BeautifulSoup

URLS = {
    "Payments Banks Internal Ombudsman": (
        "https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=13273"
    ),
    "Responsible Business Conduct Directions": (
        "https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=13140"
    ),
    "Insurance Directions (date conflict)": (
        "https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=10738"
    ),
}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; RegulatoryResearch/1.0)"
})

for label, url in URLS.items():
    print("\n" + "=" * 80)
    print(label)
    print("URL:", url)

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        heading = soup.find(
            "p",
            class_="head",
            string=re.compile(r"Directions|Direction", re.I),
        )

        if not heading:
            print("Expected heading not found.")
            for p in soup.find_all("p")[:15]:
                text = p.get_text(" ", strip=True)
                if text:
                    print("P:", text[:250])
            continue

        print("\nHEADING:")
        print(heading.get_text(" ", strip=True))

        content_cell = heading.find_parent("td")
        if not content_cell:
            print("Heading's parent table cell not found.")
            continue

        print("\nDIRECT PARAGRAPHS:")
        paragraphs = content_cell.find_all("p", recursive=False)

        for i, p in enumerate(paragraphs):
            text = p.get_text(" ", strip=True)
            if text:
                print(f"[{i}] {text[:350]}")

        print("\nREFERENCE/DATE-LIKE LINES:")
        for p in content_cell.find_all("p"):
            text = p.get_text(" ", strip=True)
            if re.search(
                r"RBI/|20\d{2}|January|February|March|April|May|June|"
                r"July|August|September|October|November|December",
                text,
                re.I,
            ):
                print("-", text[:300])

    except requests.RequestException as exc:
        print("FETCH ERROR:", exc)

print("\nInspection complete. No files modified.")
