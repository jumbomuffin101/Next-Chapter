"""Independent newsletter consent. All writes are explicit; nothing auto-subscribes."""
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from work.database.database import SessionLocal
from work.database.models import Alumni, NewsletterSubscription
from .security import nonce, verify


class NewsletterUnavailable(ValueError):
    pass


@contextmanager
def transaction():
    try:
        with SessionLocal() as session, session.begin():
            yield session
    except ProgrammingError as exc:
        if getattr(exc.orig, "sqlstate", None) == "42P01":
            raise NewsletterUnavailable("Newsletter schema is not installed; apply the approved newsletter migration first.") from None
        raise


def require_demo(session, identifier, *, lock=False):
    query = select(Alumni).where(Alumni.id == UUID(str(identifier)))
    person = session.scalar(query.with_for_update() if lock else query)
    if person is None or not person.is_demo:
        raise PermissionError("Newsletter preferences and delivery are restricted to synthetic demo accounts until verified alumni authentication is available.")
    return person


def status(row):
    return {"subscribed": bool(row and row.subscribed),
            "subscribed_at": timestamp(row.subscribed_at) if row else None,
            "unsubscribed_at": timestamp(row.unsubscribed_at) if row else None,
            "updated_at": timestamp(row.updated_at) if row else None,
            "demo_only": True}


def timestamp(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def read_preference(identifier):
    with transaction() as session:
        require_demo(session, identifier)
        return status(session.get(NewsletterSubscription, UUID(str(identifier))))


def update_preference(identifier, subscribed: bool):
    with transaction() as session:
        person = require_demo(session, identifier, lock=True)
        row = session.get(NewsletterSubscription, person.id)
        now = datetime.now(timezone.utc)
        if row is None:
            row = NewsletterSubscription(alumni_id=person.id, subscribed=False, token_nonce=nonce(), updated_at=now)
            session.add(row)
        if row.subscribed != subscribed:
            row.subscribed = subscribed
            row.token_nonce = nonce()  # Revokes links from earlier consent periods.
            row.updated_at = now
            if subscribed:
                row.subscribed_at = now
            else:
                row.unsubscribed_at = now
        session.flush()
        return {**status(row), "message": "Subscribed to Next Chapter Monthly." if subscribed else "Unsubscribed from Next Chapter Monthly."}


def unsubscribe(token: str):
    value = verify(token, "unsubscribe")
    with transaction() as session:
        # Lock Alumni first, like preferences/delivery, so opt-out and dispatch serialize.
        identifier = session.scalar(select(NewsletterSubscription.alumni_id).where(NewsletterSubscription.token_nonce == value))
        if identifier is None:
            return  # Already revoked/opted out. Do not reveal whether a person exists.
        session.scalar(select(Alumni).where(Alumni.id == identifier).with_for_update())
        row = session.get(NewsletterSubscription, identifier, populate_existing=True)
        if row.token_nonce == value and row.subscribed:
            row.subscribed = False
            row.updated_at = row.unsubscribed_at = datetime.now(timezone.utc)
            row.token_nonce = nonce()
