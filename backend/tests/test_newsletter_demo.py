"""Offline demo endpoint checks; the live database clients are blocked by isolated_db."""
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.newsletter import demo, router


def client(isolated_db, monkeypatch):
    from work.database import database
    from backend.app.analytics import router as analytics
    from work.database.models import Alumni, Job

    monkeypatch.setattr(database, "readonly_session", analytics.readonly_session)
    monkeypatch.setenv("NEWSLETTER_APP_URL", "http://localhost:5173/")
    demo._rate_events.clear()
    with isolated_db.Session.begin() as session:
        for i in range(5):
            session.add(Alumni(id=UUID(int=900 + i), first_name="PRIVATE_PEER", last_name="Example",
                               email=f"private-{i}@example.org", cohort="2022", city="New York",
                               is_demo=True))
        session.add_all([
            Job(board_token="example", greenhouse_job_id="1", title="Software Engineer",
                company="Example", location="New York", absolute_url="https://example.org/jobs/1"),
            Job(board_token="example", greenhouse_job_id="2", title="Data Analyst",
                company="Example", location="Chicago", absolute_url="https://example.org/jobs/2"),
        ])
    app = FastAPI()
    app.include_router(router.router)
    return TestClient(app)


def payload(**overrides):
    return {"synthetic": True, "first_name": "Jordan", "city": "New York", "cohort": "2022",
            "skills": ["Python"], "roles": [{"title": "Software Engineer", "is_current": True,
                                            "start_date": "2025-01", "end_date": ""}], **overrides}


def test_two_profiles_and_live_profile_update_use_only_caller_supplied_fields(isolated_db, monkeypatch):
    from work.database.models import NewsletterDelivery, NewsletterSubscription, ResumeUpload

    api = client(isolated_db, monkeypatch)
    first = api.post("/newsletter/demo", json=payload())
    second = api.post("/newsletter/demo", json=payload(first_name="Taylor", city="Chicago", cohort="2024",
        skills=["SQL"], roles=[{"title": "Data Analyst", "is_current": True, "start_date": "2026", "end_date": ""}]))
    updated = api.post("/newsletter/demo", json=payload(first_name="Jordan", city="Chicago",
        roles=[{"title": "Data Analyst", "is_current": True, "start_date": "2026", "end_date": ""}]))
    assert first.status_code == second.status_code == updated.status_code == 200
    assert first.json()["content"]["first_name"] == "Jordan"
    assert second.json()["content"]["first_name"] == "Taylor"
    assert first.json()["content"]["jobs"][0]["title"] == "Software Engineer"
    assert second.json()["content"]["jobs"][0]["title"] == "Data Analyst"
    assert updated.json()["content"]["jobs"][0]["title"] == "Data Analyst"
    assert "5 alumni on record" in first.json()["content"]["cohort_message"]
    assert "not enough shareable data" in second.json()["content"]["cohort_message"]
    for response in (first, second, updated):
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["demo_only"] is True
        assert "PRIVATE_PEER" not in response.text and "private-" not in response.text
    with isolated_db.Session() as session:
        assert session.scalar(select(func.count()).select_from(ResumeUpload)) == 0
        assert session.scalar(select(func.count()).select_from(NewsletterSubscription)) == 0
        assert session.scalar(select(func.count()).select_from(NewsletterDelivery)) == 0


def test_missing_fields_and_no_role_have_safe_empty_state(isolated_db, monkeypatch):
    api = client(isolated_db, monkeypatch)
    response = api.post("/newsletter/demo", json={"synthetic": True})
    assert response.status_code == 200
    content = response.json()["content"]
    assert content["first_name"] == "there" and content["jobs"] == []
    assert "Add your TKH cohort" in content["cohort_message"]


def test_extra_identity_fields_false_assertion_and_oversized_input_are_rejected(isolated_db, monkeypatch):
    api = client(isolated_db, monkeypatch)
    for forbidden in ({"id": str(UUID(int=900))}, {"email": "private@example.org"},
                      {"salary_min": 100000}, {"synthetic": False}):
        assert api.post("/newsletter/demo", json=payload(**forbidden)).status_code == 422
    assert api.post("/newsletter/demo", json=payload(first_name="x" * 9000)).status_code == 413
    assert api.get("/newsletter/current").status_code == 401


def test_rate_limit_and_current_role_priority(isolated_db, monkeypatch):
    api = client(isolated_db, monkeypatch)
    monkeypatch.setattr(demo, "RATE_LIMIT", 1)
    assert api.post("/newsletter/demo", json=payload()).status_code == 200
    assert api.post("/newsletter/demo", json=payload()).status_code == 429
    demo._rate_events.clear()
    profile = demo.DemoProfile.model_validate(payload(roles=[
        {"title": "Software Engineer", "is_current": False, "start_date": "2020", "end_date": "2021"},
        {"title": "Data Analyst", "is_current": True, "start_date": "2026", "end_date": ""},
    ]))
    assert demo._matching(profile).latest_title == "Data Analyst"
