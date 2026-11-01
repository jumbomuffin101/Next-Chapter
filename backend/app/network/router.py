"""Alumni network: peers in your field, sample events, and certification suggestions.

Every alumnus with a profile is in the network automatically (there is no opt-in). What other alumni can see: name, current role,
company, city, cohort, email, and a LinkedIn link only if it was on their resume. Email drafts open in the user's own mail app;
nothing is sent from here. Alumni login is still a stub, so treat this as demo-grade access control.
"""
import re
import uuid
from datetime import date
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from psycopg.rows import dict_row

from ..admin.dashboard import FAMILY_LABELS, city_of
from ..db import get_conn
from ..growth.certs import recommend
from ..jobs.matching import title_family
from .events import events_for, metro_key

router = APIRouter(prefix="/profiles", tags=["network"])

PEERS_SQL = """
SELECT a.id, a.first_name, a.last_name, a.email, a.city, a.cohort, a.is_demo, r.title AS role_title, r.employer,
  (SELECT u.parsed_data->>'linkedin_url' FROM resume_uploads u
   WHERE u.alumni_id = a.id AND u.confirmed AND COALESCE(u.parsed_data->>'linkedin_url', '') <> ''
   ORDER BY u.uploaded_at DESC LIMIT 1) AS linkedin_url,
  -- "Just joined": signed up through an invite link or event QR in the last 7 days, or any real (non-demo) sign-up in that window
  (EXISTS (SELECT 1 FROM signup_sources s WHERE s.alumni_id = a.id AND s.created_at > now() - interval '7 days')
   OR (NOT a.is_demo AND a.created_at > now() - interval '7 days')) AS just_joined
FROM alumni a
LEFT JOIN LATERAL (
  SELECT w.title, w.employer FROM work_experience w WHERE w.alumni_id = a.id
  ORDER BY (w.is_current AND w.end_date IS NULL) DESC, w.start_date DESC NULLS LAST LIMIT 1
) r ON TRUE
"""
SCOPES = ("all", "company", "city", "role")


# ---------------------------------------------------------------- pure logic (unit-tested)
def family_of(title: Optional[str]) -> str:
    return (title_family(title) if title else None) or "other"


def rank_peers(me: dict, others: list[dict]) -> list[dict]:
    """Peers in your field, best first: same company, then same metro + same role type, then same role elsewhere."""
    my_family = family_of(me["role_title"])
    my_employer = (me["employer"] or "").strip().lower()
    my_metro = metro_key(me["city"])
    out = []
    for o in others:
        fam = family_of(o["role_title"])
        same_family = my_family != "other" and fam == my_family
        same_company = bool(my_employer) and (o["employer"] or "").strip().lower() == my_employer
        same_metro = my_metro is not None and metro_key(o["city"]) == my_metro
        if not (same_family or same_company):
            continue
        reasons = ([] if not same_company else ["Same company"]) + (
            [] if not same_metro else (["Same city"] if city_of(o) == city_of(me) else ["Same metro area"])) + (
            [] if not same_family else ["Same role type"])
        linkedin_url, linkedin_kind = linkedin_for(o)
        out.append({
            "id": str(o["id"]), "name": f"{o['first_name']} {o['last_name']}".strip(), "title": o["role_title"], "employer": o["employer"],
            "city": o["city"], "cohort": (o["cohort"] or "").strip() or None, "email": o["email"],
            "linkedin_url": linkedin_url, "linkedin_kind": linkedin_kind, "just_joined": bool(o.get("just_joined")),
            "role_type": FAMILY_LABELS[fam], "reasons": reasons, "_flags": (same_company, same_metro and same_family, same_family),
            "_score": 3 * same_company + 2 * same_family + 2 * same_metro,
        })
    # people who just joined come first, then the usual best-match order
    out.sort(key=lambda p: (not p["just_joined"], -p["_score"], p["name"].lower()))
    return out


def filter_scope(peers: list[dict], scope: str) -> list[dict]:
    index = {"company": 0, "city": 1, "role": 2}
    return peers if scope == "all" else [p for p in peers if p["_flags"][index[scope]]]


LINKEDIN_PROFILE = re.compile(r"https://([a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9%_\-]{3,100}/?", re.I)


def linkedin_for(person: dict) -> tuple[Optional[str], Optional[str]]:
    """(url, kind). 'profile' = a real link from the person's own resume. 'search' = a LinkedIn people-search link, used only for
    SYNTHETIC demo people who have no real profile. Anything that is not a linkedin.com profile link (for example the old
    example.com placeholders) is ignored. Real people without a LinkedIn link on their resume get no button."""
    url = (person.get("linkedin_url") or "").strip()
    if LINKEDIN_PROFILE.fullmatch(url):
        return url, "profile"
    if person.get("is_demo"):
        keywords = f"{person['first_name']} {person['last_name']} {person['employer'] or ''}".strip()
        return f"https://www.linkedin.com/search/results/people/?keywords={quote(keywords)}", "search"
    return None, None


def _require(cur, profile_id):
    cur.execute("SELECT 1 FROM alumni WHERE id = %s", (profile_id,))
    if cur.fetchone() is None:
        raise HTTPException(404, "Profile not found")


def _load_me_and_peers(profile_id):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        _require(cur, profile_id)
        cur.execute(PEERS_SQL)  # everyone is in the network; ranking happens in rank_peers
        rows = cur.fetchall()
    me = next((r for r in rows if r["id"] == profile_id), None)
    return me, [r for r in rows if r["id"] != profile_id]


@router.get("/{profile_id}/network/peers")
def peers(profile_id: uuid.UUID, scope: str = Query("all"), limit: int = Query(24, ge=1, le=60)):
    if scope not in SCOPES:
        raise HTTPException(422, f"scope must be one of: {', '.join(SCOPES)}")
    me, others = _load_me_and_peers(profile_id)
    if me is None:
        raise HTTPException(404, "Profile not found")
    ranked = rank_peers(me, others)
    counts = {s: len(filter_scope(ranked, s)) for s in SCOPES}
    items = [{k: v for k, v in p.items() if not k.startswith("_")} for p in filter_scope(ranked, scope)[:limit]]
    return {"items": items, "counts": counts, "my_role_type": FAMILY_LABELS[family_of(me["role_title"])],
            "has_role": bool(me["role_title"]), "me": {"city": me["city"], "employer": me["employer"], "title": me["role_title"]}}


@router.get("/{profile_id}/events")
def events(profile_id: uuid.UUID):
    me, _ = _load_me_and_peers(profile_id)
    return events_for(me["city"] if me else None, family_of(me["role_title"] if me else None), date.today())


@router.get("/{profile_id}/recommendations")
def recommendations(profile_id: uuid.UUID):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        _require(cur, profile_id)
        cur.execute("SELECT name FROM skills WHERE alumni_id = %s ORDER BY name", (profile_id,))
        skills = [r["name"] for r in cur.fetchall()]
        cur.execute("SELECT name FROM certifications WHERE alumni_id = %s ORDER BY name", (profile_id,))
        held = [r["name"] for r in cur.fetchall()]
        cur.execute("""SELECT title FROM work_experience WHERE alumni_id = %s
                       ORDER BY (is_current AND end_date IS NULL) DESC, start_date DESC NULLS LAST LIMIT 1""", (profile_id,))
        row = cur.fetchone()
    return recommend(skills, held, row["title"] if row else None)
