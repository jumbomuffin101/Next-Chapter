"""Read-only outreach indicators; never sends messages."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from work.database.database import readonly_session
from work.database.models import Alumni, ResumeUpload

router = APIRouter(tags=["outreach"])


class OutreachItem(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    city: str | None
    cohort: str | None
    is_demo: bool
    last_confirmed_at: datetime | None
    needs_outreach: bool
    outreach_reason: str | None


class OutreachPage(BaseModel):
    items: list[OutreachItem]
    total: int
    limit: int
    offset: int
    stale_days: int
    as_of: datetime


@router.get("/outreach", response_model=OutreachPage)
def outreach(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    stale_days: int = Query(180, ge=1, le=3650),
    only_needs_outreach: bool = True,
    include_demo: bool = True,
):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=stale_days)
    latest = select(
        ResumeUpload.alumni_id,
        func.max(ResumeUpload.uploaded_at).label("last_confirmed_at"),
    ).where(ResumeUpload.confirmed.is_(True)).group_by(ResumeUpload.alumni_id).subquery()
    query = select(
        Alumni.id, Alumni.first_name, Alumni.last_name, Alumni.email,
        Alumni.city, Alumni.cohort, Alumni.is_demo, latest.c.last_confirmed_at,
    ).outerjoin(latest, latest.c.alumni_id == Alumni.id)
    if only_needs_outreach:
        query = query.where(or_(latest.c.last_confirmed_at.is_(None), latest.c.last_confirmed_at < cutoff))
    if not include_demo:
        query = query.where(Alumni.is_demo.is_(False))
    with readonly_session() as session:
        total = session.scalar(select(func.count()).select_from(query.subquery()))
        rows = session.execute(query.order_by(
            func.lower(Alumni.last_name), func.lower(Alumni.first_name), Alumni.id,
        ).limit(limit).offset(offset)).mappings().all()
    items = []
    for row in rows:
        confirmed = row["last_confirmed_at"]
        # SQLite fixtures omit timezone information; PostgreSQL stores timestamptz.
        if confirmed is not None and confirmed.tzinfo is None:
            confirmed = confirmed.replace(tzinfo=timezone.utc)
        reason = None
        if confirmed is None:
            reason = "No confirmed resume update"
        elif confirmed < cutoff:
            reason = f"No confirmed resume update in the last {stale_days} days"
        items.append(OutreachItem(
            **{key: row[key] for key in ("id", "email", "city", "cohort", "is_demo")},
            full_name=f"{row['first_name']} {row['last_name']}".strip(),
            last_confirmed_at=confirmed, needs_outreach=reason is not None,
            outreach_reason=reason,
        ))
    return OutreachPage(items=items, total=total, limit=limit, offset=offset,
                        stale_days=stale_days, as_of=now)
