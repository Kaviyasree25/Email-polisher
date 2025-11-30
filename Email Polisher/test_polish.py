# test_polish.py
import re
from app import simple_polish

tests = [
    "pls send the report asap, thx",
    "hi team,\n\npls send the latest sales report asap. i need the numbers for the meeting tomorrow morning.\n\nthx,\nKaviyasree",
    "Dear Sir/Madam,\n\nI would like to request a copy of the meeting minutes from last Friday’s discussion. Kindly share them at your earliest convenience.\n\nRegards,\nKaviyasree",
    ""
]

for i, t in enumerate(tests, 1):
    out = simple_polish(t)
    print(f"--- Test {i} ---")
    print("Input:")
    print(t)
    print("\nPolished Output:")
    print(out)
    print("\n")
