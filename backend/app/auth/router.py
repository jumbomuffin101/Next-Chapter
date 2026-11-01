"""Stub authentication for the hackathon demo. This is NOT production security.

- Admin: one demo account (ADMIN_EMAIL / ADMIN_PASSWORD, defaults below). A successful login returns a
  signed, expiring token; the admin endpoints (/admin/*, /analytics/*) require it as `Authorization: Bearer`.
- Alumni: email-only sign in / sign up (no password). It only looks a profile up or creates one.
Replace both with real authentication before any real use.
"""
import base64
import hashlib
import hmac
import os
import time
import uuid

from fastapi import APIRouter, Header, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel

from ..db import get_conn
from ..invites.router import find_invite
from ..onboarding.router import check_cohort

router = APIRouter(prefix="/auth", tags=["auth"])

TOKEN_TTL_SECONDS = 8 * 3600


def _admin_email() -> str:
    return os.getenv("ADMIN_EMAIL", "admin@tkh.org").strip().lower()


def _admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "tkh-demo-2026")


def _secret() -> bytes:
    return os.getenv("ADMIN_TOKEN_SECRET", "tkh-demo-secret-change-me").encode()


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def make_admin_token(now: float | None = None) -> str:
    payload = f"admin.{int((now or time.time()) + TOKEN_TTL_SECONDS)}"
    return base64.urlsafe_b64encode(f"{payload}.{_sign(payload)}".encode()).decode()


def verify_admin_token(token: str, now: float | None = None) -> bool:
    try:
        role, expires, signature = base64.urlsafe_b64decode(token.encode()).decode().split(".")
        return (role == "admin" and hmac.compare_digest(signature, _sign(f"{role}.{expires}"))
                and int(expires) > (now or time.time()))
    except (ValueError, UnicodeError):
        return False


def require_admin(authorization: str | None = Header(None)) -> None:
    """FastAPI dependency: 401 unless the request carries a valid admin token."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not verify_admin_token(token.strip()):
        raise HTTPException(401, "Admin sign-in required.")


class AdminLogin(BaseModel):
    email: str
    password: str


@router.post("/admin/login")
def admin_login(body: AdminLogin):
    ok_email = hmac.compare_digest(body.email.strip().lower().encode(), _admin_email().encode())
    ok_password = hmac.compare_digest(body.password.encode(), _admin_password().encode())
    if not (ok_email and ok_password):
        raise HTTPException(401, "Wrong email or password.")
    return {"token": make_admin_token(), "expires_in": TOKEN_TTL_SECONDS}


class AlumniLogin(BaseModel):
    email: str


class AlumniSignup(BaseModel):
    email: str
    full_name: str
    invite: str | None = None  # code from an alumnus's invite link: joins the inviter's cohort
    cohort: str | None = None  # from the in-room QR code for a cohort


def _clean_email(raw: str) -> str:
    email = raw.strip().lower()
    if len(email) > 255 or "@" not in email or " " in email:
        raise HTTPException(422, "Enter a valid email address.")
    return email


def _onboarded_row(cur, email: str):
    """The profile row plus whether onboarding is done (a name and at least one saved role)."""
    cur.execute(
        """SELECT a.id, a.email, a.is_demo, trim(a.first_name || ' ' || a.last_name) AS full_name,
                  (trim(a.first_name) <> '' AND EXISTS (SELECT 1 FROM work_experience w WHERE w.alumni_id = a.id)) AS onboarded
           FROM alumni a WHERE lower(a.email) = %s""",
        (email,),
    )
    return cur.fetchone()


@router.post("/alumni/login")
def alumni_login(body: AlumniLogin):
    email = _clean_email(body.email)
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        row = _onboarded_row(cur, email)
    if row is None:
        raise HTTPException(404, "We couldn't find a profile for that email. Create one instead.")
    # A purpose-bound demo session cannot authorize preferences for real alumni.
    from ..newsletter.security import demo_session
    row["newsletter_token"] = demo_session(row["id"]) if row.get("is_demo") else None
    return row


@router.post("/alumni/signup")
def alumni_signup(body: AlumniSignup):
    email = _clean_email(body.email)
    parts = body.full_name.strip().split(maxsplit=1)
    if not parts:
        raise HTTPException(422, "Enter your full name.")
    first, last = parts[0][:100], (parts[1][:100] if len(parts) > 1 else "")
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        if _onboarded_row(cur, email) is not None:
            raise HTTPException(409, "A profile with this email already exists. Sign in instead.")
        source, inviter, cohort = None, None, None
        if body.invite and body.invite.strip():
            inviter = find_invite(cur, body.invite)
            if inviter is None:
                raise HTTPException(422, "This invite link isn't valid. You can still create a profile without it.")
            source, cohort = "invite", inviter["cohort"]
        elif body.cohort and body.cohort.strip():
            source, cohort = "room", check_cohort(body.cohort)
        alumni_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO alumni (id, first_name, last_name, email, cohort, graduation_year, is_demo) VALUES (%s,%s,%s,%s,%s,%s,FALSE)",
            (alumni_id, first, last, email, cohort, int(cohort) if cohort and cohort.isdigit() else None),
        )
        if source:
            cur.execute("INSERT INTO signup_sources (alumni_id, source, inviter_id, cohort) VALUES (%s,%s,%s,%s)",
                        (alumni_id, source, inviter["id"] if inviter else None, cohort))
        row = _onboarded_row(cur, email)
        conn.commit()
    return row
