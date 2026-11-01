"""Small endpoints the onboarding wizard and the alumni dashboard need, kept apart from the shared
resume/profile routes: set the TKH cohort year, and read or record salary / role history for the growth section."""
import re
import uuid
from datetime import date

from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel

MAX_SALARY = 9_999_999_999  # NUMERIC(12, 2) in salary_records

from ..db import get_conn

router = APIRouter(prefix="/profiles", tags=["onboarding"])

FIRST_COHORT_YEAR = 2015  # The Knowledge House began in 2015


class CohortIn(BaseModel):
    cohort: str


def check_cohort(cohort: str) -> str:
    """The cohort year as text, or 422. Also used by sign-up through an in-room QR code."""
    year_text = cohort.strip()
    if not re.fullmatch(r"\d{4}", year_text) or not FIRST_COHORT_YEAR <= int(year_text) <= date.today().year + 1:
        raise HTTPException(422, f"Cohort must be a year between {FIRST_COHORT_YEAR} and {date.today().year + 1}.")
    return year_text


@router.post("/{profile_id}/cohort")
def set_cohort(profile_id: uuid.UUID, body: CohortIn):
    year_text = check_cohort(body.cohort)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE alumni SET cohort = %s, graduation_year = %s WHERE id = %s",
                    (year_text, int(year_text), profile_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Profile not found")
        conn.commit()
    return {"cohort": year_text}


class SalaryIn(BaseModel):
    salary_min: int
    salary_max: int
    month: str  # "YYYY-MM": when the person earned this, so past salaries can be recorded too


def month_start(month: str, today: date | None = None) -> date:
    """First day of a "YYYY-MM" month that isn't in the future, or 422."""
    text = month.strip()
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", text):
        raise HTTPException(422, "Pick the month and year you earned this.")
    when = date(int(text[:4]), int(text[5:]), 1)
    if when > (today or date.today()) or when.year < 1970:
        raise HTTPException(422, "Pick a month between 1970 and now.")
    return when


def check_salary(body: SalaryIn, today: date | None = None) -> date:
    """The entry's month, or 422 when the range can't be right."""
    if not 0 < body.salary_min <= body.salary_max <= MAX_SALARY:
        raise HTTPException(422, "Enter a minimum and a maximum yearly salary, with the minimum no higher than the maximum.")
    return month_start(body.month, today)


def job_label(title: str | None, employer: str | None) -> str:
    """'Software Engineer at Demo Cloud', or whichever part is known."""
    return " at ".join(part for part in (title, employer) if part) or "Untitled role"


class SalaryJobIn(BaseModel):
    work_experience_id: uuid.UUID | None = None  # None clears the job


def _require_profile(cur, profile_id):
    cur.execute("SELECT 1 FROM alumni WHERE id = %s", (profile_id,))
    if cur.fetchone() is None:
        raise HTTPException(404, "Profile not found")


@router.get("/{profile_id}/growth")
def growth(profile_id: uuid.UUID):
    """Salary history (oldest first, self-reported/estimated as stored) and career span. No estimates are made here."""
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        _require_profile(cur, profile_id)
        cur.execute(
            """SELECT effective_date, salary_min, salary_max, source, work_experience_id FROM salary_records
               WHERE alumni_id = %s ORDER BY effective_date ASC NULLS FIRST""",
            (profile_id,),
        )
        history = [{"date": r["effective_date"], "salary_min": int(r["salary_min"]) if r["salary_min"] is not None else None,
                    "salary_max": int(r["salary_max"]) if r["salary_max"] is not None else None, "source": r["source"],
                    "work_experience_id": str(r["work_experience_id"]) if r["work_experience_id"] else None}
                   for r in cur.fetchall()]
        # the person's jobs, for the job dropdown on each salary history row
        cur.execute("""SELECT id, title, employer, start_date, end_date, is_current FROM work_experience
                       WHERE alumni_id = %s ORDER BY start_date DESC NULLS LAST""", (profile_id,))
        jobs = [{"id": str(r["id"]), "label": job_label(r["title"], r["employer"]), "start_date": r["start_date"],
                 "end_date": r["end_date"], "is_current": r["is_current"]} for r in cur.fetchall()]
        cur.execute("SELECT count(*) AS roles, min(start_date) AS first_start FROM work_experience WHERE alumni_id = %s",
                    (profile_id,))
        career = cur.fetchone()
    return {"salary_history": history, "jobs": jobs, "roles": career["roles"], "first_role_start": career["first_start"]}


# One self-reported entry per month: saving a month again replaces it (a range saved "today" counts as this month).
_SAME_MONTH = """alumni_id = %s AND source = 'self_reported'
                 AND effective_date >= %s AND effective_date < (%s::date + INTERVAL '1 month')"""
# The role covering a month; with overlapping roles, the one started most recently
_HELD_THAT_MONTH = """alumni_id = %s AND start_date < (%s::date + INTERVAL '1 month') AND (end_date IS NULL OR end_date >= %s)
                      ORDER BY start_date DESC LIMIT 1"""


@router.post("/{profile_id}/salary")
def add_salary(profile_id: uuid.UUID, body: SalaryIn):
    """Record what the person earned in a given month (past or current). Returns the updated growth data."""
    when = check_salary(body)
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        _require_profile(cur, profile_id)
        cur.execute(f"SELECT id FROM salary_records WHERE {_SAME_MONTH} ORDER BY effective_date LIMIT 1", (profile_id, when, when))
        row = cur.fetchone()
        # Link it to the job held that month, so the role's salary in the profile fills in too (a chosen job is kept)
        cur.execute(f"SELECT id FROM work_experience WHERE {_HELD_THAT_MONTH}", (profile_id, when, when))
        held = cur.fetchone()
        job = held["id"] if held else None
        if row:
            cur.execute("""UPDATE salary_records SET salary_min = %s, salary_max = %s,
                           work_experience_id = COALESCE(work_experience_id, %s) WHERE id = %s""",
                        (body.salary_min, body.salary_max, job, row["id"]))
        else:
            cur.execute("""INSERT INTO salary_records (id, alumni_id, salary_min, salary_max, source, effective_date, work_experience_id)
                           VALUES (%s, %s, %s, %s, 'self_reported', %s, %s)""",
                        (uuid.uuid4(), profile_id, body.salary_min, body.salary_max, when, job))
        conn.commit()
    return growth(profile_id)


@router.delete("/{profile_id}/salary/{month}")
def remove_salary(profile_id: uuid.UUID, month: str):
    """Remove the person's own entry for a month (estimated entries are left alone). Returns the updated growth data."""
    when = month_start(month)
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        _require_profile(cur, profile_id)
        cur.execute(f"DELETE FROM salary_records WHERE {_SAME_MONTH}", (profile_id, when, when))
        if cur.rowcount == 0:
            raise HTTPException(404, "No salary recorded for that month.")
        conn.commit()
    return growth(profile_id)


class SupportIn(BaseModel):
    message: str | None = None


@router.post("/{profile_id}/support")
def request_support(profile_id: uuid.UUID, body: SupportIn):
    """An alumnus asks the career team for help. It shows up on the admin 'Needs action' page."""
    message = (body.message or "").strip() or None
    if message and len(message) > 1000:
        raise HTTPException(422, "Please keep your message under 1000 characters.")
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT 1 FROM alumni WHERE id = %s", (profile_id,))
        if cur.fetchone() is None:
            raise HTTPException(404, "Profile not found")
        cur.execute("INSERT INTO support_requests (id, alumni_id, message) VALUES (%s, %s, %s) RETURNING created_at",
                    (uuid.uuid4(), profile_id, message))
        created = cur.fetchone()["created_at"]
        conn.commit()
    return {"requested_at": created}


@router.get("/{profile_id}/support")
def latest_support_request(profile_id: uuid.UUID):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT created_at, message FROM support_requests WHERE alumni_id = %s ORDER BY created_at DESC LIMIT 1",
                    (profile_id,))
        row = cur.fetchone()
    return {"requested_at": row["created_at"] if row else None, "message": row["message"] if row else None}


@router.put("/{profile_id}/salary/{month}/job")
def set_salary_job(profile_id: uuid.UUID, month: str, body: SalaryJobIn):
    """Say which of your jobs a month's salary was for (or clear it). Returns the updated growth data."""
    when = month_start(month)
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        _require_profile(cur, profile_id)
        if body.work_experience_id:  # only one of this person's own jobs
            cur.execute("SELECT 1 FROM work_experience WHERE id = %s AND alumni_id = %s", (body.work_experience_id, profile_id))
            if cur.fetchone() is None:
                raise HTTPException(422, "That job isn't in your work history.")
        cur.execute(f"UPDATE salary_records SET work_experience_id = %s WHERE {_SAME_MONTH}",
                    (body.work_experience_id, profile_id, when, when))
        if cur.rowcount == 0:
            raise HTTPException(404, "No salary recorded for that month.")
        conn.commit()
    return growth(profile_id)
