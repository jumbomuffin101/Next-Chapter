"""Read-only in-app newsletter checks against isolated in-memory SQLite."""
from datetime import date
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.analytics import router as analytics
from backend.app.newsletter import security
from backend.app.newsletter.calendar import current_month
from backend.app.newsletter.router import router
from work.database import database
from work.database.models import Alumni, Job, NewsletterDelivery, NewsletterSubscription, SalaryRecord, WorkExperience


@pytest.fixture
def current_setup(isolated_db, monkeypatch):
    monkeypatch.setenv("NEWSLETTER_TOKEN_SECRET", "synthetic-test-only-signing-value-123456789")
    monkeypatch.setenv("NEWSLETTER_APP_URL", "https://app.example.org")
    monkeypatch.setattr(database, "readonly_session", analytics.readonly_session)
    demo_ids = [UUID(int=9000 + index) for index in range(6)]
    real_id = UUID(int=9999)
    with isolated_db.Session.begin() as session:
        for index, identifier in enumerate(demo_ids):
            session.add(Alumni(id=identifier, first_name=f"Example{index}", last_name="Demo",
                               email=f"demo-{index}@example.org", city="New York", cohort="2022", is_demo=True))
        session.add(Alumni(id=real_id, first_name="PRIVATE_REAL", last_name="Person",
                           email="private@example.org", city="New York", cohort="2022", is_demo=False))
        session.flush()
        session.add(WorkExperience(alumni_id=demo_ids[0], employer="Example Employer",
                                   title="Software Engineer", start_date=date(2023, 1, 1), is_current=True))
        session.add(Job(board_token="example", greenhouse_job_id="123", title="Software Engineer",
                        company="Example Employer", location="New York, NY",
                        absolute_url="https://boards.greenhouse.io/example/jobs/123"))
        session.add(SalaryRecord(alumni_id=demo_ids[0], salary_min=81234, salary_max=91234,
                                 source="self_reported", effective_date=date(2024, 1, 1)))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), isolated_db, demo_ids, real_id


def auth(identifier):
    return {"Authorization": "Bearer " + security.demo_session(identifier)}


def test_current_digest_is_personalized_demo_only_and_has_no_writes(current_setup):
    client, db, demo_ids, _ = current_setup
    response = client.get("/newsletter/current", headers=auth(demo_ids[0]))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["month"] == current_month() and body["demo_only"] is True
    content = body["content"]
    assert content["first_name"] == "Example0"
    assert content["jobs"][0]["title"] == "Software Engineer"
    assert content["jobs"][0]["apply_url"] == "https://boards.greenhouse.io/example/jobs/123"
    assert all(event["example"] for event in content["events"])
    assert "Synthetic demo records only" in content["cohort_message"]
    assert "PRIVATE_REAL" not in str(body) and "81234" not in str(body)
    with db.Session() as session:
        assert session.scalar(select(func.count()).select_from(NewsletterSubscription)) == 0
        assert session.scalar(select(func.count()).select_from(NewsletterDelivery)) == 0


def test_current_digest_is_bound_to_token_and_works_without_subscription(current_setup):
    client, _, demo_ids, real_id = current_setup
    first = client.get("/newsletter/current", headers=auth(demo_ids[0]), params={"profile_id": str(demo_ids[1])})
    other = client.get("/newsletter/current", headers=auth(demo_ids[1]))
    assert first.json()["content"]["first_name"] == "Example0"
    assert other.json()["content"]["first_name"] == "Example1"
    assert other.json()["content"]["jobs"] == []
    assert client.get("/newsletter/current").status_code == 401
    assert client.get("/newsletter/current", headers={"Authorization": "Bearer " + str(demo_ids[0])}).status_code == 401
    assert client.get("/newsletter/current", headers=auth(real_id)).status_code == 403
    assert client.get(f"/newsletter/current/{demo_ids[1]}", headers=auth(demo_ids[0])).status_code == 404
