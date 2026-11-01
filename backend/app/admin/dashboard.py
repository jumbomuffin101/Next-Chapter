"""Admin dashboard data, filtered by cohort, and the 'Needs action' list with follow-up tracking.

    GET  /admin/dashboard?cohort=current|next|all|<year>   KPI tiles, cohort list, roles, locations, salary charts
    GET  /admin/actions?cohort=&flag=&status=&city=&q=     alumni who need attention, with the reason
    POST /admin/actions/{alumni_id}                        record a follow-up: open | contacted | resolved (+ note)

Everything is computed from recorded data. Nothing is estimated: no salary data means null / an empty chart.
All routes are mounted behind the admin token in main.py.

Definitions (keep in sync with the dashboard wording):
- employed:      a work_experience row with is_current = true, no end date, and a start date that is not in the future
- salary:        midpoint of a salary_records range; growth = first vs latest record, only for alumni with 2+ records
- participation: confirmed a resume within the last 180 days
- current cohort: the latest cohort year up to this year; next = current + 1
- role type:     title family of the alumnus's current (else newest) role, via the job matcher's keyword families
"""
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

import psycopg.errors
from fastapi import APIRouter, HTTPException, Query
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from ..db import get_conn
from ..jobs.matching import title_family
from .geo import CITY_COORDS

router = APIRouter(prefix="/admin", tags=["admin"])

STALE_DAYS = 180
GAP_DAYS = 90
FAMILY_LABELS = {
    "software": "Software & engineering", "data": "Data & analytics", "product": "Product & program",
    "design": "Design & UX", "support": "IT & customer support", "ops": "Operations & admin",
    "sales": "Sales & business", "other": "Other",
}
SALARY_BINS = [(0, 40_000, "Under $40k"), (40_000, 60_000, "$40–60k"), (60_000, 80_000, "$60–80k"),
               (80_000, 100_000, "$80–100k"), (100_000, 120_000, "$100–120k"), (120_000, None, "$120k+")]
PRIORITY_RANK = {"high": 3, "medium": 2, "low": 1}
FLAG_TYPES = ("career_gap", "missing_info", "stale", "support")

ROWS_SQL = """
SELECT a.id, a.first_name, a.last_name, a.email, a.city, a.cohort, a.graduation_year, a.is_demo, a.updated_at,
  EXISTS (SELECT 1 FROM work_experience w WHERE w.alumni_id = a.id AND w.is_current AND w.end_date IS NULL
          AND (w.start_date IS NULL OR w.start_date <= CURRENT_DATE)) AS employed,
  (SELECT count(*) FROM work_experience w WHERE w.alumni_id = a.id) AS roles,
  (SELECT max(w.end_date) FROM work_experience w WHERE w.alumni_id = a.id AND w.end_date IS NOT NULL) AS last_end,
  (SELECT w.title FROM work_experience w WHERE w.alumni_id = a.id
     ORDER BY (w.is_current AND w.end_date IS NULL) DESC, w.start_date DESC NULLS LAST LIMIT 1) AS role_title,
  (SELECT count(*) FROM education e WHERE e.alumni_id = a.id) AS schools,
  (SELECT count(*) FROM skills s WHERE s.alumni_id = a.id) AS skills,
  (SELECT count(*) FROM salary_records r WHERE r.alumni_id = a.id) AS salary_records,
  (SELECT max(u.uploaded_at) FROM resume_uploads u WHERE u.alumni_id = a.id AND u.confirmed) AS last_confirmed,
  (SELECT q.created_at FROM support_requests q WHERE q.alumni_id = a.id ORDER BY q.created_at DESC LIMIT 1) AS support_at,
  (SELECT q.message FROM support_requests q WHERE q.alumni_id = a.id ORDER BY q.created_at DESC LIMIT 1) AS support_message,
  (SELECT l.status FROM action_log l WHERE l.alumni_id = a.id ORDER BY l.created_at DESC LIMIT 1) AS action_status,
  (SELECT l.note FROM action_log l WHERE l.alumni_id = a.id ORDER BY l.created_at DESC LIMIT 1) AS action_note,
  (SELECT l.created_at FROM action_log l WHERE l.alumni_id = a.id ORDER BY l.created_at DESC LIMIT 1) AS action_at
FROM alumni a
"""
SALARY_SQL = """
SELECT alumni_id, effective_date, (salary_min + salary_max) / 2 AS mid FROM salary_records
WHERE salary_min IS NOT NULL AND salary_max IS NOT NULL AND effective_date IS NOT NULL
ORDER BY effective_date ASC
"""


