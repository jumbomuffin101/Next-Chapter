import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.jobs import greenhouse, router as jobs
from backend.app.jobs.matching import MatchProfile, top_matches


def test_empty_successful_board_removes_stale_jobs_but_failed_board_does_not(monkeypatch):
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    monkeypatch.setattr(greenhouse, "get_conn", lambda: connection)
    monkeypatch.setattr(greenhouse, "BOARD_TOKENS", ["empty", "failed"])

    def fetch(token):
        if token == "failed":
            raise RuntimeError("Synthetic failure")
        return []

    monkeypatch.setattr(greenhouse, "fetch_board", fetch)
    result = greenhouse.refresh_jobs()  # SQL and network both mocked.
    assert result["per_board"] == {"empty": 0} and "failed" in result["failed"]
    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[1] == ("empty", [])


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_match_limit_never_queries_database(monkeypatch, limit):
    connection = MagicMock(side_effect=AssertionError("No database access"))
    monkeypatch.setattr(jobs, "get_conn", connection)
    app = FastAPI()
    app.include_router(jobs.router)
    with TestClient(app) as client:
        assert client.get(f"/users/{uuid.uuid4()}/job-matches?limit={limit}").status_code == 422
    connection.assert_not_called()


def test_tied_match_scores_have_stable_order():
    profile = MatchProfile("Software Engineer", "New York, NY")
    jobs_list = [{"id": n, "title": "Software Engineer", "company": "Demo", "location": "New York, NY",
                  "absolute_url": "https://example.com/job"} for n in (2, 1)]
    assert [row["job_id"] for row in top_matches(profile, jobs_list)] == [1, 2]
    assert top_matches(profile, jobs_list) == top_matches(profile, list(reversed(jobs_list)))


def test_saved_skills_feed_the_shared_job_matcher(monkeypatch):
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"city": "New York City", "salary_min": None, "salary_max": None}
    cursor.fetchall.side_effect = [[{"title": "Software Engineer"}],
                                   [{"name": "Python"}, {"name": "React"}]]
    monkeypatch.setattr(jobs, "get_conn", lambda: connection)
    profile = jobs.load_match_profile(uuid.UUID(int=2024))
    assert profile.skills == ("Python", "React")
    assert profile.city == "New York City"
    assert cursor.execute.call_count == 3


def test_refresh_requires_the_admin_token(monkeypatch):
    from backend.app.auth.router import make_admin_token
    calls = []
    monkeypatch.setattr(jobs, "refresh_jobs", lambda: calls.append(1) or {"jobs_upserted": 0})
    app = FastAPI()
    app.include_router(jobs.router)
    with TestClient(app) as client:
        assert client.post("/jobs/refresh").status_code == 401
        assert client.post("/jobs/refresh", headers={"Authorization": "Bearer nope"}).status_code == 401
        assert calls == []  # rejected before any Greenhouse calls or database writes
        ok = client.post("/jobs/refresh", headers={"Authorization": f"Bearer {make_admin_token()}"})
        assert ok.status_code == 200 and calls == [1]


def test_schedule_waits_one_interval_after_the_last_sync_and_never_loops_fast():
    from datetime import datetime, timedelta, timezone
    from backend.app.jobs.scheduler import next_due
    now = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
    day = timedelta(hours=24)
    assert next_due(None, None, day, now) == now                                        # never synced: refresh now
    assert next_due(now - timedelta(hours=2), None, day, now) == now + timedelta(hours=22)
    assert next_due(now - timedelta(days=3), None, day, now) == now                      # overdue: refresh now
    # every board failed, so the sync time did not move: wait an hour after the last run, not zero seconds
    assert next_due(now - timedelta(days=3), now - timedelta(minutes=5), day, now) == now + timedelta(minutes=55)


@pytest.mark.parametrize("value, enabled", [("24", True), ("0.5", True), ("0", False)])
def test_schedule_interval_from_env(monkeypatch, value, enabled):
    from backend.app.jobs import scheduler
    monkeypatch.setenv("JOB_REFRESH_HOURS", value)
    assert (scheduler.interval_hours() > 0) is enabled
    if not enabled:
        assert scheduler.start() is None


@pytest.mark.parametrize("value", ["daily", "-1"])
def test_bad_schedule_interval_is_an_error(monkeypatch, value):
    from backend.app.jobs import scheduler
    monkeypatch.setenv("JOB_REFRESH_HOURS", value)
    with pytest.raises(RuntimeError):
        scheduler.interval_hours()
