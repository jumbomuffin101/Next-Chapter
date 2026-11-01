"""Live Greenhouse check: python scripts/check_boards.py [token ...]   (defaults to config list)

For each board token: does it respond, how many jobs, how many expose a salary range, and a
sample of locations. Use it to pick tokens that actually have jobs in TKH's cities or remote.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.jobs.config import BOARD_TOKENS  # noqa: E402
from app.jobs.greenhouse import fetch_board  # noqa: E402

for token in sys.argv[1:] or BOARD_TOKENS:
    try:
        rows = fetch_board(token)
    except Exception as e:
        print(f"{token:18} FAILED: {e}")
        continue
    with_pay = sum(1 for r in rows if r["salary_min"])
    locs = Counter(r["location"] for r in rows).most_common(4)
    print(f"{token:18} jobs={len(rows):4}  with_salary={with_pay:3}  top_locations={locs}")