# ---------------------------------------------------------------- small helpers
def cohort_of(row: dict) -> Optional[str]:
    return (row["cohort"] or "").strip() or None


def _year(cohort: Optional[str]) -> Optional[int]:
    return int(cohort) if cohort and cohort.isdigit() and len(cohort) == 4 else None


def city_of(row: dict) -> Optional[str]:
    name = (row["city"] or "").split(",")[0].strip()
    return name.title() if name else None


def full_name(row: dict) -> str:
    return f"{row['first_name']} {row['last_name']}".strip() or row["email"]


def _pct(part: int, whole: int) -> Optional[int]:
    return round(100 * part / whole) if whole else None


def _mean(values) -> Optional[int]:
    nums = [float(v) for v in values if v is not None]
    return round(sum(nums) / len(nums)) if nums else None


def salary_index(salary_rows: list[dict]) -> dict:
    """alumni_id -> chronological list of (date, midpoint)."""
    index: dict = defaultdict(list)
    for r in salary_rows:
        index[r["alumni_id"]].append((r["effective_date"], float(r["mid"])))
    return index


def group_stats(members: list[dict], sal: dict) -> dict:
    growth = [(history[-1][1] / history[0][1] - 1) * 100
              for r in members if len(history := sal.get(r["id"], [])) >= 2 and history[0][1]]
    latest = [sal[r["id"]][-1][1] for r in members if sal.get(r["id"])]
    employed = sum(1 for r in members if r["employed"])
    return {"size": len(members), "employed": employed, "employment_rate": _pct(employed, len(members)),
            "avg_salary": _mean(latest), "salary_growth_pct": round(sum(growth) / len(growth), 1) if growth else None,
            "salary_growth_n": len(growth)}


# ---------------------------------------------------------------- cohorts
def cohort_choices(rows: list[dict], sal: dict, today: date) -> dict:
    members: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if (name := cohort_of(r)):
            members[name].append(r)
    years = [y for y in map(_year, members) if y is not None]
    current_year = max([y for y in years if y <= today.year], default=today.year)
    current, nxt = str(current_year), str(current_year + 1)
    names = set(members) | {current, nxt}
    listing = sorted(names, key=lambda n: (_year(n) or 0, n), reverse=True)
    return {
        "current": current, "next": nxt,
        "list": [{"name": n, "year": _year(n), **group_stats(members.get(n, []), sal)} for n in listing],
    }


def resolve_cohort(requested: str, choices: dict) -> str:
    if requested == "current":
        return choices["current"]
    if requested == "next":
        return choices["next"]
    return requested  # 'all' or a specific cohort name


def select_members(rows: list[dict], cohort: str) -> list[dict]:
    return rows if cohort == "all" else [r for r in rows if cohort_of(r) == cohort]


# ---------------------------------------------------------------- charts
def role_breakdown(members: list[dict]) -> list[dict]:
    counts = Counter((title_family(r["role_title"]) or "other") for r in members if r["role_title"])
    return [{"family": fam, "label": FAMILY_LABELS[fam], "count": n} for fam, n in counts.most_common()]


def location_breakdown(members: list[dict]) -> list[dict]:
    counts = Counter(c for r in members if (c := city_of(r)))
    out = []
    for city, n in counts.most_common():
        coords = CITY_COORDS.get(city.lower())
        out.append({"city": city, "alumni": n, "lat": coords[0] if coords else None, "lng": coords[1] if coords else None})
    return out


