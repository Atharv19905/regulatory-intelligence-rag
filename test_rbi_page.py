
import requests
from bs4 import BeautifulSoup

url = (
    "https://www.rbi.org.in/scripts/"
    "bs_circularindexdisplay.aspx/Scripts/"
    "BS_CircularIndexDisplay.aspx?Id=13742"
)

response = requests.get(url, timeout=30)

print("Status:", response.status_code)
print("Content type:", response.headers.get("Content-Type"))

soup = BeautifulSoup(response.text, "html.parser")

print("\nPage title:")
print(soup.title.get_text(strip=True) if soup.title else "No title")

print("\nLinks containing PDF:")
for link in soup.find_all("a", href=True):
    href = link["href"]

    if ".pdf" in href.lower():
        print(link.get_text(" ", strip=True))
        print("URL:", href)
        print()
