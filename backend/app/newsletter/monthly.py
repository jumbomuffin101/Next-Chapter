"""Standalone monthly CLI. Never imported/started as a FastAPI background worker."""
import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import time

from .calendar import TIMEZONE, current_month, local_now, month_start, scheduled_at


@dataclass
class Result:
    month: str
    mode: str
    timezone: str = TIMEZONE
    eligible: int = 0
    processed: int = 0
    success: int = 0
    skipped: int = 0
    failed: int = 0
    retries: int = 0
    deferred: int = 0
    status: str = "complete"


def eligible_query(month: str, *, live: bool, allowlist, retry_failed: bool, actionable=True):
    from sqlalchemy import and_, func, or_, select
    from work.database.models import Alumni, NewsletterDelivery, NewsletterSubscription
    query = select(Alumni.id).join(NewsletterSubscription, NewsletterSubscription.alumni_id == Alumni.id).outerjoin(
        NewsletterDelivery, and_(NewsletterDelivery.alumni_id == Alumni.id, NewsletterDelivery.month == month_start(month)),
    ).where(Alumni.is_demo.is_(True), NewsletterSubscription.subscribed.is_(True))
    if live:
        query = query.where(func.lower(Alumni.email).in_(allowlist))
    if actionable:
        conditions = [NewsletterDelivery.id.is_(None), NewsletterDelivery.status == "dry_run"]
        if retry_failed:
            conditions.append(and_(NewsletterDelivery.status == "retryable", NewsletterDelivery.error_code == "provider_rate_limited"))
        query = query.where(or_(*conditions))
    return query


def run_month(month: str, *, live=False, limit=None, batch_size=50, retry_failed=False,
              max_retries=2, adapter=None, now: datetime | None = None, sleep=time.sleep) -> Result:
    """Read-only simulation by default. Only live dispatch writes the existing ledger."""
    from sqlalchemy import func, select
    from work.database.database import readonly_session
    from .provider import Settings
    from .service import generate_newsletter
    from .delivery import deliver

    month_start(month)
    if not 1 <= batch_size <= 500 or (limit is not None and not 1 <= limit <= 10000) or not 0 <= max_retries <= 5:
        raise ValueError("Invalid newsletter batch bounds")
    settings = Settings.load()
    if live:
        if settings.dry_run:
            raise ValueError("Live authorization also requires NEWSLETTER_DRY_RUN=false")
        if month != current_month(now):
            raise ValueError("Live runs require the current America/New_York month")
        # Validate before any delivery claims, including the empty-recipient case.
        settings.validate_live(next(iter(sorted(settings.allowlist)), ""))
    result = Result(month, "live" if live else "dry_run")
    query = eligible_query(month, live=live, allowlist=settings.allowlist, retry_failed=retry_failed)
    all_query = eligible_query(month, live=live, allowlist=settings.allowlist, retry_failed=retry_failed, actionable=False)
    with readonly_session() as session:
        result.eligible = session.scalar(select(func.count()).select_from(all_query.subquery()))
        count = session.scalar(select(func.count()).select_from(query.subquery()))
        result.skipped = result.eligible - count
        # Freeze an upper UUID bound; subscriptions are still rechecked later.
        upper = session.scalar(query.order_by(query.selected_columns.id.desc()).limit(1))
    after = None
    remaining = limit if limit is not None else count
    while remaining > 0 and upper is not None:
        from work.database.models import Alumni, NewsletterSubscription
        batch = query.where(Alumni.id <= upper)
        if after is not None:
            batch = batch.where(Alumni.id > after)
        with readonly_session() as session:
            identifiers = session.scalars(batch.order_by(Alumni.id).limit(min(batch_size, remaining))).all()
        if not identifiers:
            break
        for identifier in identifiers:
            after = identifier
            remaining -= 1
            result.processed += 1
            try:
                if not live:
                    # Never call deliver in dry-run: that legacy API records a dry-run row.
                    with readonly_session() as session:
                        subscribed = session.scalar(select(Alumni.id).join(NewsletterSubscription).where(
                            Alumni.id == identifier, Alumni.is_demo.is_(True), NewsletterSubscription.subscribed.is_(True)))
                    if subscribed is None:
                        result.skipped += 1
                        continue
                    generate_newsletter(identifier, app_url=settings.app_url, events_after=scheduled_at(month).date())
                    result.success += 1
                    continue
                outcome = deliver(identifier, month, adapter=adapter, retry_failed=retry_failed)
                attempts = 0
                while outcome["status"] == "retryable" and attempts < max_retries:
                    sleep(min(2 ** attempts, 16))
                    result.retries += 1
                    attempts += 1
                    outcome = deliver(identifier, month, adapter=adapter, retry_failed=True)
                if outcome["status"] == "accepted":
                    result.success += 1
                elif outcome["status"] in {"not_subscribed", "dry_run"}:
                    result.skipped += 1
                else:
                    result.failed += 1
            except Exception:
                # No per-recipient IDs, email, provider error text, or tracebacks in CLI logs.
                result.failed += 1
    result.deferred = max(0, count - result.processed)
    if result.failed:
        result.status = "partial_failure"
    return result


