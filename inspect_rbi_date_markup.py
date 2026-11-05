
import requests
from bs4 import BeautifulSoup

URL = (
    "https://www.rbi.org.in/scripts/"
    "BS_ViewMasDirections.aspx?id=13138"
)

response = requests.get(
    URL,
    headers={"User-Agent": "RegulatoryResearchProject/1.0"},
    timeout=30,
)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

for keyword in (
    "Climate Finance",
    "October 01, 2026",
    "dated",
    "Date of Issue",
    "Updated as on",
    "Website last updated date",
):
    print("\n" + "=" * 65)
    print("SEARCH:", keyword)

    matches = soup.find_all(
        string=lambda value: value and keyword.lower() in value.lower()
    )

    if not matches:
        print("No exact text match.")
        continue

    for match in matches[:5]:
        element = match.parent
        print("TEXT:", " ".join(match.strip().split())[:300])
        print("HTML:", str(element)[:1200])

        parent = element.parent
        if parent:
            print("PARENT HTML:", str(parent)[:1800])

print("\nInspection complete. No files or database records modified.")
