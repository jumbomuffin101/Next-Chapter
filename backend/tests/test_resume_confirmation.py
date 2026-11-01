import copy
import io
import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from backend.app.parsing.router import router
from backend.app.analytics.router import router as analytics_router
from backend.app.profiles.router import router as profiles_router
from work.database.crud import parse_date, save_confirmed_resume
from work.database.models import Alumni, Certification, Education, ResumeUpload, SalaryRecord, Skill, WorkExperience


@pytest.fixture
def person(isolated_db):
    identifier = uuid.UUID(int=101)
    with isolated_db.Session.begin() as session:
        session.add(Alumni(id=identifier, first_name="Before", last_name="Example",
                           email="before@example.com", cohort="2022", graduation_year=2022,
                           updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc)))
    return identifier


@pytest.fixture
def emails_hook(monkeypatch):
    # The automated-email step uses Postgres (covered in test_integration.py); here we only record that confirm calls it.
    calls = []
    monkeypatch.setattr("backend.app.parsing.router.on_resume_confirmed", calls.append)
    return calls


@pytest.fixture
def client(isolated_db, emails_hook):
    app = FastAPI()
    app.include_router(router)
    app.include_router(analytics_router)
    app.include_router(profiles_router)
    with TestClient(app) as api:
        yield api


@pytest.fixture
def resume():
    return {
        "full_name": "Test Person", "email": "test@example.com", "phone": None, "location": "Newark, NJ",
        "work_experience": [{"employer": "Demo Company", "title": "Engineer", "location": "New York, NY",
                             "start_date": "2024-06-15", "end_date": None, "is_current": True}],
        "education": [{"school": "Demo College", "degree": "BS", "field_of_study": "Computing",
                       "start_date": "2018", "end_date": "2022-05"}],
        "skills": ["Python", "python"], "certifications": ["Demo Certificate", "demo certificate"],
        "warnings": ["User reviewed"],
    }


@pytest.mark.parametrize("value,expected", [
    ("2024", date(2024, 1, 1)), ("2024-02", date(2024, 2, 1)),
    ("2024-02-29", date(2024, 2, 29)), (None, None), ("", None),
])
def test_date_precision(value, expected):
    assert parse_date(value) == expected


@pytest.mark.parametrize("value", ["2023-02-29", "2024-13", "bad", "2024-1", "0000", "2024-01-00"])
def test_invalid_dates_rejected(value):
    with pytest.raises(ValueError):
        parse_date(value)


def test_atomic_confirm_preserves_history_and_response(client, isolated_db, person, resume, emails_hook):
    with isolated_db.Session.begin() as session:
        session.add(WorkExperience(alumni_id=person, employer="Prior Company", title="Intern",
                                   start_date=date(2020, 1, 1), end_date=date(2021, 1, 1), is_current=False))
    response = client.post(f"/resume/confirm/{person}", json={
        "resume": resume, "salary_min": 70000, "salary_max": 90000, "file_name": "reviewed.pdf",
    })
    assert response.status_code == 200
    assert response.json() == {"profile_id": str(person), "roles_added": 1, "roles_updated": 0, "salary_saved": True}
    assert [str(i) for i in emails_hook] == [str(person)]  # the automated-email step runs after a successful save
    with isolated_db.Session() as session:
        alumni = session.get(Alumni, person)
        assert (alumni.cohort, alumni.graduation_year) == ("2022", 2022)
        assert alumni.email == "test@example.com" and alumni.updated_at.year > 2020
        roles = session.scalars(select(WorkExperience).order_by(WorkExperience.start_date)).all()
        assert len(roles) == 2 and roles[-1].start_date == date(2024, 6, 15)
        assert session.scalar(select(func.count()).select_from(Skill)) == 1
        assert session.scalar(select(func.count()).select_from(Certification)) == 1
        assert session.scalar(select(Education)).graduation_year == 2022
        snapshot = session.scalar(select(ResumeUpload))
        assert snapshot.confirmed and snapshot.file_name == "reviewed.pdf"
        assert snapshot.parsed_data["warnings"] == ["User reviewed"]
        assert session.scalar(select(SalaryRecord)).source == "self_reported"


