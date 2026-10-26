
from difflib import SequenceMatcher

old_text = [
    "The policy repo rate is 5.25%.",
    "The stance remains neutral.",
    "Banks must follow existing guidelines."
]

new_text = [
    "The policy repo rate is 5.50%.",
    "The stance changes to calibrated tightening.",
    "Banks must follow existing guidelines.",
    "The new rules take effect immediately."
]

matcher = SequenceMatcher(
    None, old_text, new_text, autojunk=False
)

print("=== CHANGE DETECTION TEST ===")

for tag, i1, i2, j1, j2 in matcher.get_opcodes():
    if tag == "equal":
        continue

    if tag == "replace":
        print("\nPOTENTIALLY MODIFIED:")
        print("Old:", old_text[i1:i2])
        print("New:", new_text[j1:j2])

    elif tag == "delete":
        print("\nREMOVED:")
        print(old_text[i1:i2])

    elif tag == "insert":
        print("\nADDED:")
        print(new_text[j1:j2])