def salary_charts(members: list[dict], sal: dict) -> dict:
    ids = {r["id"] for r in members}
    by_quarter: dict[str, list[tuple]] = defaultdict(list)
    for alumni_id in ids:
        for when, mid in sal.get(alumni_id, []):
            by_quarter[f"{when.year}-Q{(when.month - 1) // 3 + 1}"].append((alumni_id, mid))
    series = [{"period": q, "avg": round(sum(m for _, m in pts) / len(pts)), "n": len({a for a, _ in pts})}
              for q, pts in sorted(by_quarter.items())]
    latest = [sal[i][-1][1] for i in ids if sal.get(i)]
    distribution = [{"label": label, "count": sum(1 for v in latest if v >= lo and (hi is None or v < hi))}
                    for lo, hi, label in SALARY_BINS]
    return {"series": series, "distribution": distribution, "n_with_salary": len(latest)}


# ---------------------------------------------------------------- needs action
def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def action_status(row: dict) -> str:
    status = row["action_status"] or "open"
    support_at, action_at = _aware(row["support_at"]), _aware(row["action_at"])
    if support_at and (action_at is None or support_at > action_at):
        return "open"  # a newer request for help reopens it
    return status


def flags_for(row: dict, now: datetime) -> list[dict]:
    today = now.date()
    flags = []
    if row["support_at"]:
        message = (row["support_message"] or "").strip()
        flags.append({"type": "support", "label": "Asked for help", "priority": "high",
                      "detail": f"Requested support {_aware(row['support_at']):%b %d}" + (f': "{message[:140]}"' if message else "")})
    if not row["employed"] and row["last_end"] and (today - row["last_end"]).days > GAP_DAYS:
        months = (today - row["last_end"]).days // 30
        flags.append({"type": "career_gap", "label": "Career gap", "priority": "high",
                      "detail": f"No current job since {row['last_end']:%b %Y} ({months} months)"})
    missing = [label for label, present in [
        ("work experience", row["roles"]), ("city", row["city"] and row["city"].strip()), ("education", row["schools"]),
        ("skills", row["skills"]), ("salary", row["salary_records"]), ("cohort", cohort_of(row))] if not present]
    if missing:
        flags.append({"type": "missing_info", "label": "Missing profile info",
                      "priority": "medium" if "work experience" in missing or len(missing) >= 3 else "low",
                      "detail": "Missing: " + ", ".join(missing)})
    confirmed = _aware(row["last_confirmed"])
    if confirmed is None:
        flags.append({"type": "stale", "label": "No confirmed resume", "priority": "medium", "detail": "Has never confirmed a resume"})
    elif now - confirmed > timedelta(days=STALE_DAYS):
        flags.append({"type": "stale", "label": "Resume out of date", "priority": "low",
                      "detail": f"Last confirmed {confirmed:%b %d, %Y}"})
    return flags


def build_actions(rows: list[dict], now: datetime) -> list[dict]:
    items = []
    for r in rows:
        flags = flags_for(r, now)
        if not flags:
            continue
        action_at = _aware(r["action_at"])
        items.append({
            "id": str(r["id"]), "name": full_name(r), "email": r["email"], "city": r["city"], "cohort": cohort_of(r),
            "is_demo": r["is_demo"], "flags": flags, "status": action_status(r), "note": r["action_note"],
            "last_action_at": action_at.isoformat() if action_at else None,
            "last_confirmed": _aware(r["last_confirmed"]).isoformat() if r["last_confirmed"] else None,
            "priority": max((f["priority"] for f in flags), key=PRIORITY_RANK.get),
        })
    items.sort(key=lambda i: (-PRIORITY_RANK[i["priority"]], i["name"].lower()))
    return items


# ---------------------------------------------------------------- queries
def _load(cur):
    try:
        cur.execute(ROWS_SQL)
        rows = cur.fetchall()
        cur.execute(SALARY_SQL)
        return rows, salary_index(cur.fetchall())
    except psycopg.errors.UndefinedTable:
        raise HTTPException(503, "Admin tables are missing. Run: python -m backend.app.init_db") from None