def test_reconfirmation_and_duplicate_items_do_not_duplicate_jobs(client, isolated_db, person, resume):
    resume["work_experience"][0]["start_date"] = "2024-06"
    duplicate = copy.deepcopy(resume["work_experience"][0])
    duplicate.update(employer="demo company", title="engineer")
    resume["work_experience"].append(duplicate)
    body = {"resume": resume, "salary_min": 70000, "salary_max": 90000}
    assert client.post(f"/resume/confirm/{person}", json=body).json()["roles_added"] == 1
    body.update(salary_min=80000, salary_max=100000)
    result = client.post(f"/resume/confirm/{person}", json=body).json()
    assert result["roles_added"] == 0 and result["roles_updated"] == 1
    with isolated_db.Session() as session:
        assert session.scalar(select(func.count()).select_from(WorkExperience)) == 1
        assert session.scalar(select(func.count()).select_from(ResumeUpload)) == 2
        assert session.scalar(select(func.count()).select_from(SalaryRecord)) == 1
        assert session.scalar(select(SalaryRecord)).salary_min == 80000
    body.pop("salary_min")
    body.pop("salary_max")
    assert client.post(f"/resume/confirm/{person}", json=body).json()["salary_saved"] is False
    with isolated_db.Session() as session:
        assert session.scalar(select(SalaryRecord)).salary_min == 80000


