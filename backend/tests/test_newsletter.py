"""Newsletter checks are offline; production database clients are never used."""
from dataclasses import asdict
from datetime import date, datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import func, select

from backend.app.jobs.matching import MatchProfile
from backend.app.newsletter import content as selection
from backend.app.newsletter.content import CohortCounts, Profile, application_url, compose, safe_url
from backend.app.newsletter.render import render
from backend.app.newsletter.service import generate_newsletter

TODAY = date(2026, 10, 17)


def job(identifier=1, **overrides):
    return {"id": str(identifier), "title": "Software Engineer", "company": "Example Company",
            "location": "New York, NY", "absolute_url": f"https://example.org/jobs/{identifier}",
            "salary_min": 70000, "salary_max": 100000,
            "updated_at": datetime(2026, 10, 10, tzinfo=timezone.utc), **overrides}


def build(jobs=None, profile=None, matching=None, counts=None):
    return compose(profile or Profile("Jordan", "New York", "2022"),
                   matching or MatchProfile("Software Engineer", "New York", 80000, 90000),
                   jobs or [], counts, app_url="https://app.example.org/next-chapter/", today=TODAY)


def test_selection_reuses_matcher_eligibility_and_recency():
    jobs = [job(i, updated_at=datetime(2026, 10, i, tzinfo=timezone.utc)) for i in range(1, 8)]
    jobs += [job(8, title="Engineering Manager"), job(9, location="Remote UK"),
             job(10, title="Account Executive"), job(11, location="Los Angeles, CA")]
    result = build(jobs)
    assert len(result.jobs) == 5
    assert [j.apply_url for j in result.jobs] == [f"https://example.org/jobs/{i}" for i in range(7, 2, -1)]
    assert all("Similar role" in j.why_matched and "Same city" in j.why_matched
               and "Salary in range" in j.why_matched for j in result.jobs)
    assert all(not j.example for j in result.jobs)


def test_relevance_precedes_recency_and_ties_are_stable():
    weak = job(1, title="Backend Developer", salary_min=None, salary_max=None,
               updated_at="2026-10-17T00:00:00Z")
    strong = job(2, updated_at="2026-10-01T00:00:00Z")
    assert build([weak, strong]).jobs[0].title == "Software Engineer"
    assert build([job(2), job(1)]).jobs == build([job(1), job(2)]).jobs


def test_unknown_update_dates_do_not_crash_or_claim_posting_dates():
    result = build([job(1, updated_at="bad"), job(2, updated_at=None), job(3)])
    assert result.jobs[0].apply_url.endswith("/3")
    newsletter = render(result)
    assert "Employer updated:" in newsletter.text
    assert "posted on" not in newsletter.text.lower()
    assert result.jobs[1].updated_on is None


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,unsafe", "//example.org", "file:///tmp/x",
                                 "https://user:password@example.org", "https://example.org\n.evil", "https://example.org:bad"])
def test_unsafe_links_are_rejected(url):
    assert safe_url(url) is None
    assert build([job(absolute_url=url)]).jobs == ()


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://app.example.org/?token=private", "https://app.example.org/#bad"])
def test_application_links_are_validated(url):
    with pytest.raises(ValueError):
        application_url(url)


def test_escaping_plain_text_and_safe_existing_app_entry_point():
    result = build([job(title='Software Engineer <img src=x onerror="bad">', company="A&B <script>bad()</script>")],
                   profile=Profile('<script>alert("name")</script>', "New York", "<b>2022</b>"),
                   counts=CohortCounts(5, 4, 3))
    newsletter = render(result)
    assert "<script>" not in newsletter.html and "<img src=x" not in newsletter.html
    assert "&lt;script&gt;" in newsletter.html and "A&amp;B" in newsletter.html
    assert "A&B <script>bad()</script>" in newsletter.text
    assert 'href="https://app.example.org/next-chapter/"' in newsletter.html
    assert "Job Monitor" in newsletter.text and "/jobs/monitor" not in newsletter.html
    for heading in ["Job Opportunities", "Upcoming Events", "Cohort Updates and Summary"]:
        assert heading in newsletter.html and heading in newsletter.text


def test_missing_profile_fields_jobs_and_events(monkeypatch):
    monkeypatch.setattr(selection, "events_for", lambda *args: {})
    newsletter = render(compose(Profile(), None, [job()], None, app_url="http://localhost:5173", today=TODAY))
    assert "Hi there," in newsletter.text
    assert newsletter.content.jobs == newsletter.content.events == ()
    assert "No eligible job listings" in newsletter.text and "No upcoming event" in newsletter.text
    assert "Add your TKH cohort" in newsletter.text
    assert "Job Monitor" in newsletter.text


def test_reuses_relevant_future_events_with_explicit_example_labels():
    newsletter = render(build())
    assert 1 <= len(newsletter.content.events) <= 3
    assert all(e.date > TODAY and e.example for e in newsletter.content.events)
    assert "Software & Web Dev Meetup" in [e.title for e in newsletter.content.events]
    assert "EXAMPLE EVENT" in newsletter.html and "not a scheduled TKH event" in newsletter.text


def test_past_and_malformed_events_are_excluded(monkeypatch):
    data = selection.events_for("New York", "software", TODAY)
    stale = {**data['local'][0], 'date': TODAY.isoformat()}
    invalid = {**stale, 'date': 'invalid'}
    monkeypatch.setattr(selection, "events_for", lambda *args: {'local': [stale, invalid], 'online': []})
    assert build().events == ()


