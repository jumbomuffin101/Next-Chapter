"""Account-specific digests from disposable records; production clients are blocked."""
from dataclasses import asdict
from datetime import date, datetime, timezone
import json
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update

from backend.app.analytics import router as analytics
from backend.app.newsletter import security
from backend.app.newsletter.router import router
from backend.app.newsletter.service import generate_newsletter
from work.database import database
from work.database.models import (Alumni, Job, NewsletterDelivery, NewsletterSubscription,
                                  ResumeUpload, Skill, WorkExperience)

APP_URL = "https://app.example.org"
ALEX = UUID(int=2024)
JORDAN = UUID(int=2023)
REAL = UUID(int=2999)


def bearer(identifier):
    return {"Authorization": "Bearer " + security.demo_session(identifier)}


@pytest.fixture
def synthetic_accounts(isolated_db, monkeypatch):
    monkeypatch.setenv("NEWSLETTER_TOKEN_SECRET", "synthetic-personalization-tests-only-123456")
    monkeypatch.setenv("NEWSLETTER_APP_URL", APP_URL)
    monkeypatch.setattr(database, "readonly_session", analytics.readonly_session)

    with isolated_db.Session.begin() as session:
        for cohort, city, identifier, first, last, peers in (
            ("2024", "New York City", ALEX, "Alex", "Johnson", 3),
            ("2023", "Chicago", JORDAN, "Jordan", "Lee", 2),
        ):
            session.add(Alumni(id=identifier, first_name=first, last_name=last,
                               email=f"{first.lower()}-synthetic@example.org", city=city,
                               cohort=cohort, is_demo=True))
            for index in range(4):
                peer = UUID(int=int(cohort) * 100 + index)
                session.add(Alumni(id=peer, first_name=f"Synthetic{cohort}{index}", last_name="Peer",
                                   email=f"peer-{cohort}-{index}@example.org", city=city,
                                   cohort=cohort, is_demo=True))
                if index < peers - 1:
                    session.add(WorkExperience(alumni_id=peer, title="Example Role", employer="Example",
                                               start_date=date(2024, 1, 1), is_current=True))
            session.add(ResumeUpload(alumni_id=identifier, file_name="synthetic.pdf",
                                     parsed_data={}, confirmed=True))
        session.add(Alumni(id=REAL, first_name="PRIVATE_REAL", last_name="Person",
                           email="private-real@example.org", city="New York", cohort="2024", is_demo=False))
        session.flush()
        session.add_all([
            WorkExperience(alumni_id=ALEX, title="Software Engineer", employer="Example Tech",
                           start_date=date(2023, 1, 1), is_current=True),
            # A later-dated historical role must not override a recorded current role.
            WorkExperience(alumni_id=ALEX, title="Data Analyst", employer="Past Example",
                           start_date=date(2024, 1, 1), end_date=date(2024, 6, 1), is_current=False),
            WorkExperience(alumni_id=JORDAN, title="Data Analyst", employer="Example Data",
                           start_date=date(2022, 1, 1), is_current=True),
            WorkExperience(alumni_id=REAL, title="Software Engineer", employer="Private",
                           start_date=date(2024, 1, 1), is_current=True),
        ])
        for identifier, names in ((ALEX, ("Python", "React", "JavaScript", "SQL")),
                                  (JORDAN, ("SQL", "Tableau", "Excel", "Python"))):
            session.add_all(Skill(alumni_id=identifier, name=name) for name in names)
        stamp = datetime(2026, 10, 10, tzinfo=timezone.utc)
        for code, title, company, city, description, url in (
            ("swe-1", "Software Engineer", "Python React Studio", "New York, NY",
             "<p>Build with Python, React, JavaScript and SQL.</p>", "https://example.org/jobs/swe-1"),
            ("swe-duplicate", "Software Engineer", "Python React Studio", "New York, NY",
             "<p>Build with Python and React.</p>", "https://example.org/jobs/swe-1"),
            ("swe-2", "Software Engineer", "Java Systems", "New York, NY",
             "Java and Spring services.", "https://example.org/jobs/swe-2"),
            ("swe-other-city", "Software Engineer", "Chicago Software", "Chicago, IL",
             "Python and React.", "https://example.org/jobs/swe-chicago"),
            ("data-1", "Data Analyst", "Tableau Analytics", "Chicago, IL",
             "Use SQL, Tableau and Excel.", "https://example.org/jobs/data-1"),
            ("data-2", "Data Analyst", "Power BI Group", "Chicago, IL",
             "Use Power BI and R.", "https://example.org/jobs/data-2"),
            ("data-other-city", "Data Analyst", "NY Analytics", "New York, NY",
             "Use SQL and Tableau.", "https://example.org/jobs/data-ny"),
        ):
            session.add(Job(board_token="synthetic", greenhouse_job_id=code, title=title,
                            company=company, location=city, description=description,
                            absolute_url=url, updated_at=stamp))

    app = FastAPI()
    app.include_router(router)
    return TestClient(app), isolated_db