def test_snapshot_failure_rolls_back_every_change(isolated_db, person, resume):
    def fail_snapshot(connection, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO resume_uploads"):
            raise RuntimeError("Synthetic snapshot failure")
    event.listen(isolated_db.engine, "before_cursor_execute", fail_snapshot)
    try:
        with pytest.raises(RuntimeError, match="Synthetic snapshot"):
            save_confirmed_resume(str(person), resume, salary_min=1, salary_max=2)
    finally:
        event.remove(isolated_db.engine, "before_cursor_execute", fail_snapshot)
    with isolated_db.Session() as session:
        assert session.get(Alumni, person).email == "before@example.com"
        for model in (WorkExperience, SalaryRecord, ResumeUpload, Skill, Education, Certification):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_existing_whitespace_and_case_do_not_duplicate_jobs(isolated_db, person, resume):
    with isolated_db.Session.begin() as session:
        session.add(WorkExperience(alumni_id=person, employer=" Demo Company ", title=" ENGINEER ",
                                   start_date=date(2024, 6, 15), is_current=True))
        session.add(Skill(alumni_id=person, name=" Python "))
    result = save_confirmed_resume(str(person), resume)
    assert result["work_experience_added"] == 0 and result["work_experience_updated"] == 1
    with isolated_db.Session() as session:
        assert session.scalar(select(func.count()).select_from(WorkExperience)) == 1
        assert session.scalar(select(func.count()).select_from(Skill)) == 1


def test_salary_updates_preserve_other_days_and_sources(isolated_db, person, resume):
    with isolated_db.Session.begin() as session:
        session.add(SalaryRecord(alumni_id=person, salary_min=40000, salary_max=50000,
                                 source="self_reported", effective_date=date(2020, 1, 1)))
        session.add(SalaryRecord(alumni_id=person, salary_min=50000, salary_max=60000,
                                 source="estimated", effective_date=datetime.now(timezone.utc).date()))
    save_confirmed_resume(str(person), resume, salary_min=70000, salary_max=90000)
    with isolated_db.Session() as session:
        salaries = session.scalars(select(SalaryRecord)).all()
        assert len(salaries) == 3
        assert {(s.source, int(s.salary_min)) for s in salaries} == {
            ("self_reported", 40000), ("estimated", 50000), ("self_reported", 70000),
        }


def test_email_conflicts_are_case_insensitive(client, isolated_db, person, resume):
    with isolated_db.Session.begin() as session:
        session.add(Alumni(first_name="Other", last_name="Person", email="TEST@EXAMPLE.COM"))
    response = client.post(f"/resume/confirm/{person}", json={"resume": resume})
    assert response.status_code == 422
    with isolated_db.Session() as session:
        assert session.get(Alumni, person).email == "before@example.com"
        assert session.scalar(select(func.count()).select_from(ResumeUpload)) == 0


@pytest.mark.parametrize("changes", [
    {"full_name": ""}, {"email": None}, {"email": "invalid"},
    {"phone": "x" * 31}, {"skills": [""]},
    {"work_experience": [{"employer": "", "title": "Engineer"}]},
    {"work_experience": [{"employer": "Company", "title": ""}]},
    {"work_experience": [{"employer": "C", "title": "T", "start_date": "2024", "end_date": "2023"}]},
    {"work_experience": [{"employer": "C", "title": "T", "end_date": "2024", "is_current": True}]},
    {"work_experience": [{"employer": "C", "title": "T", "start_date": "9999", "is_current": True}]},
    {"education": [{"school": ""}]},
])
def test_invalid_confirmation_does_not_write(client, isolated_db, person, resume, changes):
    resume.update(changes)
    assert client.post(f"/resume/confirm/{person}", json={"resume": resume}).status_code == 422
    with isolated_db.Session() as session:
        assert session.scalar(select(func.count()).select_from(ResumeUpload)) == 0
        assert session.get(Alumni, person).email == "before@example.com"


@pytest.mark.parametrize("salary", [
    {"salary_min": 1}, {"salary_max": 1}, {"salary_min": -1, "salary_max": 2},
    {"salary_min": 3, "salary_max": 2}, {"salary_min": True, "salary_max": 2},
    {"salary_min": 1.5, "salary_max": 2}, {"salary_min": 1, "salary_max": 10_000_000_000},
])
def test_invalid_salary_returns_422(client, person, resume, salary):
    assert client.post(f"/resume/confirm/{person}", json={"resume": resume, **salary}).status_code == 422


def test_missing_profile_and_empty_resume(client, resume):
    assert client.post(f"/resume/confirm/{uuid.UUID(int=999)}", json={"resume": resume}).status_code == 404
    assert client.post(f"/resume/confirm/{uuid.UUID(int=999)}", json={"resume": {}}).status_code == 422


def test_legacy_helper_result_and_city_fallback(isolated_db, person, resume):
    resume["location"] = None
    result = save_confirmed_resume(str(person), resume)
    assert result["success"] and result["resume_confirmed"] and result["alumni_id"] == str(person)
    with isolated_db.Session() as session:
        assert session.get(Alumni, person).city == "New York, NY"


def test_upload_review_confirm_and_dashboard_flow(client, isolated_db, person):
    from reportlab.pdfgen import canvas
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    text = ["Test Person", "test@example.com | Newark, NJ", "EXPERIENCE",
            "Software Engineer | Demo Company | Newark, NJ  Jan 2024 - Present",
            "Built and maintained useful software for community programs", "SKILLS", "Python, SQL"]
    for index, line in enumerate(text):
        pdf.drawString(30, 750 - index * 20, line)
    pdf.save()
    response = client.post("/resume/parse", files={"file": ("synthetic.pdf", buffer.getvalue(), "application/pdf")})
    assert response.status_code == 200
    parsed = response.json()
    assert parsed["full_name"] == "Test Person"
    with isolated_db.Session() as session:
        assert session.scalar(select(func.count()).select_from(ResumeUpload)) == 0
    confirmed = client.post(f"/resume/confirm/{person}", json={"resume": parsed})
    assert confirmed.status_code == 200 and confirmed.json()["roles_added"] == 1
    summary = client.get("/analytics/summary").json()
    assert summary["alumni_with_confirmed_resumes"] == summary["alumni_with_current_roles"] == 1
    assert client.get("/profiles/outreach").json()["total"] == 0


def test_upload_error_paths_do_not_write(client, isolated_db):
    assert client.post("/resume/parse", files={"file": ("bad.pdf", b"not a PDF", "application/pdf")}).status_code == 422
    assert client.post("/resume/parse", files={"file": ("bad.txt", b"text", "text/plain")}).status_code == 400
    assert client.post("/resume/parse", files={"file": ("big.pdf", b"x" * (5 * 1024 * 1024 + 1), "application/pdf")}).status_code == 413
    with isolated_db.Session() as session:
        assert session.scalar(select(func.count()).select_from(ResumeUpload)) == 0


def test_replace_saves_exactly_what_the_editor_sent(client, isolated_db, person, resume):
    """Profile editor: removed and renamed entries go away, cleared fields are cleared."""
    resume["phone"] = "555-0100"
    resume["skills"] = ["Python", "SQL"]
    resume["certifications"] = ["Demo Certificate", "Other Cert"]
    resume["work_experience"].append({"employer": "Old Co", "title": "Intern", "start_date": "2020-01",
                                      "end_date": "2021-01", "is_current": False, "description": "Old notes"})
    assert client.post(f"/resume/confirm/{person}", json={"resume": resume}).status_code == 200

    edited = copy.deepcopy(resume)
    edited["phone"] = None
    edited["skills"] = ["SQL"]
    edited["certifications"] = []
    edited["education"] = []
    edited["work_experience"] = [dict(resume["work_experience"][0], title="Senior Engineer", description=None)]
    assert client.post(f"/resume/confirm/{person}", json={"resume": edited, "replace": True}).status_code == 200
    with isolated_db.Session() as session:
        assert session.get(Alumni, person).phone is None
        assert [r.title for r in session.scalars(select(WorkExperience))] == ["Senior Engineer"]
        assert [s.name for s in session.scalars(select(Skill))] == ["SQL"]
        assert session.scalar(select(func.count()).select_from(Certification)) == 0
        assert session.scalar(select(func.count()).select_from(Education)) == 0


def test_without_replace_a_resume_still_merges(client, isolated_db, person, resume):
    assert client.post(f"/resume/confirm/{person}", json={"resume": resume}).status_code == 200
    partial = dict(resume, skills=[], work_experience=[], education=[], certifications=[])
    assert client.post(f"/resume/confirm/{person}", json={"resume": partial}).status_code == 200
    with isolated_db.Session() as session:
        assert session.scalar(select(func.count()).select_from(WorkExperience)) == 1
        assert session.scalar(select(func.count()).select_from(Skill)) == 1


def test_education_start_year_is_saved_and_editable(client, isolated_db, person, resume):
    assert client.post(f"/resume/confirm/{person}", json={"resume": resume}).status_code == 200
    with isolated_db.Session() as session:
        assert (session.scalar(select(Education)).start_year, session.scalar(select(Education)).graduation_year) == (2018, 2022)
    resume["education"][0]["start_date"] = "2019"
    assert client.post(f"/resume/confirm/{person}", json={"resume": resume, "replace": True}).status_code == 200
    with isolated_db.Session() as session:
        assert session.scalar(select(Education)).start_year == 2019


def test_each_role_salary_is_a_chart_entry_at_the_role_start(client, isolated_db, person, resume):
    resume["work_experience"][0].update(salary_min=90000, salary_max=100000)  # current role, started 2024-06-15
    resume["work_experience"].append({"employer": "Old Co", "title": "Intern", "start_date": "2021-03", "end_date": "2022-01",
                                      "is_current": False, "salary_min": 40000, "salary_max": 45000})
    assert client.post(f"/resume/confirm/{person}", json={"resume": resume}).status_code == 200
    with isolated_db.Session() as session:
        jobs = {j.title: j.id for j in session.scalars(select(WorkExperience))}
        pay = {(s.effective_date, int(s.salary_min), int(s.salary_max), s.work_experience_id) for s in session.scalars(select(SalaryRecord))}
    assert pay == {(date(2024, 6, 1), 90000, 100000, jobs["Engineer"]), (date(2021, 3, 1), 40000, 45000, jobs["Intern"])}

    # saving again with a new range updates the same entry; "Not set" (replace mode) removes that role's entry
    resume["work_experience"][0].update(salary_min=95000, salary_max=105000)
    resume["work_experience"][1].update(salary_min=None, salary_max=None)
    assert client.post(f"/resume/confirm/{person}", json={"resume": resume, "replace": True}).status_code == 200
    with isolated_db.Session() as session:
        rows = [(s.effective_date, int(s.salary_min)) for s in session.scalars(select(SalaryRecord))]
    assert rows == [(date(2024, 6, 1), 95000)]


def test_a_role_salary_reuses_an_unlinked_entry_in_its_start_month(client, isolated_db, person, resume):
    with isolated_db.Session.begin() as session:
        session.add(SalaryRecord(alumni_id=person, salary_min=80000, salary_max=85000, source="self_reported", effective_date=date(2024, 6, 20)))
    resume["work_experience"][0].update(salary_min=90000, salary_max=100000)
    assert client.post(f"/resume/confirm/{person}", json={"resume": resume}).status_code == 200
    with isolated_db.Session() as session:
        rows = session.scalars(select(SalaryRecord)).all()
        assert len(rows) == 1 and int(rows[0].salary_min) == 90000 and rows[0].work_experience_id is not None


@pytest.mark.parametrize("low,high", [(90000, None), (None, 5), (100, 50), (0, 10)])
def test_role_salary_needs_a_sensible_range(client, isolated_db, person, resume, low, high):
    resume["work_experience"][0].update(salary_min=low, salary_max=high)
    assert client.post(f"/resume/confirm/{person}", json={"resume": resume}).status_code == 422
