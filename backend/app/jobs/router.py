"""POST /jobs/refresh            -> poll Greenhouse boards now (admin token required)
GET  /users/{id}/job-matches   -> top ~10 matches for the profile
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.rows import dict_row

from ..admin.dashboard import FAMILY_LABELS
from ..auth.router import require_admin
from ..db import get_conn
from .greenhouse import refresh_jobs
from .matching import MatchProfile, title_family, top_matches

router = APIRouter(tags=["jobs"])


def load_match_profile(user_id: uuid.UUID) -> MatchProfile:
    """Read saved city, salary, work titles, and skills from the shared schema."""
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT a.city, s.salary_min, s.salary_max
            FROM alumni a
            LEFT JOIN LATERAL (
              SELECT salary_min, salary_max FROM salary_records
              WHERE alumni_id = a.id ORDER BY effective_date DESC NULLS LAST, id LIMIT 1
            ) s ON true
            WHERE a.id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        cur.execute(
            """SELECT title FROM work_experience WHERE alumni_id = %s
               AND (start_date IS NULL OR start_date <= CURRENT_DATE)
               ORDER BY CASE WHEN is_current = TRUE AND end_date IS NULL THEN 0 ELSE 1 END,
                        start_date DESC NULLS LAST, id""",
            (user_id,),
        )
        titles = [t["title"] for t in cur.fetchall() if t["title"]]
        cur.execute("SELECT name FROM skills WHERE alumni_id = %s ORDER BY lower(name), id", (user_id,))
        skills = tuple(item["name"] for item in cur.fetchall() if item["name"])
    if not row or not titles:
        raise HTTPException(404, "No profile/title yet. Upload a resume first.")
    # Most recent role we can classify: a "Course Assistant" job on top of software internships
    # should not decide what jobs to show. Falls back to the latest title if none is classifiable.
    latest = next((t for t in titles if title_family(t)), titles[0])
    return MatchProfile(
        latest_title=latest,
        city=row["city"],
        salary_min=int(row["salary_min"]) if row["salary_min"] is not None else None,
        salary_max=int(row["salary_max"]) if row["salary_max"] is not None else None,
        skills=skills,
    )


# Writes/deletes job rows and calls every Greenhouse board, so only the admin may trigger it
@router.post("/jobs/refresh", dependencies=[Depends(require_admin)])
def refresh():
    return refresh_jobs()


@router.get("/users/{user_id}/job-matches")
def job_matches(user_id: uuid.UUID, limit: int = Query(10, ge=1)):
    profile = load_match_profile(user_id)
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM jobs")
        jobs = cur.fetchall()
    synced = [j["last_synced_at"] for j in jobs if j.get("last_synced_at")]
    return {
        "matches": top_matches(profile, jobs, n=min(limit, 20)),
        # real timestamps so the screen can show how fresh this is: when our job list was last refreshed
        "refreshed_at": max(synced) if synced else None,
        # what these matches were personalized from
        "matched_on": {
            "role_title": profile.latest_title,
            "role_type": FAMILY_LABELS[title_family(profile.latest_title) or "other"],
            "city": profile.city,
            "salary_min": profile.salary_min,
            "salary_max": profile.salary_max,
        },
    }
