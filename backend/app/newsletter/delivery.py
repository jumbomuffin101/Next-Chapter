"""Single-recipient dispatch; retries require an explicit safe-retry request."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from work.database.models import Alumni, NewsletterDelivery, NewsletterSubscription
from .preferences import require_demo, timestamp, transaction
from .provider import Message, ProviderFailure, ResendAdapter, Settings, email_valid
from .render import render
from .security import unsubscribe_token
from .service import generate_newsletter
from .calendar import current_month, month_start, scheduled_at


def may_retry(row, requested):
    return bool(requested and row.status == "retryable" and row.error_code == "provider_rate_limited")


def delivery_status(row):
    return {"month": row.month.strftime("%Y-%m"), "status": row.status,
            "error_code": row.error_code, "retryable": row.status == "retryable",
            "updated_at": timestamp(row.updated_at)}


def get_delivery(identifier, month: str):
    with transaction() as session:
        row = session.scalar(select(NewsletterDelivery).where(
            NewsletterDelivery.alumni_id == UUID(str(identifier)), NewsletterDelivery.month == month_start(month)))
        return delivery_status(row) if row else {"month": month, "status": "not_attempted", "retryable": False}


def deliver(identifier, month: str, *, adapter=None, retry_failed=False):
    settings = Settings.load()
    when = month_start(month)
    now = datetime.now(timezone.utc)
    if month != current_month(now):
        raise ValueError("Only the current America/New_York newsletter month may be dispatched")
    identifier = UUID(str(identifier))
    # Inspect consent before generating any personalized content.
    with transaction() as session:
        person = require_demo(session, identifier)
        subscription = session.get(NewsletterSubscription, identifier)
        if subscription is None or not subscription.subscribed:
            return {"month": month, "status": "not_subscribed", "retryable": False}
        existing = session.scalar(select(NewsletterDelivery).where(
            NewsletterDelivery.alumni_id == identifier, NewsletterDelivery.month == when))
        if existing and existing.status != "dry_run" and not may_retry(existing, retry_failed):
            return delivery_status(existing)
        consent = subscription.token_nonce
    newsletter = generate_newsletter(identifier, app_url=settings.app_url, events_after=scheduled_at(month).date())
    unsubscribe_url = settings.api_url + "newsletter/unsubscribe?token=" + unsubscribe_token(consent)
    newsletter = render(newsletter.content, unsubscribe_url=unsubscribe_url,
                        sender_name=settings.sender_name, sender_address=settings.sender_address,
                        preview=settings.dry_run)
    # Persist a durable claim before contacting the provider. Every competing
    # dispatch/consent change locks the same Alumni row; DB uniqueness is a second guard.
    with transaction() as session:
        person = require_demo(session, identifier, lock=True)
        subscription = session.get(NewsletterSubscription, identifier)
        if not subscription or not subscription.subscribed or subscription.token_nonce != consent:
            return {"month": month, "status": "not_subscribed", "retryable": False}
        existing = session.scalar(select(NewsletterDelivery).where(
            NewsletterDelivery.alumni_id == identifier, NewsletterDelivery.month == when))
        if existing and existing.status != "dry_run" and not may_retry(existing, retry_failed):
            return delivery_status(existing)
        if not email_valid(person.email):
            raise ValueError("The synthetic recipient needs a valid email address")
        if not settings.dry_run:
            settings.validate_live(person.email)
        row = existing or NewsletterDelivery(alumni_id=identifier, month=when)
        row.status = "dry_run" if settings.dry_run else "attempting"
        row.error_code = None
        row.updated_at = now
        session.add(row)
        session.flush()
        delivery_id, recipient = row.id, person.email
        # A new key is safe only after a definite 429 rejection. Unknown/accepted
        # claims never reach here again. The monthly row remains the durable guard.
        attempt_key = f"newsletter/{delivery_id}/{uuid4().hex}"
        if settings.dry_run:
            return delivery_status(row)  # Never instantiate/call a provider in dry-run.
    # Recheck opt-out and hold the recipient lock through the single provider call.
    # An opt-out that wins this lock suppresses dispatch; an already in-flight
    # provider request cannot be recalled. Any crash leaves an unretryable claim.
    with transaction() as session:
        person = require_demo(session, identifier, lock=True)
        subscription = session.get(NewsletterSubscription, identifier)
        row = session.get(NewsletterDelivery, delivery_id)
        if not subscription or not subscription.subscribed or subscription.token_nonce != consent or person.email != recipient:
            row.status, row.error_code = "failed", "consent_or_address_changed"
        else:
            message = Message(recipient, f"{settings.sender_name} <{settings.sender_email}>", newsletter.subject,
                              newsletter.html, newsletter.text, unsubscribe_url, attempt_key)
            try:
                row.provider_message_id = (adapter or ResendAdapter(settings.api_key)).send(message)
                row.status = "accepted"  # Provider acceptance, not inbox/delivery confirmation.
            except ProviderFailure as exc:
                row.status = "unknown" if exc.uncertain else "retryable" if exc.retryable else "failed"
                row.error_code = exc.code
            except Exception:
                row.status, row.error_code = "unknown", "provider_unexpected_unknown"
        row.updated_at = datetime.now(timezone.utc)
        session.flush()
        return delivery_status(row)
