import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.analytics.router import router as analytics_router
from backend.app.profiles.router import router as profiles_router
from work.database.models import Alumni, ResumeUpload, WorkExperience


@pytest.fixture
def client(isolated_db):
    app = FastAPI()
    app.include_router(analytics_router)
    app.include_router(profiles_router)
    with TestClient(app) as api:
        yield api


@pytest.fixture
def population(isolated_db):
    now = datetime.now(timezone.utc)
    ids = [uuid.uuid4() for _ in range(5)]
    with isolated_db.Session.begin() as session:
        for index, (cohort, city) in enumerate([
            ("2022", "New York"), (None, None), (" ", " "),
            ("2022", "New York"), ("2023", "Newark"),
        ]):
            session.add(Alumni(id=ids[index], first_name=f"Person{index}", last_name="Example",
                               email=f"person{index}@example.com", cohort=cohort, city=city,
                               is_demo=index >= 3, updated_at=now))
        session.flush()
        for person, start, end, current in [
            (0, "2023-01-01", None, True), (0, "2024-01-01", None, True),
            (1, "2020-01-01", "2021-01-01", False),
            (2, "2020-01-01", "2021-01-01", True),
            (3, None, None, True), (3, "9999-01-01", None, True),
        ]:
            session.add(WorkExperience(alumni_id=ids[person], employer="Demo Company", title="Engineer",
                                       start_date=date.fromisoformat(start) if start else None,
                                       end_date=date.fromisoformat(end) if end else None, is_current=current))
        for person, days, confirmed in [(0, 20, True), (0, 500, True), (1, 1, False),
                                         (3, 400, True), (3, 1, False)]:
            session.add(ResumeUpload(alumni_id=ids[person], file_name="synthetic.pdf",
                                     uploaded_at=now - timedelta(days=days), confirmed=confirmed))
    return ids


def test_analytics_distinct_counts_and_demo_split(client, population):
    response = client.get("/analytics/summary")
    assert response.status_code == 200
    body = response.json()
    assert {key: body[key] for key in body["real"]} == {
        "total_alumni": 5, "alumni_with_current_roles": 2,
        "alumni_with_confirmed_resumes": 2, "total_career_history_records": 6,
    }
    assert body["real"] == {
        "total_alumni": 3, "alumni_with_current_roles": 1,
        "alumni_with_confirmed_resumes": 1, "total_career_history_records": 4,
    }
    assert body["demo"] == {
        "total_alumni": 2, "alumni_with_current_roles": 1,
        "alumni_with_confirmed_resumes": 1, "total_career_history_records": 2,
    }
    for dimension in ("cohort", "city"):
        groups = body[f"by_{dimension}"]
        assert sum(group["total_alumni"] for group in groups) == 5
        missing = next(group for group in groups if group[dimension] is None)
        assert missing["total_alumni"] == missing["real"]["total_alumni"] == 2
        assert sum(group["total_career_history_records"] for group in groups) == 6
    assert "synthetic" in body["data_note"] and "verified" in body["data_note"]


def test_analytics_can_exclude_demo(client, population):
    body = client.get("/analytics/summary?include_demo=false").json()
    assert body["total_alumni"] == 3
    assert body["real"]["total_alumni"] == 3
    assert all(value == 0 for value in body["demo"].values())
    assert sum(row["total_alumni"] for row in body["by_city"]) == 3


def test_empty_analytics_and_outreach(client):
    body = client.get("/analytics/summary").json()
    assert body["total_alumni"] == body["alumni_with_current_roles"] == 0
    assert body["alumni_with_confirmed_resumes"] == body["total_career_history_records"] == 0
    assert body["by_city"] == body["by_cohort"] == []
    assert all(value == 0 for value in body["demo"].values())
    assert client.get("/profiles/outreach").json()["items"] == []


def test_outreach_uses_latest_confirmed_snapshot(client, population):
    response = client.get("/profiles/outreach")
    assert response.status_code == 200  # Static path must not be parsed as a UUID.
    body = response.json()
    assert body["total"] == 4
    rows = {row["id"]: row for row in body["items"]}
    assert str(population[0]) not in rows
    assert rows[str(population[1])]["outreach_reason"] == "No confirmed resume update"
    assert rows[str(population[2])]["last_confirmed_at"] is None
    assert rows[str(population[3])]["outreach_reason"] == "No confirmed resume update in the last 180 days"
    assert all(row["needs_outreach"] for row in rows.values())


def test_outreach_pagination_demo_filter_and_recent_records(client, population):
    first = client.get("/profiles/outreach?limit=1").json()
    second = client.get("/profiles/outreach?limit=1&offset=1").json()
    assert first["total"] == second["total"] == 4
    assert first["items"][0]["id"] != second["items"][0]["id"]
    empty = client.get("/profiles/outreach?offset=999").json()
    assert empty["items"] == [] and empty["total"] == 4
    real = client.get("/profiles/outreach?include_demo=false").json()
    assert real["total"] == 2 and all(not row["is_demo"] for row in real["items"])
    all_rows = client.get("/profiles/outreach?only_needs_outreach=false").json()
    assert all_rows["total"] == 5
    recent = next(row for row in all_rows["items"] if row["id"] == str(population[0]))
    assert recent["needs_outreach"] is False and recent["outreach_reason"] is None
    assert client.get("/profiles/outreach?stale_days=500").json()["total"] == 3


@pytest.mark.parametrize("query", ["stale_days=0", "stale_days=3651", "offset=-1", "limit=0", "limit=101"])
def test_outreach_validates_parameters(client, query):
    assert client.get("/profiles/outreach?" + query).status_code == 422
