"""Greenhouse poller: fetch public boards and upsert into the `jobs` table.

Run on demand (POST /jobs/refresh or `python -m app.jobs.greenhouse`). Not a worker.
"""
import html
import re
import uuid

import httpx

from ..db import get_conn
from .config import BOARD_TOKENS, GREENHOUSE_URL

# Fallback: many postings state pay in the description, e.g. "$120,000 - $150,000".
_PAY_RE = re.compile(r"\$\s?(\d{2,3}(?:,\d{3})+)\s*(?:-|–|to)\s*\$?\s?(\d{2,3}(?:,\d{3})+)")


# Anything outside this is not an annual salary (hourly rates, typos, equity figures)
_MIN_ANNUAL, _MAX_ANNUAL = 15_000, 1_000_000


def _plausible(lo: int, hi: int) -> bool:
    return _MIN_ANNUAL <= lo < hi <= _MAX_ANNUAL


def _extract_salary(job: dict, description: str):
    # `pay_input_ranges` is only returned when the request has pay_transparency=true.
    # Skip hourly entries (cents are per hour, not per year) and min==max placeholders.
    for r in job.get("pay_input_ranges") or []:
        lo, hi = r.get("min_cents"), r.get("max_cents")
        if "hour" in (r.get("title") or "").lower() or not lo or not hi:
            continue
        if _plausible(lo // 100, hi // 100):
            return lo // 100, hi // 100
    m = _PAY_RE.search(description)
    if m:
        lo, hi = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
        if _plausible(lo, hi):
            return lo, hi
    return None, None


def fetch_board(token: str) -> list[dict]:
    """Raises on network errors / non-200 so callers can report the failure."""
    r = httpx.get(GREENHOUSE_URL.format(token=token), timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    rows = []
    for j in r.json().get("jobs", []):
        desc = html.unescape(j.get("content") or "")
        lo, hi = _extract_salary(j, desc)
        rows.append(
            {
                "board_token": token,
                "id": uuid.uuid4(),
                "greenhouse_job_id": str(j["id"]),
                # shared-schema VARCHAR(255): cut rather than fail the whole refresh
                "title": (j.get("title") or "")[:255],
                "company": (j.get("company_name") or token.title())[:255],
                "location": ((j.get("location") or {}).get("name") or "")[:255],
                "is_remote": "remote" in ((j.get("location") or {}).get("name") or "").lower(),
                "absolute_url": j.get("absolute_url", ""),
                "description": desc[:5000],
                "salary_min": lo,
                "salary_max": hi,
                "updated_at": j.get("updated_at"),
            }
        )
    return rows


UPSERT = """
INSERT INTO jobs (id, board_token, greenhouse_job_id, title, company, location, is_remote,
                  absolute_url, description, salary_min, salary_max, updated_at, last_synced_at)
VALUES (%(id)s, %(board_token)s, %(greenhouse_job_id)s, %(title)s, %(company)s, %(location)s, %(is_remote)s,
        %(absolute_url)s, %(description)s, %(salary_min)s, %(salary_max)s, %(updated_at)s, now())
ON CONFLICT (board_token, greenhouse_job_id) DO UPDATE SET
  title = EXCLUDED.title, company = EXCLUDED.company, location = EXCLUDED.location,
  is_remote = EXCLUDED.is_remote, absolute_url = EXCLUDED.absolute_url,
  description = EXCLUDED.description, salary_min = EXCLUDED.salary_min,
  salary_max = EXCLUDED.salary_max, updated_at = EXCLUDED.updated_at, last_synced_at = now()
"""


def refresh_jobs() -> dict:
    total, per_board, failed = 0, {}, {}
    with get_conn() as conn, conn.cursor() as cur:
        for token in BOARD_TOKENS:
            try:
                rows = fetch_board(token)
            except Exception as e:  # one bad/slow board must not break the whole refresh
                failed[token] = str(e) or type(e).__name__
                continue
            per_board[token] = len(rows)
            for row in rows:
                cur.execute(UPSERT, row)
            # A successful empty board means all its old postings disappeared.
            # Failed boards skip this block and retain their previous listings.
            cur.execute(
                "DELETE FROM jobs WHERE board_token = %s AND greenhouse_job_id <> ALL(%s)",
                (token, [r["greenhouse_job_id"] for r in rows]),
            )
            total += len(rows)
        conn.commit()
    return {"boards": len(BOARD_TOKENS), "jobs_upserted": total, "per_board": per_board, "failed": failed}


if __name__ == "__main__":
    print(refresh_jobs())
