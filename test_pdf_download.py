
import requests

url = (
    "https://rbidocs.rbi.org.in/rdocs/Notification/PDFs/"
    "NOTI2964177D6F8B5FA4B0A917BA90749E2394E.PDF"
)

response = requests.get(url, timeout=30)

print("Status:", response.status_code)
print("Content-Type:", response.headers.get("Content-Type"))
print("Final URL:", response.url)
print("First 20 bytes:", repr(response.content[:20]))

if response.content.startswith(b"%PDF-"):
    print("SUCCESS: Valid PDF received.")
else:
    print("Not a PDF. Do not save it as a regulatory document.")
