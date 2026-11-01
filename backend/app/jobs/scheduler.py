"""Scheduled Greenhouse refresh, run inside the API process (started by main.py when the app starts).

JOB_REFRESH_HOURS sets the interval (default 24); 0 turns the schedule off. A refresh is due one interval after the job list
was last synced (immediately if it never was). A failed run is logged and shown on the admin Automation page. Runs are
always at least RETRY_AFTER (or the interval, if shorter) apart, so failing boards are never polled in a tight loop.
"""
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..db import get_conn
from .greenhouse import refresh_jobs

log = logging.getLogger(__name__)
RETRY_AFTER = timedelta(hours=1)
STATUS = {"next_run_at": None, "last_run_at": None, "last_result": None, "last_error": None}


def interval_hours() -> float:
    raw = os.getenv("JOB_REFRESH_HOURS", "24").strip()
    try:
        hours = float(raw)
    except ValueError:
        raise RuntimeError("JOB_REFRESH_HOURS must be a number of hours (0 turns the scheduled refresh off)") from None
    if hours < 0:
        raise RuntimeError("JOB_REFRESH_HOURS must be 0 or more")
    return hours


def next_due(last_synced: Optional[datetime], last_run: Optional[datetime], interval: timedelta, now: datetime) -> datetime:
    due = now if last_synced is None else max(now, last_synced + interval)
    return due if last_run is None else max(due, last_run + min(RETRY_AFTER, interval))


def last_synced_at() -> Optional[datetime]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT max(last_synced_at) FROM jobs")
        return cur.fetchone()[0]


def _run_loop(stop: threading.Event, interval: timedelta) -> None:
    while not stop.is_set():
        now = datetime.now(timezone.utc)
        try:
            due = next_due(last_synced_at(), STATUS["last_run_at"], interval, now)
        except Exception as e:  # database unreachable: report it and try again later
            log.exception("Scheduled job refresh: could not read the last sync time")
            # only the error type on the admin page: database errors can name the host and user; details are in the server log
            STATUS["last_error"] = f"Could not read the job list ({type(e).__name__}); see the server log"
            due = now + min(RETRY_AFTER, interval)
        STATUS["next_run_at"] = due
        if stop.wait(max(0.0, (due - now).total_seconds())):
            return
        STATUS["last_run_at"] = datetime.now(timezone.utc)
        try:
            result = refresh_jobs()
            STATUS["last_result"], STATUS["last_error"] = result, None
            log.info("Scheduled job refresh: %s jobs, failed boards: %s", result["jobs_upserted"], list(result["failed"]))
        except Exception as e:
            log.exception("Scheduled job refresh failed")
            STATUS["last_error"] = f"Refresh failed ({type(e).__name__}); see the server log"


def start() -> Optional[threading.Event]:
    """Start the background schedule. Returns the stop event, or None when JOB_REFRESH_HOURS is 0."""
    hours = interval_hours()
    if hours == 0:
        log.info("Scheduled job refresh is off (JOB_REFRESH_HOURS=0)")
        return None
    stop = threading.Event()
    threading.Thread(target=_run_loop, args=(stop, timedelta(hours=hours)), name="job-refresh", daemon=True).start()
    return stop


def status() -> dict:
    hours = interval_hours()
    return {"enabled": hours > 0, "interval_hours": hours, "last_synced_at": last_synced_at(),
            "next_run_at": STATUS["next_run_at"] if hours > 0 else None,
            "last_run_at": STATUS["last_run_at"], "last_error": STATUS["last_error"],
            "failed_boards": sorted((STATUS["last_result"] or {}).get("failed", {}))}
