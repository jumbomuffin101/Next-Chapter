"""Personal invite links.

    GET /profiles/{id}/invite  -> {"code": "...", "joined": 2}   the alumnus's own code (made on first request) and who joined through it
    GET /invites/{code}        -> {"inviter_first_name": "...", "cohort": "2026"}   what the sign-up page shows; 404 if unknown

The link itself is built by the frontend as <app url>/?invite=<code>, like the other dashboard links.
"""
import secrets
import uuid

from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row

from ..db import get_conn

router = APIRouter(tags=["invites"])


def new_code() -> str:
    return secrets.token_urlsafe(6)  # 8 URL-safe characters


def find_invite(cur, code: str):
    """The inviter behind a code (id, first name, cohort), or None."""
    cur.execute(
        """SELECT a.id, a.first_name, nullif(trim(a.cohort), '') AS cohort
           FROM invite_codes c JOIN alumni a ON a.id = c.alumni_id WHERE c.code = %s""",
        (code.strip(),),
    )
    return cur.fetchone()


@router.get("/profiles/{profile_id}/invite")
def my_invite(profile_id: uuid.UUID):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT 1 FROM alumni WHERE id = %s", (profile_id,))
        if cur.fetchone() is None:
            raise HTTPException(404, "Profile not found")
        cur.execute("INSERT INTO invite_codes (code, alumni_id) VALUES (%s, %s) ON CONFLICT (alumni_id) DO NOTHING",
                    (new_code(), profile_id))
        cur.execute("SELECT code FROM invite_codes WHERE alumni_id = %s", (profile_id,))
        code = cur.fetchone()["code"]
        cur.execute("SELECT count(*) AS n FROM signup_sources WHERE inviter_id = %s", (profile_id,))
        joined = cur.fetchone()["n"]
        conn.commit()
    return {"code": code, "joined": joined}


@router.get("/invites/{code}")
def invite_details(code: str):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        inviter = find_invite(cur, code)
    if inviter is None:
        raise HTTPException(404, "This invite link isn't valid. You can still create a profile.")
    return {"inviter_first_name": inviter["first_name"], "cohort": inviter["cohort"]}