def monthly_enabled() -> bool:
    """The admin Automation page's on/off switch for the scheduled run (on unless the career team turned it off)."""
    from psycopg.rows import dict_row
    from ..db import get_conn
    from .switch import monthly_enabled as enabled
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        return enabled(cur)


def parser():
    result = argparse.ArgumentParser(description="Monthly newsletter runner. Default: read-only dry-run. No installed scheduler.")
    mode = result.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Simulate without provider calls or ledger writes (default)")
    mode.add_argument("--authorize-live", action="store_true", help="Explicitly authorize guarded demo delivery; requires separate operator approval")
    result.add_argument("--month", help="YYYY-MM; default is the current America/New_York month")
    result.add_argument("--limit", type=int)
    result.add_argument("--batch-size", type=int, default=50)
    result.add_argument("--retry-failed", action="store_true", help="Include previous definite rate-limit rejections only")
    result.add_argument("--max-retries", type=int, default=2, help="Bounded rate-limit retries per recipient (0–5)")
    result.add_argument("--scheduled", action="store_true", help="Require explicit scheduling-enabled environment switch and due date")
    result.add_argument("--preview", action="store_true", help="Synthetic-only offline files; no database configuration needed")
    result.add_argument("--output-dir", type=Path)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        month = args.month or current_month()
        month_start(month)
        if args.preview:
            if args.authorize_live or args.scheduled or not args.output_dir:
                raise ValueError("Preview requires an output directory and cannot authorize delivery")
            from .preview import demo_newsletter
            newsletter = demo_newsletter(today=max(local_now().date(), scheduled_at(month).date()))
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for suffix, body in [("html", newsletter.html), ("txt", newsletter.text)]:
                with (args.output_dir / f"next-chapter-{month}.{suffix}").open("x", encoding="utf-8") as output:
                    output.write(body)
            print(json.dumps({"status": "complete", "mode": "synthetic_preview", "month": month, "emails_sent": 0}))
            return 0
        if args.output_dir:
            raise ValueError("Output files are supported only for synthetic preview")
        if args.scheduled and os.getenv("NEWSLETTER_SCHEDULING_ENABLED", "false").lower() != "true":
            print(json.dumps({"status": "disabled", "month": month, "emails_sent": 0}))
            return 0
        if args.scheduled and (month != current_month() or local_now() < scheduled_at(month)):
            print(json.dumps({"status": "not_due", "month": month, "emails_sent": 0}))
            return 0
        if args.scheduled and not monthly_enabled():
            print(json.dumps({"status": "paused_by_admin", "month": month, "emails_sent": 0}))
            return 0
        report = run_month(month, live=args.authorize_live, limit=args.limit, batch_size=args.batch_size,
                           retry_failed=args.retry_failed, max_retries=args.max_retries)
        print(json.dumps(asdict(report)))
        return 1 if report.failed else 0
    except Exception as exc:
        missing = getattr(getattr(exc, "orig", None), "sqlstate", None) == "42P01"
        print(json.dumps({"status": "blocked", "reason": "newsletter_schema_pending" if missing else "newsletter_execution_failed",
                          "action": "Review approved newsletter.sql and scheduler configuration; no migration is run automatically."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