def test_two_accounts_get_distinct_saved_profile_content_and_email_matches_in_app(synthetic_accounts):
    client, db = synthetic_accounts
    alex_response = client.get("/newsletter/current", headers=bearer(ALEX))
    jordan_response = client.get("/newsletter/current", headers=bearer(JORDAN))
    assert alex_response.status_code == jordan_response.status_code == 200
    alex, jordan = alex_response.json()["content"], jordan_response.json()["content"]
    assert (alex["first_name"], jordan["first_name"]) == ("Alex", "Jordan")
    assert alex["jobs"][0]["company"] == "Python React Studio"
    assert jordan["jobs"][0]["company"] == "Tableau Analytics"
    assert "Relevant skills: " in alex["jobs"][0]["why_matched"]
    assert "Python" in alex["jobs"][0]["why_matched"]
    assert "Tableau" in jordan["jobs"][0]["why_matched"]
    assert "Same metro area" in alex["jobs"][0]["why_matched"]
    assert "Same city" in jordan["jobs"][0]["why_matched"]
    assert all("Chicago Software" != job["company"] for job in alex["jobs"])
    assert all("NY Analytics" != job["company"] for job in jordan["jobs"])
    assert len({job["apply_url"] for job in alex["jobs"]}) == len(alex["jobs"])
    assert any("New York metro" in event["title"] for event in alex["events"])
    assert any("Chicago" in event["title"] for event in jordan["events"])
    assert any("Software & Web Dev Meetup" in event["title"] for event in alex["events"])
    assert any("Data & Analytics Circle" in event["title"] for event in jordan["events"])
    assert all(event["example"] for event in alex["events"] + jordan["events"])
    assert "Cohort 2024" in alex["cohort_message"] and "3 have recorded current roles" in alex["cohort_message"]
    assert "Cohort 2023" in jordan["cohort_message"] and "2 have recorded current roles" in jordan["cohort_message"]
    assert "5 alumni on record" in alex["cohort_message"] and "5 alumni on record" in jordan["cohort_message"]
    assert "PRIVATE_REAL" not in str(alex) and "Jordan Lee" not in str(alex)
    assert "Alex Johnson" not in str(jordan) and "private-real@example.org" not in str(jordan)

    # Email and in-app reads share one generator and must contain the same selections.
    for identifier, content in ((ALEX, alex), (JORDAN, jordan)):
        email = generate_newsletter(identifier, app_url=APP_URL, demo_only=True)
        assert jsonable_encoder(asdict(email.content)) == content
        assert f"Hi {content['first_name']}," in email.text
        assert content["jobs"][0]["title"] in email.html
    with db.Session() as session:
        assert session.scalar(select(func.count()).select_from(NewsletterDelivery)) == 0
        assert session.scalar(select(func.count()).select_from(NewsletterSubscription)) == 0
    print("SYNTHETIC_NEWSLETTERS " + json.dumps({name: {
        "greeting": content["first_name"],
        "jobs": [{"title": job["title"], "company": job["company"], "location": job["location"],
                  "reason": job["why_matched"]} for job in content["jobs"]],
        "events": [event["title"] for event in content["events"]],
        "cohort": content["cohort_message"],
    } for name, content in (("Alex", alex), ("Jordan", jordan))}, sort_keys=True))


def test_token_scope_and_empty_fallbacks(synthetic_accounts):
    client, db = synthetic_accounts
    response = client.get("/newsletter/current", headers=bearer(ALEX), params={"profile_id": str(JORDAN)})
    assert response.status_code == 200 and response.json()["content"]["first_name"] == "Alex"
    assert client.get("/newsletter/current").status_code == 401
    assert client.get("/newsletter/current", headers={"Authorization": "Bearer " + str(JORDAN)}).status_code == 401
    assert client.get("/newsletter/current", headers=bearer(REAL)).status_code == 403
    assert client.get(f"/newsletter/current/{JORDAN}", headers=bearer(ALEX)).status_code == 404

    empty_id = UUID(int=3000)
    with db.Session.begin() as session:
        session.add(Alumni(id=empty_id, first_name="", last_name="", email="empty-synthetic@example.org", is_demo=True))
    empty = client.get("/newsletter/current", headers=bearer(empty_id)).json()["content"]
    assert empty["first_name"] == "there" and empty["jobs"] == []
    assert "Add your TKH cohort" in empty["cohort_message"]
    assert all(event["location"] == "Online" for event in empty["events"])

    with db.Session.begin() as session:
        session.execute(delete(Job))
    no_jobs = client.get("/newsletter/current", headers=bearer(ALEX)).json()["content"]
    assert no_jobs["jobs"] == []


def test_profile_update_is_reflected_on_next_read_without_cross_contamination(synthetic_accounts):
    client, db = synthetic_accounts
    before = client.get("/newsletter/current", headers=bearer(ALEX)).json()["content"]
    assert before["jobs"][0]["company"] == "Python React Studio"
    with db.Session.begin() as session:
        session.execute(update(Alumni).where(Alumni.id == ALEX).values(city="Chicago", cohort="2023"))
        session.execute(update(WorkExperience).where(WorkExperience.alumni_id == ALEX)
                        .values(title="Data Analyst"))
        session.execute(delete(Skill).where(Skill.alumni_id == ALEX))
        session.add_all(Skill(alumni_id=ALEX, name=name) for name in ("SQL", "Tableau", "Excel"))
    after = client.get("/newsletter/current", headers=bearer(ALEX)).json()["content"]
    jordan = client.get("/newsletter/current", headers=bearer(JORDAN)).json()["content"]
    again = client.get("/newsletter/current", headers=bearer(ALEX)).json()["content"]
    assert after == again
    assert after["jobs"][0]["company"] == "Tableau Analytics"
    assert all("Software Engineer" not in job["title"] for job in after["jobs"])
    assert any("Chicago" in event["title"] for event in after["events"])
    assert "Cohort 2023" in after["cohort_message"]
    assert "Cohort 2023" in jordan["cohort_message"]
    assert jordan["first_name"] == "Jordan" and after["first_name"] == "Alex"
    assert before["cohort_message"] != after["cohort_message"]
