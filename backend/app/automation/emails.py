"""Automated emails, written to the email_outbox table. Nothing is sent: no mail provider is connected yet.

When an alumnus finishes onboarding (their FIRST confirmed resume), and the career team has not switched automated
emails off on the admin Automation page:
- just_joined:   everyone else in their cohort hears "<name> just joined"
- invite_worked: whoever invited them hears that their invite worked
- cohort_invite: roster people in their cohort who have no profile yet get an invite with this alumnus's link
                 (each roster person is invited once, by the first cohort-mate who joins)
Links point at APP_URL (the dashboard's address, default http://localhost:5173).
"""
import os
import uuid

from psycopg.rows import dict_row

from ..db import get_conn
from ..invites.router import new_code

SETTING = "auto_emails_enabled"


def app_url() -> str:
    return os.getenv("APP_URL", "http://localhost:5173").rstrip("/")


def emails_enabled(cur) -> bool:
    cur.execute("SELECT value FROM app_settings WHERE key = %s", (SETTING,))
    row = cur.fetchone()
    return True if row is None else bool(row["value"])  # on unless the career team turned it off


def _who(me: dict) -> str:
    role = f", {me['title']}" + (f" at {me['employer']}" if me["employer"] else "") if me["title"] else ""
    return f"{me['first_name']} {me['last_name']}".strip() + role


def _invite_code(cur, alumni_id) -> str:
    cur.execute("INSERT INTO invite_codes (code, alumni_id) VALUES (%s, %s) ON CONFLICT (alumni_id) DO NOTHING", (new_code(), alumni_id))
    cur.execute("SELECT code FROM invite_codes WHERE alumni_id = %s", (alumni_id,))
    return cur.fetchone()["code"]


def build_emails(cur, alumni_id) -> list[dict]:
    cur.execute(
        """SELECT a.id, a.first_name, a.last_name, a.email, nullif(trim(a.cohort), '') AS cohort, r.title, r.employer
           FROM alumni a LEFT JOIN LATERAL (
             SELECT w.title, w.employer FROM work_experience w WHERE w.alumni_id = a.id
             ORDER BY (w.is_current AND w.end_date IS NULL) DESC, w.start_date DESC NULLS LAST LIMIT 1) r ON TRUE
           WHERE a.id = %s""",
        (alumni_id,),
    )
    me = cur.fetchone()
    if me is None:
        raise LookupError("Alumni profile not found")
    emails = []
    sign_off = f"\n\nStay connected through TKH: {app_url()}\n- The TKH career team"

    cur.execute("""SELECT a.first_name, a.last_name, a.email FROM signup_sources s JOIN alumni a ON a.id = s.inviter_id
                   WHERE s.alumni_id = %s AND s.source = 'invite'""", (alumni_id,))
    inviter = cur.fetchone()
    if inviter:
        emails.append({"kind": "invite_worked", "to_email": inviter["email"], "to_name": f"{inviter['first_name']} {inviter['last_name']}".strip(),
                       "subject": f"{me['first_name']} joined TKH next chapter through your invite",
                       "body": f"Hi {inviter['first_name']},\n\n{_who(me)} just joined TKH next chapter using your invite link. Thank you for growing the network!{sign_off}"})

    if me["cohort"]:
        cur.execute("""SELECT first_name, last_name, email FROM alumni
                       WHERE trim(cohort) = %s AND id <> %s AND email IS NOT NULL ORDER BY email""", (me["cohort"], alumni_id))
        for mate in cur.fetchall():
            emails.append({"kind": "just_joined", "to_email": mate["email"], "to_name": f"{mate['first_name']} {mate['last_name']}".strip(),
                           "subject": f"{me['first_name']} from your TKH {me['cohort']} cohort just joined",
                           "body": f"Hi {mate['first_name']},\n\n{_who(me)} from your {me['cohort']} cohort just joined TKH next chapter. "
                                   f"Say hi from the People tab.{sign_off}"})
        cur.execute("""SELECT r.first_name, r.last_name, r.email FROM alumni_roster r
                       WHERE trim(r.cohort) = %s
                         AND NOT EXISTS (SELECT 1 FROM alumni a WHERE lower(a.email) = lower(r.email))
                         AND NOT EXISTS (SELECT 1 FROM email_outbox o WHERE o.kind = 'cohort_invite' AND lower(o.to_email) = lower(r.email))
                       ORDER BY r.email""", (me["cohort"],))
        not_joined = cur.fetchall()
        if not_joined:
            link = f"{app_url()}/?invite={_invite_code(cur, alumni_id)}"
            for person in not_joined:
                emails.append({"kind": "cohort_invite", "to_email": person["email"], "to_name": f"{person['first_name']} {person['last_name']}".strip(),
                               "subject": f"{me['first_name']} invited you to TKH next chapter",
                               "body": f"Hi {person['first_name']},\n\n{_who(me)} from your TKH {me['cohort']} cohort invited you to TKH next chapter: "
                                       f"job matches picked for you, skills to learn next, and your cohort in one place. "
                                       f"It takes two minutes with your resume.\n\nJoin here: {link}\n- The TKH career team"})
    return emails


def on_resume_confirmed(alumni_id) -> int:
    """Log the onboarding emails after an alumnus's first confirmed resume. Returns how many were logged (0 when switched off)."""
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) AS n FROM resume_uploads WHERE alumni_id = %s AND confirmed", (alumni_id,))
        if cur.fetchone()["n"] != 1 or not emails_enabled(cur):
            return 0
        logged = 0
        for email in build_emails(cur, alumni_id):
            cur.execute(
                """INSERT INTO email_outbox (id, kind, to_email, to_name, subject, body, about_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                (uuid.uuid4(), email["kind"], email["to_email"], email["to_name"], email["subject"], email["body"], alumni_id),
            )
            logged += cur.rowcount
        conn.commit()
    return logged
