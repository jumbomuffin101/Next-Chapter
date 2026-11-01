"""GET /admin/outcomes: how alumni are doing N years after graduation, across cohorts (TKH's 3-5 year question).

Only the graduation YEAR is stored, so graduation is taken as July 1 of that year. For each year out (0 = graduation):
- employed: a recorded role covers that date. Alumni with no recorded roles at all are "unknown", not unemployed.
- salary: their latest salary entry in the year up to that date (midpoint of the range); the median across alumni.
Only alumni who have reached that point count (someone who graduated last year has no "year 3").
Everything is self-reported and nothing is estimated here.
"""
from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Optional

from fastapi import APIRouter, Query
from psycopg.rows import dict_row

from ..db import get_conn

router = APIRouter(prefix="/admin", tags=["admin"])
YEARS_OUT = range(0, 7)  # graduation through six years out


def graduation_date(year: int) -> date:
    return date(year, 7, 1)


def years_after(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # Feb 29 in a non-leap year
        return day.replace(year=day.year + years, day=28)


def employed_on(roles: list[dict], day: date) -> bool:
    return any(r["start_date"] and r["start_date"] <= day and (r["is_current"] or r["end_date"] is None or r["end_date"] >= day)
               for r in roles)


def salary_on(salaries: list[dict], day: date) -> Optional[float]:
    """Midpoint of the latest salary entry within the year up to `day`, or None."""
    recent = [s for s in salaries if s["effective_date"] and day - timedelta(days=365) < s["effective_date"] <= day
              and s["salary_min"] is not None and s["salary_max"] is not None]
    if not recent:
        return None
    latest = max(recent, key=lambda s: s["effective_date"])
    return (float(latest["salary_min"]) + float(latest["salary_max"])) / 2


def outcomes_by_year(alumni: list[dict], roles: dict, salaries: dict, today: date) -> list[dict]:
    rows = []
    for years in YEARS_OUT:
        point = {a["id"]: years_after(graduation_date(a["graduation_year"]), years) for a in alumni if a["graduation_year"]}
        reached = [a for a in alumni if a["id"] in point and point[a["id"]] <= today]
        known = [a for a in reached if roles.get(a["id"])]
        employed = sum(employed_on(roles[a["id"]], point[a["id"]]) for a in known)
        pay = [p for a in reached if (p := salary_on(salaries.get(a["id"], []), point[a["id"]])) is not None]
        rows.append({
            "years_out": years, "alumni": len(reached), "with_work_history": len(known),
            "employed_pct": round(100 * employed / len(known)) if known else None,
            "with_salary": len(pay), "median_salary": round(median(pay)) if pay else None,
        })
    return rows


@router.get("/outcomes")
def outcomes(cohort: str = Query("all", max_length=20)):
    """Employment and pay by years since graduation. cohort: 'all' (default) or a graduation year like '2022'."""
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, graduation_year, is_demo FROM alumni WHERE graduation_year IS NOT NULL"
                    + ("" if cohort == "all" else " AND graduation_year::text = %s"), () if cohort == "all" else (cohort,))
        alumni = cur.fetchall()
        cur.execute("SELECT alumni_id, start_date, end_date, is_current FROM work_experience")
        roles = defaultdict(list)
        for r in cur.fetchall():
            roles[r["alumni_id"]].append(r)
        cur.execute("SELECT alumni_id, effective_date, salary_min, salary_max FROM salary_records")
        salaries = defaultdict(list)
        for s in cur.fetchall():
            salaries[s["alumni_id"]].append(s)
    return {
        "cohort": cohort, "graduation_assumed": "July 1 of the graduation year",
        "alumni": len(alumni), "demo": sum(1 for a in alumni if a["is_demo"]),
        "years": outcomes_by_year(alumni, roles, salaries, date.today()),
    }
