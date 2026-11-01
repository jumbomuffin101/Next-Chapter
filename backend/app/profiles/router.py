"""Minimal profile endpoints so my slice can run on its own, on the shared `alumni` table.

Auth is stubbed: POST /profiles with an email creates the alumni row or returns the existing one,
which doubles as "login". Replace/merge with the team's version if one exists.
"""
import uuid

from fastapi import APIRouter, HTTPException, Query
from psycopg import IsolationLevel
from psycopg.rows import dict_row
from pydantic import BaseModel

from ..db import get_conn
from .schema import CurrentRole, ProfileList, ProfileSummary
from .outreach import router as outreach_router

router = APIRouter(prefix="/profiles", tags=["profiles"])
# Register the static outreach path before /{profile_id}.
router.include_router(outreach_router)


class ProfileIn(BaseModel):
    email: str
    full_name: str | None = None
    city: str | None = None


@router.get("", response_model=ProfileList)
def list_profiles(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    cohort: str | None = Query(None, min_length=1, max_length=100),
    city: str | None = Query(None, min_length=1, max_length=100),
):
    """List alumni ordered by case-insensitive surname, first name, then UUID.

    Filters are case-insensitive exact matches with surrounding input whitespace
    removed. A current role must be explicitly marked current, have no end date,
    and have no future start date. Latest known start wins; UUID breaks ties.
    """
    conditions, params = [], []
    for column, value in (("cohort", cohort), ("city", city)):
        if value is not None:
            conditions.append(f"lower(a.{column}) = lower(%s)")
            params.append(value.strip())
    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    with get_conn() as conn:
        # Count and page share a consistent snapshot, including when the offset
        # is past the last result. These settings affect this connection only.
        conn.isolation_level = IsolationLevel.REPEATABLE_READ
        conn.read_only = True
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT count(*) AS total FROM alumni a" + where, params)
            total = cur.fetchone()["total"]
            cur.execute(
                """WITH current_roles AS (
                     SELECT id, alumni_id, title, employer, start_date,
                            row_number() OVER (
                              PARTITION BY alumni_id
                              ORDER BY start_date DESC NULLS LAST, id ASC
                            ) AS role_rank
                     FROM work_experience
                     WHERE is_current = TRUE AND end_date IS NULL
                       AND (start_date IS NULL OR start_date <= CURRENT_DATE)
                   )
                   SELECT a.id, trim(a.first_name || ' ' || a.last_name) AS full_name,
                          a.email, a.city, a.cohort, a.graduation_year, a.is_demo,
                          a.updated_at AS last_updated_at,
                          r.id AS role_id, r.title AS role_title,
                          r.employer AS role_employer, r.start_date AS role_start_date
                   FROM alumni a
                   LEFT JOIN current_roles r ON r.alumni_id = a.id AND r.role_rank = 1"""
                + where
                + " ORDER BY lower(a.last_name), lower(a.first_name), a.id LIMIT %s OFFSET %s",
                [*params, limit, offset],
            )
            rows = cur.fetchall()

    items = []
    for row in rows:
        current_role = None
        if row["role_id"] is not None:
            current_role = CurrentRole(
                title=row["role_title"], employer=row["role_employer"],
                start_date=row["role_start_date"],
            )
        items.append(ProfileSummary(**row, current_role=current_role))
    return ProfileList(items=items, total=total, limit=limit, offset=offset)


@router.post("")
def create_or_get_profile(body: ProfileIn):
    email = body.email.strip().lower()
    if "@" not in email or len(email) > 255:
        raise HTTPException(422, "Invalid email")
    parts = (body.full_name or "").strip().split(maxsplit=1)
    first, last = (parts[0][:100] if parts else ""), (parts[1][:100] if len(parts) > 1 else "")
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        # first/last name are NOT NULL in the shared schema; "" until the first resume confirm fills them
        cur.execute(
            """INSERT INTO alumni (id, first_name, last_name, email, city, is_demo)
               VALUES (%s,%s,%s,%s,%s,FALSE)
               ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
               RETURNING id, email, trim(first_name || ' ' || last_name) AS full_name, city""",
            (uuid.uuid4(), first, last, email, (body.city or None) and body.city[:100]),
        )
        row = cur.fetchone()
        conn.commit()
    return row


def _num(v):
    return int(v) if v is not None else None


@router.get("/{profile_id}")
def get_profile(profile_id: uuid.UUID):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM alumni WHERE id = %s", (profile_id,))
        a = cur.fetchone()
        if not a:
            raise HTTPException(404, "Profile not found")
        profile = {
            "id": a["id"], "email": a["email"], "full_name": f"{a['first_name']} {a['last_name']}".strip(),
            "phone": a["phone"], "city": a["city"], "cohort": a["cohort"],
            "graduation_year": a["graduation_year"], "is_demo": a["is_demo"],
            "created_at": a["created_at"], "last_updated_at": a["updated_at"],  # drives the outreach flag
        }
        cur.execute(
            """SELECT salary_min, salary_max, source FROM salary_records WHERE alumni_id = %s
               ORDER BY effective_date DESC NULLS LAST LIMIT 1""",
            (profile_id,),
        )
        sal = cur.fetchone()
        profile["salary_min"] = _num(sal["salary_min"]) if sal else None
        profile["salary_max"] = _num(sal["salary_max"]) if sal else None
        profile["salary_source"] = sal["source"] if sal else None
        cur.execute(
            "SELECT * FROM work_experience WHERE alumni_id=%s ORDER BY start_date DESC NULLS LAST", (profile_id,)
        )
        profile["work_experiences"] = cur.fetchall()
        # each role's own salary: its earliest linked self-reported entry
        cur.execute(
            """SELECT DISTINCT ON (work_experience_id) work_experience_id, salary_min, salary_max FROM salary_records
               WHERE alumni_id = %s AND source = 'self_reported' AND work_experience_id IS NOT NULL
               ORDER BY work_experience_id, effective_date""", (profile_id,))
        role_pay = {r["work_experience_id"]: r for r in cur.fetchall()}
        for role in profile["work_experiences"]:
            pay = role_pay.get(role["id"])
            role["salary_min"] = _num(pay["salary_min"]) if pay else None
            role["salary_max"] = _num(pay["salary_max"]) if pay else None
        cur.execute(
            "SELECT * FROM education WHERE alumni_id=%s ORDER BY graduation_year DESC NULLS LAST", (profile_id,)
        )
        profile["education"] = cur.fetchall()
        cur.execute("SELECT name FROM skills WHERE alumni_id=%s ORDER BY name", (profile_id,))
        profile["skills"] = [r["name"] for r in cur.fetchall()]
        cur.execute("SELECT name FROM certifications WHERE alumni_id=%s ORDER BY name", (profile_id,))
        profile["certifications"] = [r["name"] for r in cur.fetchall()]
    return profile
