"""Admin Automation page: peer invite emails, the personalized monthly newsletter, and the data behind the event QR codes.

    GET  /admin/automation                       peer-email switch + log, sign-ups via invite/QR, newsletter status
    POST /admin/automation/emails                {"enabled": true|false}   peer invite emails on/off
    POST /admin/automation/newsletter            {"enabled": true|false}   scheduled monthly newsletter on/off (on by default)
    POST /admin/automation/newsletter/send       {"email": "..."}   send this month's newsletter to one alum now

Mounted behind the admin token in main.py. Peer emails are logged only (see app/automation/emails.py). The newsletter
follows Aryan's rules (app/newsletter): demo accounts only, the alum must have opted in, and nothing is emailed while
NEWSLETTER_DRY_RUN is on (the default).
"""
import os
from datetime import datetime, timezone

import psycopg.errors
from fastapi import APIRouter, HTTPException, Query
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from ..automation.emails import SETTING, emails_enabled
from ..db import get_conn
from ..newsletter import delivery
from ..newsletter.calendar import current_month, month_start, scheduled_at
from ..newsletter.router import call
from ..newsletter.switch import monthly_enabled, set_monthly_enabled

router = APIRouter(prefix="/admin", tags=["admin"])
KINDS = ("just_joined", "invite_worked", "cohort_invite")


def _next_send_at(now: datetime) -> datetime:
    """The monthly send goes out on the 1st at 9:00 AM America/New_York: this month's if still ahead, else next month's."""
    month = current_month(now)
    this = scheduled_at(month)
    if now < this:
        return this
    year, mon = map(int, month.split("-"))
    return scheduled_at(f"{year + (mon == 12)}-{mon % 12 + 1:02d}")


def _newsletter_status(conn, cur) -> dict:
    month = current_month()
    base = {"monthly_enabled": monthly_enabled(cur), "month": month,
            # same rule as newsletter.provider.Settings: only the exact value "false" turns real sending on
            "mode": "dry_run" if os.getenv("NEWSLETTER_DRY_RUN", "true").lower() != "false" else "live",
            "next_send_at": _next_send_at(datetime.now(timezone.utc))}
    try:
        with conn.transaction():  # a savepoint: a missing table must not poison the rest of the request
            cur.execute("SELECT count(*) AS n FROM newsletter_subscriptions WHERE subscribed")
            subscribers = cur.fetchone()["n"]
            cur.execute("SELECT status, count(*) AS n FROM newsletter_deliveries WHERE month = %s GROUP BY status",
                        (month_start(month),))
            deliveries = {row["status"]: row["n"] for row in cur.fetchall()}
    except psycopg.errors.UndefinedTable:
        return {**base, "available": False, "subscribers": 0, "deliveries": {},
                "reason": "The newsletter tables are not installed yet. Apply backend/sql/newsletter.sql first."}
    return {**base, "available": True, "subscribers": subscribers, "deliveries": deliveries}


@router.get("/automation")
def automation(limit: int = Query(30, ge=1, le=200)):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        enabled = emails_enabled(cur)
        cur.execute("SELECT kind, count(*) AS n FROM email_outbox GROUP BY kind")
        counts = {row["kind"]: row["n"] for row in cur.fetchall()}
        cur.execute("""SELECT o.kind, o.to_email, o.to_name, o.subject, o.body, o.created_at, o.sent_at,
                              trim(a.first_name || ' ' || a.last_name) AS about
                       FROM email_outbox o JOIN alumni a ON a.id = o.about_id
                       ORDER BY o.created_at DESC, o.kind, o.to_email LIMIT %s""", (limit,))
        recent = cur.fetchall()
        cur.execute("SELECT source, count(*) AS n FROM signup_sources GROUP BY source")
        signups = {row["source"]: row["n"] for row in cur.fetchall()}
        newsletter = _newsletter_status(conn, cur)
    return {
        "emails": {"enabled": enabled, "sending": False, "counts": {k: counts.get(k, 0) for k in KINDS},
                   "total": sum(counts.values()), "recent": recent},
        "signups": {"invite": signups.get("invite", 0), "room": signups.get("room", 0)},
        "newsletter": newsletter,
    }


class EmailSwitch(BaseModel):
    enabled: bool


@router.post("/automation/emails")
def switch_emails(body: EmailSwitch):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO app_settings (key, value) VALUES (%s, %s)
                       ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()""", (SETTING, Jsonb(body.enabled)))
        conn.commit()
    return {"enabled": body.enabled}


@router.post("/automation/newsletter")
def switch_newsletter(body: EmailSwitch):
    with get_conn() as conn, conn.cursor() as cur:
        set_monthly_enabled(cur, body.enabled)
        conn.commit()
    return {"enabled": body.enabled}


class NewsletterSend(BaseModel):
    email: str


def _demo_alum(email: str) -> dict:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, trim(first_name || ' ' || last_name) AS name, is_demo FROM alumni WHERE lower(email) = %s",
                    (email.strip().lower(),))
        alum = cur.fetchone()
    if alum is None:
        raise HTTPException(404, "No alum has that email.")
    if not alum["is_demo"]:
        raise HTTPException(403, "Newsletter sends are limited to synthetic demo accounts until verified alumni authentication is available.")
    return alum


@router.post("/automation/newsletter/send")
def send_newsletter(body: NewsletterSend):
    alum = _demo_alum(body.email)
    month = current_month()
    result = call(delivery.deliver, alum["id"], month)
    return {"name": alum["name"], "month": month,
            "mode": "dry_run" if os.getenv("NEWSLETTER_DRY_RUN", "true").lower() != "false" else "live", **result}