@pytest.mark.parametrize("count", [0, 1, 4])
def test_small_cohort_privacy_suppresses_all_statistics(count):
    newsletter = render(build(counts=CohortCounts(count, count, count)))
    assert "not enough shareable data" in newsletter.text
    assert "alumni on record" not in newsletter.text
    assert "have confirmed resumes" not in newsletter.text


def test_shareable_cohort_totals_have_no_monthly_or_salary_claims():
    newsletter = render(build(counts=CohortCounts(8, 6, 5)))
    assert "8 alumni on record" in newsletter.text and "6 have recorded current roles" in newsletter.text
    assert "synthetic demo records excluded" in newsletter.text
    assert "current totals, not changes this month" in newsletter.text
    assert "salary_min" not in str(asdict(newsletter.content))
    assert "80000" not in newsletter.text and "90000" not in newsletter.html


def test_synthetic_preview_is_labelled_and_offline_without_database_configuration(tmp_path):
    environment = {**os.environ, "DATABASE_URL": "intentionally-invalid-no-database", "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-B", "-m", "backend.app.newsletter.preview", "--output-dir", str(tmp_path)],
                            cwd=Path(__file__).resolve().parents[2], env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    html = (tmp_path / "next-chapter-monthly.html").read_text(encoding="utf-8")
    text = (tmp_path / "next-chapter-monthly.txt").read_text(encoding="utf-8")
    assert "SYNTHETIC DEMO PREVIEW" in html and "Synthetic demo records only" in text
    assert "Example job" in html and "not a live listing" in text
    assert "EXAMPLE EVENT" in html
    again = subprocess.run([sys.executable, "-B", "-m", "backend.app.newsletter.preview", "--output-dir", str(tmp_path)],
                           cwd=Path(__file__).resolve().parents[2], env=environment, capture_output=True)
    assert again.returncode != 0  # Never overwrite existing output.
    assert (tmp_path / "next-chapter-monthly.html").read_text(encoding="utf-8") == html


@pytest.fixture
def stored_profiles(isolated_db, monkeypatch):
    from work.database import database
    from work.database.models import Alumni, Job, ResumeUpload, SalaryRecord, WorkExperience
    from backend.app.analytics import router as analytics
    # Reuse the asserted SQLite fixture and its query-only read session. Both live clients are blocked.
    monkeypatch.setattr(database, "readonly_session", analytics.readonly_session)
    identifiers = [uuid.UUID(int=1000 + i) for i in range(10)]
    with isolated_db.Session.begin() as session:
        for i, identifier in enumerate(identifiers):
            session.add(Alumni(id=identifier, first_name="Recipient" if i == 0 else "PRIVATE_OTHER_NAME",
                               last_name="Example", email=f"private-{i}@example.org", city="New York",
                               cohort="2022", is_demo=i >= 5))
        session.flush()
        for identifier in identifiers:
            session.add_all([WorkExperience(alumni_id=identifier, title="Software Engineer", employer="Example",
                                            start_date=date(2024, 1, 1), is_current=True),
                             ResumeUpload(alumni_id=identifier, file_name="private.pdf", confirmed=True,
                                          parsed_data={"private": "DO_NOT_DISCLOSE"})])
        session.add(SalaryRecord(alumni_id=identifiers[0], salary_min=81234, salary_max=91234,
                                 source="self_reported", effective_date=TODAY))
        session.add(Job(board_token="example", greenhouse_job_id="1", title="Software Engineer",
                        company="Example Company", location="New York", absolute_url="https://example.org/jobs/1"))
    return identifiers


def test_database_service_separates_real_and_demo_without_exposing_private_rows(isolated_db, stored_profiles):
    newsletter = generate_newsletter(stored_profiles[0], app_url="https://app.example.org")
    assert "5 alumni on record" in newsletter.text  # Five real, not all ten.
    assert "synthetic demo records excluded" in newsletter.text
    assert len(newsletter.content.jobs) == 1  # Never pad with invented listings.
    for private in ["PRIVATE_OTHER_NAME", "private-", "private.pdf", "DO_NOT_DISCLOSE", "81234", "91234"]:
        assert private not in newsletter.html and private not in newsletter.text
    demo = generate_newsletter(stored_profiles[5], app_url="https://app.example.org")
    assert "5 alumni on record" in demo.text and "Synthetic demo records only" in demo.text
    from work.database.models import ResumeUpload
    with isolated_db.Session() as session:
        assert session.scalar(select(func.count()).select_from(ResumeUpload)) == 10


def test_service_missing_profile_and_invalid_url(isolated_db, stored_profiles):
    with pytest.raises(LookupError, match="Alumni profile not found"):
        generate_newsletter(uuid.UUID(int=99999), app_url="https://app.example.org")
    with pytest.raises(ValueError, match="Application URL"):
        generate_newsletter(stored_profiles[0], app_url="javascript:alert(1)")


def test_database_service_without_roles_or_cohort_returns_useful_empty_state(isolated_db, stored_profiles):
    from work.database.models import Alumni
    identifier = uuid.UUID(int=5000)
    with isolated_db.Session.begin() as session:
        session.add(Alumni(id=identifier, first_name="", last_name="", email="empty@example.org"))
    newsletter = generate_newsletter(identifier, app_url="https://app.example.org")
    assert newsletter.content.first_name == "there"
    assert newsletter.content.jobs == ()
    assert "Add your TKH cohort" in newsletter.text and "Job Monitor" in newsletter.text


def test_no_newsletter_route_exposes_personal_content():
    from backend.app.main import app
    paths = app.openapi()["paths"]
    assert not any("newsletter" in path and "preview" in path for path in paths)
    from fastapi.testclient import TestClient
    assert TestClient(app).get('/newsletter/preferences').status_code == 401
