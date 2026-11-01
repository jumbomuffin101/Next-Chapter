"""Admin dashboard data: GET /admin/overview.

Everything is computed from the shared tables (alumni, work_experience, salary_records, education,
skills). Nothing is estimated: when there is no salary data the value is null, not a guess.
No admin authentication exists yet, so this endpoint is open like the rest of the API.

Definitions (keep in sync with the dashboard wording):
- employed:        the alumni has a work_experience row with is_current = true
- salary:          midpoint of the alumni's NEWEST salary_records range
- salary growth:   newest vs oldest salary record, only for alumni with 2+ records
- current cohort:  the cohort with the latest graduation_year; the rest are past cohorts
- city:            the part of alumni.city before the comma
- needs outreach:  no update in 6+ months, no current job, missing salary, or incomplete profile
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter
from psycopg.rows import dict_row

from ..db import get_conn

router = APIRouter(prefix="/admin", tags=["admin"])

STALE_AFTER = timedelta(days=183)

SQL = """
SELECT a.id, a.first_name, a.last_name, a.email, a.city, a.cohort, a.graduation_year, a.updated_at,
  (SELECT max(u.uploaded_at) FROM resume_uploads u WHERE u.alumni_id = a.id AND u.confirmed) AS last_confirmed,
  EXISTS (SELECT 1 FROM work_experience w WHERE w.alumni_id = a.id AND w.is_current) AS employed,
  (SELECT count(*) FROM work_experience w WHERE w.alumni_id = a.id) AS roles,
  (SELECT count(*) FROM education e WHERE e.alumni_id = a.id) AS schools,
  (SELECT count(*) FROM skills s WHERE s.alumni_id = a.id) AS skills,
  (SELECT count(*) FROM salary_records r WHERE r.alumni_id = a.id) AS salary_records,
  (SELECT (r.salary_min + r.salary_max) / 2 FROM salary_records r WHERE r.alumni_id = a.id
     ORDER BY r.effective_date DESC NULLS LAST LIMIT 1) AS salary_now,
  (SELECT (r.salary_min + r.salary_max) / 2 FROM salary_records r WHERE r.alumni_id = a.id
     ORDER BY r.effective_date ASC NULLS LAST LIMIT 1) AS salary_first
FROM alumni a
"""


def _pct(part: int, whole: int) -> Optional[int]:
    return round(100 * part / whole) if whole else None


def _mean(values) -> Optional[int]:
    nums = [float(v) for v in values if v is not None]
    return round(sum(nums) / len(nums)) if nums else None


def _city(raw: Optional[str]) -> Optional[str]:
    name = (raw or "").split(",")[0].strip()
    return name.title() if name else None


def _cohort_name(r: dict) -> Optional[str]:
    return r["cohort"] or (str(r["graduation_year"]) if r["graduation_year"] else None)


def outreach_reasons(r: dict, now: datetime) -> list[str]:
    reasons = []
    if r["updated_at"] is None or now - r["updated_at"] > STALE_AFTER:
        reasons.append("No update in 6+ months")
    if r.get("last_confirmed") is None:
        reasons.append("No confirmed resume yet")
    if not r["employed"]:
        reasons.append("No current job")
    if not r["salary_records"]:
        reasons.append("Missing salary")
    missing = [label for label, present in
               [("city", r["city"]), ("work experience", r["roles"]), ("education", r["schools"]), ("skills", r["skills"])]
               if not present]
    if missing:
        reasons.append("Incomplete profile: no " + ", ".join(missing))
    return reasons


def _group_stats(rows: list[dict]) -> dict:
    growth = [(float(r["salary_now"]) / float(r["salary_first"]) - 1) * 100
              for r in rows
              if r["salary_records"] >= 2 and r["salary_now"] is not None and r["salary_first"]]
    return {
        "size": len(rows),
        "employment_rate": _pct(sum(1 for r in rows if r["employed"]), len(rows)),
        "avg_salary": _mean(r["salary_now"] for r in rows),
        "salary_growth_pct": round(sum(growth) / len(growth), 1) if growth else None,
    }


def build_overview(rows: list[dict], now: datetime) -> dict:
    cohorts: dict[str, list[dict]] = {}
    cities: dict[str, list[dict]] = {}
    for r in rows:
        if (name := _cohort_name(r)):
            cohorts.setdefault(name, []).append(r)
        if (city := _city(r["city"])):
            cities.setdefault(city, []).append(r)

    cohort_list = [
        {"name": name, "graduation_year": max((m["graduation_year"] or 0) for m in members) or None,
         **_group_stats(members)}
        for name, members in cohorts.items()
    ]
    cohort_list.sort(key=lambda c: (c["graduation_year"] or 0, c["name"]), reverse=True)

    locations = [
        {"city": city, "alumni": len(members), **{k: v for k, v in _group_stats(members).items()
                                                  if k in ("employment_rate", "avg_salary")}}
        for city, members in cities.items()
    ]
    locations.sort(key=lambda c: (-c["alumni"], c["city"]))

    outreach = []
    for r in rows:
        reasons = outreach_reasons(r, now)
        if reasons:
            outreach.append({
                "id": str(r["id"]), "name": f"{r['first_name']} {r['last_name']}".strip() or r["email"],
                "email": r["email"], "city": r["city"], "cohort": _cohort_name(r), "reasons": reasons,
                "last_updated": r["updated_at"].isoformat() if r["updated_at"] else None,
                "last_confirmed": r["last_confirmed"].isoformat() if r.get("last_confirmed") else None,
            })
    outreach.sort(key=lambda o: (-len(o["reasons"]), o["name"]))

    return {
        "totals": {k: v for k, v in _group_stats(rows).items() if k != "salary_growth_pct"},
        "current_cohort": cohort_list[0] if cohort_list else None,
        "past_cohorts": cohort_list[1:],
        "locations": locations,
        "outreach": outreach,
    }


@router.get("/overview")
def overview():
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(SQL)
        rows = cur.fetchall()
    return build_overview(rows, datetime.now(timezone.utc))
