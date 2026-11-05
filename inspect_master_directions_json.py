
import json
from pathlib import Path

path = Path("data/versions/rbi_master_directions_discovered.json")

data = json.loads(path.read_text(encoding="utf-8"))

print("Top-level type:", type(data).__name__)

if isinstance(data, dict):
    print("Top-level keys:", list(data.keys())[:20])

    for key, value in data.items():
        print(f"\nKey: {key!r}")
        print("Value type:", type(value).__name__)

        if isinstance(value, list):
            print("List length:", len(value))
            if value:
                print("First item type:", type(value[0]).__name__)
                print("First item:", repr(value[0])[:1000])
            break

        if isinstance(value, dict):
            print("First keys:", list(value.keys())[:15])
            print("Sample:", repr(value)[:1000])
            break

elif isinstance(data, list):
    print("List length:", len(data))
    if data:
        print("First item type:", type(data[0]).__name__)
        print("First item:", repr(data[0])[:1000])

print("\nInspection only; no files modified.")