def _cohort_filter(items: list[dict], rows: list[dict], cohort: str) -> list[dict]:
    if cohort == "all":
        return items
    allowed = {str(r["id"]) for r in select_members(rows, cohort)}
    return [i for i in items if i["id"] in allowed]


@router.get("/dashboard")
def dashboard(cohort: str = Query("current", max_length=20)):
    now = datetime.now(timezone.utc)
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        rows, sal = _load(cur)
    choices = cohort_choices(rows, sal, now.date())
    selected = resolve_cohort(cohort, choices)
    members = select_members(rows, selected)
    stats = group_stats(members, sal)
    confirmed_recent = sum(1 for r in members if r["last_confirmed"] and now - _aware(r["last_confirmed"]) <= timedelta(days=STALE_DAYS))
    open_actions = [i for i in _cohort_filter(build_actions(rows, now), rows, selected) if i["status"] == "open"]
    return {
        "cohorts": choices, "selected": selected,
        "kpis": {
            "alumni": stats["size"], "demo": sum(1 for r in members if r["is_demo"]), "real": sum(1 for r in members if not r["is_demo"]),
            "employed": stats["employed"], "employment_rate": stats["employment_rate"],
            "salary_growth_pct": stats["salary_growth_pct"], "salary_growth_n": stats["salary_growth_n"], "avg_salary": stats["avg_salary"],
            "participation_n": confirmed_recent, "participation_pct": _pct(confirmed_recent, stats["size"]),
            "needs_action": len(open_actions),
        },
        "roles": role_breakdown(members),
        "locations": location_breakdown(members),
        "salary": salary_charts(members, sal),
        "actions_preview": open_actions[:5],
    }


@router.get("/actions")
def actions(
    cohort: str = Query("all", max_length=20),
    flag: Optional[Literal["career_gap", "missing_info", "stale", "support"]] = None,
    status: Literal["open", "contacted", "resolved", "all"] = "open",
    city: Optional[str] = Query(None, max_length=100),
    q: Optional[str] = Query(None, max_length=100),
):
    now = datetime.now(timezone.utc)
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        rows, sal = _load(cur)
    selected = resolve_cohort(cohort, cohort_choices(rows, sal, now.date()))
    items = _cohort_filter(build_actions(rows, now), rows, selected)
    cities = sorted({c.title() for i in items if (c := (i["city"] or "").split(",")[0].strip())})
    if status != "all":
        items = [i for i in items if i["status"] == status]
    if city:
        items = [i for i in items if (i["city"] or "").split(",")[0].strip().lower() == city.strip().lower()]
    if q and q.strip():
        needle = q.strip().lower()
        items = [i for i in items if needle in i["name"].lower() or needle in i["email"].lower()]
    counts = {t: sum(1 for i in items if any(f["type"] == t for f in i["flags"])) for t in FLAG_TYPES}
    counts["total"] = len(items)
    if flag:
        items = [i for i in items if any(f["type"] == flag for f in i["flags"])]
    return {"items": items, "counts": counts, "cities": cities, "selected": selected}


class ActionIn(BaseModel):
    status: Literal["open", "contacted", "resolved"]
    note: Optional[str] = Field(None, max_length=1000)


@router.post("/actions/{alumni_id}")
def record_action(alumni_id: uuid.UUID, body: ActionIn):
    note = (body.note or "").strip() or None
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT 1 FROM alumni WHERE id = %s", (alumni_id,))
        if cur.fetchone() is None:
            raise HTTPException(404, "Alumni not found")
        try:
            cur.execute("INSERT INTO action_log (id, alumni_id, status, note) VALUES (%s, %s, %s, %s) RETURNING created_at",
                        (uuid.uuid4(), alumni_id, body.status, note))
        except psycopg.errors.UndefinedTable:
            raise HTTPException(503, "Admin tables are missing. Run: python -m backend.app.init_db") from None
        created = cur.fetchone()["created_at"]
        conn.commit()
    return {"status": body.status, "note": note, "last_action_at": created.isoformat()}
