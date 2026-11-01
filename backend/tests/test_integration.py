"""End-to-end flow against a REAL Postgres. Skipped unless TEST_DATABASE_URL is set.

    TEST_DATABASE_URL=postgresql://user@localhost/tkh_test pytest tests/test_integration.py

WARNING: this TRUNCATES tables in that database. Never point it at shared/real data.
Greenhouse HTTP is mocked here; use the live script (scripts/live_check.py) for the real API.
"""
import io
import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")

from tests.test_rule_parser import RESUME_A  # noqa: E402

UPDATED_RESUME = RESUME_A.replace(
    "EXPERIENCE\n",
    "EXPERIENCE\nSenior Systems Engineer | NASA | Houston, TX                 Jan 2026 – Present\n• Led a team of 4 engineers\n",
).replace("Systems Engineer | NASA | Houston, TX                      Mar 2024 – Present",
          "Systems Engineer | NASA | Houston, TX                      Mar 2024 – Dec 2025")


def make_pdf(text: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 760
    for line in text.splitlines():
        c.drawString(40, y, line.replace("•", "-"))
        y -= 13
    c.save()
    return buf.getvalue()


class FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def json(self):
        return self._p


def gh_job(i, title, loc, content=""):
    return {"id": i, "title": title, "location": {"name": loc}, "absolute_url": f"https://boards.greenhouse.io/acme/jobs/{i}",
            "updated_at": "2026-10-01T12:00:00-04:00", "company_name": "Acme", "content": content}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    from fastapi.testclient import TestClient

    from app.db import get_conn
    from app.init_db import init_db
    from app.main import app

    init_db()
    with get_conn() as conn:
        conn.execute("TRUNCATE alumni, jobs, alumni_roster, app_settings CASCADE")
        conn.commit()
    return TestClient(app)


def upload_and_confirm(client, pid, text, **salary):
    r = client.post("/resume/parse", files={"file": ("r.pdf", make_pdf(text), "application/pdf")})
    assert r.status_code == 200, r.text
    parsed = r.json()
    c = client.post(f"/resume/confirm/{pid}", json={"resume": parsed, **salary})
    assert c.status_code == 200, c.text
    return c.json()


def test_full_flow(client, monkeypatch):
    # profile ("login")
    pid = client.post("/profiles", json={"email": "Jane.Doe@email.com"}).json()["id"]
    assert client.post("/profiles", json={"email": "jane.doe@email.com"}).json()["id"] == pid  # idempotent

    # first upload + self-reported salary
    res = upload_and_confirm(client, pid, RESUME_A, salary_min=95000, salary_max=115000)
    assert res["roles_added"] == 2 and res["salary_saved"]
    prof = client.get(f"/profiles/{pid}").json()
    assert prof["full_name"] == "Jane Doe" and prof["city"] == "Chicago, IL"
    assert (prof["salary_min"], prof["salary_source"]) == (95000, "self_reported")
    assert [w["title"] for w in prof["work_experiences"]] == ["Systems Engineer", "Help Desk Technician"]
    assert "Python" in prof["skills"] and prof["education"][0]["school"] == "Harold Washington College"

    # re-confirming the same resume must not duplicate anything
    again = upload_and_confirm(client, pid, RESUME_A)
    assert again["roles_added"] == 0 and again["roles_updated"] == 2

    # promotion: updated resume adds a new current role, closes the old one, keeps history
    upload_and_confirm(client, pid, UPDATED_RESUME)
    roles = client.get(f"/profiles/{pid}").json()["work_experiences"]
    assert [w["title"] for w in roles] == ["Senior Systems Engineer", "Systems Engineer", "Help Desk Technician"]
    assert roles[0]["is_current"] and not roles[1]["is_current"]

    # Greenhouse poll (mocked)
    import app.jobs.greenhouse as gh

    monkeypatch.setattr(gh, "BOARD_TOKENS", ["acme"])
    jobs = [
        gh_job(1, "Systems Engineer", "Chicago, IL", "Pay range: $100,000 - $130,000 per year"),
        gh_job(2, "Account Executive", "Austin, TX"),
        gh_job(4, "Systems Engineer", "Dublin, Ireland"),
        gh_job(3, "Help Desk Technician", "Remote"),
    ]
    monkeypatch.setattr(gh.httpx, "get", lambda *a, **k: FakeResp({"jobs": jobs}))
    assert client.post("/jobs/refresh", headers=admin_headers(client)).json()["jobs_upserted"] == 4

    # salary parsed from posting text; matching ranks relevant role first with an explanation
    matches = client.get(f"/users/{pid}/job-matches").json()["matches"]
    assert matches and matches[0]["title"] == "Systems Engineer"
    assert (matches[0]["salary_min"], matches[0]["salary_max"]) == (100000, 130000)
    assert "Similar role" in matches[0]["why_matched"] and "Salary in range" in matches[0]["why_matched"]
    assert all(m["title"] != "Account Executive" for m in matches)
    assert len(matches) == 1  # same-title job in Dublin is excluded by location
    assert matches[0]["apply_url"].startswith("https://")

    # a posting that disappears from the board is removed on the next refresh
    monkeypatch.setattr(gh.httpx, "get", lambda *a, **k: FakeResp({"jobs": jobs[:1]}))
    client.post("/jobs/refresh", headers=admin_headers(client))
    titles = [m["title"] for m in client.get(f"/users/{pid}/job-matches").json()["matches"]]
    assert titles == ["Systems Engineer"]


def test_error_paths(client):
    import uuid

    valid = {"full_name": "Ada Lovelace", "email": "ada@example.com"}
    assert client.post(f"/resume/confirm/{uuid.uuid4()}", json={"resume": valid}).status_code == 404
    assert client.post(f"/resume/confirm/{uuid.uuid4()}", json={"resume": {}}).status_code == 422  # name/email required
    assert client.post("/resume/confirm/999", json={"resume": {}}).status_code == 422  # ids are UUIDs
    pid = client.post("/profiles", json={"email": "x@y.com"}).json()["id"]
    assert client.get(f"/users/{pid}/job-matches").status_code == 404  # no resume yet
    bad = client.post(f"/resume/confirm/{pid}", json={"resume": {}, "salary_min": 9, "salary_max": 1})
    assert bad.status_code == 422
    assert client.post("/resume/parse", files={"file": ("r.txt", b"hello", "text/plain")}).status_code == 400


def test_one_failing_board_does_not_break_refresh(client, monkeypatch):
    import app.jobs.greenhouse as gh

    monkeypatch.setattr(gh, "BOARD_TOKENS", ["good", "bad"])

    def fake_get(url, **kw):
        if "/bad/" in url:
            raise gh.httpx.ConnectError("boom")
        return FakeResp({"jobs": [gh_job(1, "Software Engineer", "Remote")]})

    monkeypatch.setattr(gh.httpx, "get", fake_get)
    out = client.post("/jobs/refresh", headers=admin_headers(client)).json()
    assert out["jobs_upserted"] == 1 and out["per_board"] == {"good": 1} and "bad" in out["failed"]


NO_CITY_RESUME = """Test Person
test@example.com
Experience
Acme Corp, Hoboken, NJ
Course Assistant                                    Sep 2026 - Present
- Graded assignments
Remote Co  Remote
Software Engineering Intern                         Oct 2025 - May 2026
- Built APIs
"""


def test_city_prefilled_from_latest_onsite_role_without_overwriting(client):
    pid = client.post("/profiles", json={"email": "nocity@example.com"}).json()["id"]
    upload_and_confirm(client, pid, NO_CITY_RESUME)
    assert client.get(f"/profiles/{pid}").json()["city"] == "Hoboken, NJ"

    # a city the user already has is never replaced by a guess
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute("UPDATE alumni SET city = 'Newark, NJ' WHERE id = %s", (pid,))
        conn.commit()
    upload_and_confirm(client, pid, NO_CITY_RESUME)
    assert client.get(f"/profiles/{pid}").json()["city"] == "Newark, NJ"


def test_match_profile_uses_most_recent_classifiable_title(client):
    from app.jobs.router import load_match_profile

    pid = client.post("/profiles", json={"email": "latest@example.com"}).json()["id"]
    upload_and_confirm(client, pid, NO_CITY_RESUME)
    # latest role is "Course Assistant" (no known family); the software internship decides matching
    assert load_match_profile(pid).latest_title == "Software Engineering Intern"


def test_shared_schema_details(client):
    """Salary history, confirmed-resume snapshot, de-duplication and over-long values."""
    from app.db import get_conn

    pid = client.post("/profiles", json={"email": "schema@example.com"}).json()["id"]
    upload_and_confirm(client, pid, NO_CITY_RESUME, salary_min=60000, salary_max=70000)
    upload_and_confirm(client, pid, NO_CITY_RESUME, salary_min=65000, salary_max=75000)  # same day: updated
    with get_conn() as conn:
        assert conn.execute("SELECT count(*) FROM salary_records WHERE alumni_id=%s", (pid,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM resume_uploads WHERE alumni_id=%s AND confirmed", (pid,)).fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM work_experience WHERE alumni_id=%s", (pid,)).fetchone()[0] == 2
    prof = client.get(f"/profiles/{pid}").json()
    assert (prof["salary_min"], prof["salary_max"], prof["salary_source"]) == (65000, 75000, "self_reported")
    assert prof["last_updated_at"]

    # values longer than the shared VARCHAR limits are rejected with a clear 422, never a 500 or a silent cut
    long = {"full_name": "A" * 300 + " " + "B" * 300, "phone": "9" * 80, "location": "C" * 300,
            "work_experience": [{"employer": "E" * 400, "title": "T" * 400, "location": "L" * 400,
                                 "start_date": "2024-01"}],
            "skills": ["S" * 300], "certifications": ["K" * 400]}
    too_long = client.post(f"/resume/confirm/{pid}", json={"resume": long})
    assert too_long.status_code == 422 and "exceeds" in too_long.json()["detail"]
    assert client.get(f"/profiles/{pid}").json()["city"] == "Hoboken, NJ"  # the failed save changed nothing (atomic)


def test_empty_strings_from_the_frontend_count_as_missing(client):
    """The review screen sends '' for blank fields; that must not blank the city or duplicate rows."""
    pid = client.post("/profiles", json={"email": "blank@example.com"}).json()["id"]
    body = {"full_name": "Blank Test", "email": "blank@example.com", "phone": "", "location": "",
            "education": [{"school": "State College", "degree": "", "field_of_study": "",
                           "start_date": "", "end_date": "2022-05"}],
            "work_experience": [{"employer": "Acme", "title": "Software Engineer", "location": "Hoboken, NJ",
                                 "start_date": "2024-01", "end_date": "", "description": "", "is_current": True}],
            "skills": ["Python"], "certifications": [], "warnings": []}
    for _ in range(2):  # re-confirming must not duplicate education
        assert client.post(f"/resume/confirm/{pid}", json={"resume": body}).status_code == 200
    prof = client.get(f"/profiles/{pid}").json()
    assert prof["city"] == "Hoboken, NJ"  # '' location did not erase the prefill
    assert len(prof["education"]) == 1 and prof["education"][0]["graduation_year"] == 2022
    assert prof["work_experiences"][0]["description"] is None


def test_admin_overview_reflects_real_rows(client):
    """Two alumni, one with a confirmed resume + salary: the admin endpoint sees both."""
    from app.db import get_conn

    full = client.post("/profiles", json={"email": "full@example.com"}).json()["id"]
    client.post("/profiles", json={"email": "empty@example.com"})
    # confirm stores the resume's email on the account, so keep it equal to the login email
    upload_and_confirm(client, full, NO_CITY_RESUME.replace("test@example.com", "full@example.com"),
                       salary_min=60000, salary_max=80000)
    with get_conn() as conn:
        conn.execute("UPDATE alumni SET cohort = '2024', graduation_year = 2024 WHERE id = %s", (full,))
        conn.commit()

    out = client.get("/admin/overview", headers=admin_headers(client)).json()
    assert out["totals"]["size"] == 2
    assert out["current_cohort"]["name"] == "2024" and out["current_cohort"]["size"] == 1
    assert out["current_cohort"]["avg_salary"] == 70000
    assert {l["city"] for l in out["locations"]} == {"Hoboken"}  # the empty profile has no city
    flagged = {o["email"]: o["reasons"] for o in out["outreach"]}
    assert "empty@example.com" in flagged and "No current job" in flagged["empty@example.com"]
    assert "full@example.com" in flagged and "Missing salary" not in flagged["full@example.com"]


def admin_headers(client):
    token = client.post("/auth/admin/login", json={"email": "admin@tkh.org", "password": "tkh-demo-2026"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_endpoints_need_the_admin_token(client):
    for path in ("/admin/overview", "/analytics/summary"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer nope"}).status_code == 401
        assert client.get(path, headers=admin_headers(client)).status_code == 200
    bad = client.post("/auth/admin/login", json={"email": "admin@tkh.org", "password": "wrong"})
    assert bad.status_code == 401 and "Wrong email or password" in bad.json()["detail"]
    assert client.post("/auth/admin/login", json={"email": "other@tkh.org", "password": "tkh-demo-2026"}).status_code == 401


def test_alumni_sign_up_sign_in_and_onboarding_flag(client):
    # unknown email cannot sign in
    assert client.post("/auth/alumni/login", json={"email": "new@example.com"}).status_code == 404
    # sign up creates a profile that is NOT onboarded yet
    created = client.post("/auth/alumni/signup", json={"email": " New@Example.com ", "full_name": "Nia Okafor"})
    assert created.status_code == 200
    body = created.json()
    assert (body["email"], body["full_name"], body["onboarded"]) == ("new@example.com", "Nia Okafor", False)
    # signing up twice is a conflict; signing in works and is still not onboarded
    assert client.post("/auth/alumni/signup", json={"email": "new@example.com", "full_name": "Nia O"}).status_code == 409
    assert client.post("/auth/alumni/login", json={"email": "NEW@example.com"}).json()["onboarded"] is False
    # validation
    assert client.post("/auth/alumni/signup", json={"email": "nope", "full_name": "A B"}).status_code == 422
    assert client.post("/auth/alumni/signup", json={"email": "x@y.com", "full_name": "   "}).status_code == 422
    # once a resume is confirmed the profile counts as onboarded
    upload_and_confirm(client, body["id"], NO_CITY_RESUME.replace("test@example.com", "new@example.com"))
    assert client.post("/auth/alumni/login", json={"email": "new@example.com"}).json()["onboarded"] is True


def test_cohort_year_and_growth(client):
    pid = client.post("/auth/alumni/signup", json={"email": "grow@example.com", "full_name": "Gro Wth"}).json()["id"]
    assert client.post(f"/profiles/{pid}/cohort", json={"cohort": "2023"}).json() == {"cohort": "2023"}
    prof = client.get(f"/profiles/{pid}").json()
    assert (prof["cohort"], prof["graduation_year"]) == ("2023", 2023)
    for bad in ("2014", "abcd", "23", "9999", ""):
        assert client.post(f"/profiles/{pid}/cohort", json={"cohort": bad}).status_code == 422
    import uuid
    assert client.post(f"/profiles/{uuid.uuid4()}/cohort", json={"cohort": "2023"}).status_code == 404

    empty = client.get(f"/profiles/{pid}/growth").json()
    assert empty["salary_history"] == [] and empty["roles"] == 0 and empty["first_role_start"] is None

    from app.db import get_conn
    with get_conn() as conn:
        for day, lo, hi in (("2025-01-10", 60000, 70000), ("2026-02-01", 80000, 90000)):
            conn.execute("INSERT INTO salary_records (id, alumni_id, salary_min, salary_max, source, effective_date) "
                         "VALUES (gen_random_uuid(), %s, %s, %s, 'self_reported', %s)", (pid, lo, hi, day))
        conn.commit()
    history = client.get(f"/profiles/{pid}/growth").json()["salary_history"]
    assert [(h["date"], h["salary_min"], h["salary_max"]) for h in history] == [
        ("2025-01-10", 60000, 70000), ("2026-02-01", 80000, 90000)]


def _alumni(client, email, name, cohort=None, resume=True):
    """Sign up a profile (optionally with a confirmed resume and cohort) and return its id."""
    pid = client.post("/auth/alumni/signup", json={"email": email, "full_name": name}).json()["id"]
    if resume:
        upload_and_confirm(client, pid, NO_CITY_RESUME.replace("test@example.com", email))
    if cohort:
        assert client.post(f"/profiles/{pid}/cohort", json={"cohort": cohort}).status_code == 200
    return pid


def test_dashboard_and_actions_need_the_admin_token(client):
    for path in ("/admin/dashboard", "/admin/actions"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=admin_headers(client)).status_code == 200
    assert client.post("/admin/actions/00000000-0000-0000-0000-000000000000", json={"status": "contacted"}).status_code == 401


def test_dashboard_filters_by_cohort(client):
    _alumni(client, "a24@example.com", "Ann Twentyfour", cohort="2024")
    _alumni(client, "b22@example.com", "Bo Twentytwo", cohort="2022")
    _alumni(client, "nocohort@example.com", "No Cohort")
    h = admin_headers(client)

    everyone = client.get("/admin/dashboard?cohort=all", headers=h).json()
    assert everyone["selected"] == "all" and everyone["kpis"]["alumni"] == 3 and everyone["kpis"]["real"] == 3
    only24 = client.get("/admin/dashboard?cohort=2024", headers=h).json()
    assert only24["kpis"]["alumni"] == 1 and only24["selected"] == "2024"
    assert [c["name"] for c in only24["cohorts"]["list"]][:3] == ["2025", "2024", "2022"]  # next cohort is listed
    assert only24["cohorts"]["current"] == "2024" and only24["cohorts"]["next"] == "2025"
    assert client.get("/admin/dashboard?cohort=current", headers=h).json()["selected"] == "2024"
    assert client.get("/admin/dashboard?cohort=next", headers=h).json()["kpis"]["alumni"] == 0
    assert {r["label"] for r in only24["roles"]} == {"Other"}  # current role "Course Assistant" is not a known role type
    assert [l["city"] for l in only24["locations"]] == ["Hoboken"] and only24["locations"][0]["lat"] is not None
    assert only24["salary"]["n_with_salary"] == 0 and only24["salary"]["series"] == []  # nothing invented


def test_needs_action_flow_with_follow_up_and_support(client):
    pid = _alumni(client, "gap@example.com", "Gap Person", cohort="2024", resume=False)  # no roles at all
    h = admin_headers(client)

    open_now = client.get("/admin/actions", headers=h).json()
    item = next(i for i in open_now["items"] if i["id"] == pid)
    assert item["priority"] == "medium" and {f["type"] for f in item["flags"]} >= {"missing_info", "stale"}
    assert open_now["counts"]["total"] >= 1 and open_now["counts"]["missing_info"] >= 1

    # follow-up: contacted removes it from the open list but keeps it under 'contacted'
    done = client.post(f"/admin/actions/{pid}", headers=h, json={"status": "contacted", "note": "Emailed on Oct 17"})
    assert done.status_code == 200 and done.json()["note"] == "Emailed on Oct 17"
    assert pid not in [i["id"] for i in client.get("/admin/actions", headers=h).json()["items"]]
    contacted = client.get("/admin/actions?status=contacted", headers=h).json()["items"]
    assert [i["note"] for i in contacted if i["id"] == pid] == ["Emailed on Oct 17"]

    # the alumnus asks for help: it reopens as a high-priority item with their message
    assert client.post(f"/profiles/{pid}/support", json={"message": "Laid off in June"}).status_code == 200
    assert client.get(f"/profiles/{pid}/support").json()["message"] == "Laid off in June"
    again = next(i for i in client.get("/admin/actions", headers=h).json()["items"] if i["id"] == pid)
    assert again["status"] == "open" and again["priority"] == "high"
    assert any(f["type"] == "support" and "Laid off in June" in f["detail"] for f in again["flags"])

    # filters
    assert pid in [i["id"] for i in client.get("/admin/actions?flag=support", headers=h).json()["items"]]
    assert pid not in [i["id"] for i in client.get("/admin/actions?flag=career_gap", headers=h).json()["items"]]
    assert pid in [i["id"] for i in client.get("/admin/actions?q=gap%20per", headers=h).json()["items"]]
    assert client.get("/admin/actions?cohort=2022", headers=h).json()["items"] == []

    # validation
    assert client.post(f"/admin/actions/{pid}", headers=h, json={"status": "bogus"}).status_code == 422
    import uuid
    assert client.post(f"/admin/actions/{uuid.uuid4()}", headers=h, json={"status": "resolved"}).status_code == 404
    assert client.post(f"/profiles/{uuid.uuid4()}/support", json={}).status_code == 404


def _software_resume(email, employer, city, linkedin=None, name="Test Person"):
    extra = f" | linkedin.com/in/{linkedin}" if linkedin else ""
    return (f"{name}\n{email}{extra}\nExperience\n{employer}, {city}\n"
            "Software Engineer                                   Sep 2025 - Present\n- Built APIs\nSkills\nPython, SQL\n")


def _engineer(client, email, name, employer, city, linkedin=None):
    pid = client.post("/auth/alumni/signup", json={"email": email, "full_name": name}).json()["id"]
    upload_and_confirm(client, pid, _software_resume(email, employer, city, linkedin, name))
    return pid


def test_everyone_is_in_the_network_automatically_ranked_with_linkedin_from_the_resume(client):
    me = _engineer(client, "me@example.com", "Me Myself", "Acme Corp", "Hoboken, NJ")
    _engineer(client, "co@example.com", "Casey Colleague", "Acme Corp", "Atlanta, GA", linkedin="casey-colleague")
    _engineer(client, "near@example.com", "Nia Neighbor", "Other Co", "Newark, NJ")
    far = _engineer(client, "far@example.com", "Fay Faraway", "Other Co", "Chicago, IL", linkedin="fay-faraway")
    _engineer(client, "also@example.com", "Hal Hadnothingtodo", "Acme Corp", "Hoboken, NJ")  # no opt-in step exists: he is in too

    got = client.get(f"/profiles/{me}/network/peers").json()
    names = [p["name"] for p in got["items"]]
    assert names == ["Hal Hadnothingtodo", "Casey Colleague", "Nia Neighbor", "Fay Faraway"]   # everyone but me, ranked
    assert got["counts"] == {"all": 4, "company": 2, "city": 2, "role": 4} and got["my_role_type"] == "Software & engineering"
    by_name = {p["name"]: p for p in got["items"]}
    assert by_name["Casey Colleague"]["reasons"] == ["Same company", "Same role type"]
    assert by_name["Nia Neighbor"]["reasons"] == ["Same metro area", "Same role type"]
    assert by_name["Casey Colleague"]["email"] == "co@example.com" and by_name["Casey Colleague"]["employer"] == "Acme Corp"
    assert by_name["Casey Colleague"]["linkedin_url"] == "https://www.linkedin.com/in/casey-colleague"   # found on the resume
    assert by_name["Casey Colleague"]["linkedin_kind"] == "profile"
    assert by_name["Nia Neighbor"]["linkedin_url"] is None and by_name["Nia Neighbor"]["linkedin_kind"] is None   # none on the resume
    assert [p["name"] for p in client.get(f"/profiles/{me}/network/peers?scope=company").json()["items"]] == ["Hal Hadnothingtodo", "Casey Colleague"]
    assert [p["name"] for p in client.get(f"/profiles/{me}/network/peers?scope=city").json()["items"]] == ["Hal Hadnothingtodo", "Nia Neighbor"]

    # re-confirming WITHOUT a LinkedIn link (what the review form sends later) must not erase the one already found
    upload_and_confirm(client, far, _software_resume("far@example.com", "Other Co", "Chicago, IL", name="Fay Faraway"))
    again = {p["name"]: p for p in client.get(f"/profiles/{me}/network/peers").json()["items"]}
    assert again["Fay Faraway"]["linkedin_url"] == "https://www.linkedin.com/in/fay-faraway"

    # the old opt-in endpoints are gone
    assert client.get(f"/profiles/{me}/network/settings").status_code in (404, 405)
    assert client.put(f"/profiles/{me}/network/settings", json={"visible": False}).status_code in (404, 405)


def test_network_errors_and_empty_state(client):
    import uuid
    pid = client.post("/auth/alumni/signup", json={"email": "s@example.com", "full_name": "Sam Settings"}).json()["id"]
    assert client.get(f"/profiles/{pid}/network/peers?scope=bogus").status_code == 422
    empty = client.get(f"/profiles/{pid}/network/peers").json()
    assert empty["items"] == [] and empty["has_role"] is False
    ghost = uuid.uuid4()
    assert client.get(f"/profiles/{ghost}/network/peers").status_code == 404
    assert client.get(f"/profiles/{ghost}/recommendations").status_code == 404


def test_job_matches_report_recency_and_what_they_were_based_on(client, monkeypatch):
    import app.jobs.greenhouse as gh
    pid = _engineer(client, "job@example.com", "Jo Seeker", "Acme Corp", "Hoboken, NJ")
    monkeypatch.setattr(gh, "BOARD_TOKENS", ["acme"])
    jobs = [gh_job(1, "Software Engineer", "Hoboken, NJ"), gh_job(2, "Software Engineer II", "Remote")]
    jobs[0]["updated_at"] = "2026-10-12T09:00:00-04:00"
    jobs[1]["updated_at"] = "2026-09-01T09:00:00-04:00"
    monkeypatch.setattr(gh.httpx, "get", lambda *a, **k: FakeResp({"jobs": jobs}))
    assert client.post("/jobs/refresh", headers=admin_headers(client)).json()["jobs_upserted"] == 2

    body = client.get(f"/users/{pid}/job-matches").json()
    assert {m["title"]: m["updated_at"][:10] for m in body["matches"]} == {"Software Engineer": "2026-10-12", "Software Engineer II": "2026-09-01"}
    assert body["refreshed_at"] is not None                                  # when OUR list was last refreshed
    assert body["matched_on"] == {"role_title": "Software Engineer", "role_type": "Software & engineering",
                                  "city": "Hoboken, NJ", "salary_min": None, "salary_max": None}


def test_events_and_recommendations_endpoints(client):
    pid = _engineer(client, "ev@example.com", "Eva Events", "Acme Corp", "Hoboken, NJ")
    ev = client.get(f"/profiles/{pid}/events").json()
    assert ev["metro"] == "New York metro" and ev["local"] and ev["online"]
    assert ev["local"][0]["for_you"] is True and all(e["sample"] for e in ev["local"])
    rec = client.get(f"/profiles/{pid}/recommendations").json()
    assert rec["family"] == "software" and rec["recommended"] and rec["skills_to_add"] and rec["programs"]


def test_resume_hyperlink_target_beats_a_printed_url_that_was_cut_short(client):
    """A long LinkedIn URL wraps in a real resume, so the printed text is truncated; the link target is exact."""
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 760
    for line in ["Jane Doe", "jane@example.com | linkedin.com/in/jane-doe-with-a-very-lo", "Experience", "Acme Corp, Hoboken, NJ",
                 "Software Engineer                      Sep 2025 - Present", "- Built APIs", "Skills", "Python, SQL"]:
        c.drawString(40, y, line); y -= 14
    c.linkURL("https://www.linkedin.com/in/jane-doe-with-a-very-long-profile-name-4a5b6c", (40, 732, 330, 746))
    c.save()
    got = client.post("/resume/parse", files={"file": ("r.pdf", buf.getvalue(), "application/pdf")})
    assert got.status_code == 200
    assert got.json()["linkedin_url"] == "https://www.linkedin.com/in/jane-doe-with-a-very-long-profile-name-4a5b6c"


# ---------------------------------------------------------------- invite links, in-room QR, automated emails
def _joined(client, email, name, cohort=None, invite=None, room=None):
    """Sign up the way the app does (optionally through an invite link or in-room QR), pick a cohort, confirm a resume."""
    body = {"email": email, "full_name": name, **({"invite": invite} if invite else {}), **({"cohort": room} if room else {})}
    r = client.post("/auth/alumni/signup", json=body)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    if cohort:
        assert client.post(f"/profiles/{pid}/cohort", json={"cohort": cohort}).status_code == 200
    upload_and_confirm(client, pid, _software_resume(email, "Acme Corp", "Newark, NJ", name=name))
    return pid


def _outbox():
    from app.db import get_conn
    with get_conn() as conn:
        return conn.execute("SELECT kind, to_email, subject, body, sent_at FROM email_outbox ORDER BY kind, to_email").fetchall()


def test_invite_link_signs_up_into_the_inviters_cohort_and_logs_the_emails(client):
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute("""INSERT INTO alumni_roster (email, first_name, last_name, cohort) VALUES
                        ('rosa.roster@example.com', 'Rosa', 'Roster', '2026'), ('late@example.com', 'Lee', 'Late', '2026'),
                        ('other@example.com', 'Oz', 'Other', '2024')""")
        conn.commit()
    ana = _joined(client, "ana@example.com", "Ana Alum", cohort="2026")
    invite = client.get(f"/profiles/{ana}/invite").json()
    assert invite["joined"] == 0 and len(invite["code"]) >= 8
    assert client.get(f"/profiles/{ana}/invite").json()["code"] == invite["code"]          # one code per alumnus
    assert client.get(f"/invites/{invite['code']}").json() == {"inviter_first_name": "Ana", "cohort": "2026"}
    assert client.get("/invites/nope").status_code == 404

    # Ana joined first: her roster cohort-mates who have no profile get her link; nobody else is in her cohort yet
    assert [(k, to) for k, to, *_ in _outbox()] == [("cohort_invite", "late@example.com"), ("cohort_invite", "rosa.roster@example.com")]
    assert f"/?invite={invite['code']}" in _outbox()[0][3] and all(sent is None for *_, sent in _outbox())   # logged, never sent

    # Rosa uses the link: she lands in Ana's cohort without choosing it, and Ana's invite counts her
    rosa = _joined(client, "rosa.roster@example.com", "Rosa Roster", invite=invite["code"])
    assert client.get(f"/profiles/{rosa}").json()["cohort"] == "2026"
    assert client.get(f"/profiles/{ana}/invite").json()["joined"] == 1
    new = [(k, to) for k, to, *_ in _outbox() if k != "cohort_invite"]
    assert new == [("invite_worked", "ana@example.com"), ("just_joined", "ana@example.com")]
    assert sum(1 for k, to, *_ in _outbox() if to == "late@example.com") == 1   # a roster person is invited only once

    # a second confirm (profile update) sends nothing new
    before = len(_outbox())
    upload_and_confirm(client, rosa, _software_resume("rosa.roster@example.com", "Beta Inc", "Newark, NJ", name="Rosa Roster"))
    assert len(_outbox()) == before

    bad = client.post("/auth/alumni/signup", json={"email": "x@example.com", "full_name": "X Y", "invite": "nope"})
    assert bad.status_code == 422 and "invite link" in bad.json()["detail"]


def test_in_room_qr_signup_picks_the_cohort(client):
    pid = client.post("/auth/alumni/signup", json={"email": "room@example.com", "full_name": "Rae Room", "cohort": "2025"}).json()["id"]
    assert client.get(f"/profiles/{pid}").json()["cohort"] == "2025"
    assert client.post("/auth/alumni/signup", json={"email": "r2@example.com", "full_name": "R T", "cohort": "1999"}).status_code == 422
    auto = client.get("/admin/automation", headers=admin_headers(client)).json()
    assert auto["signups"] == {"invite": 0, "room": 1}


def test_admin_can_switch_automated_emails_off(client):
    headers = admin_headers(client)
    assert client.get("/admin/automation").status_code == 401
    assert client.post("/admin/automation/emails", json={"enabled": False}).status_code == 401
    assert client.get("/admin/automation", headers=headers).json()["emails"]["enabled"] is True        # on by default
    _joined(client, "first@example.com", "Fi First", cohort="2023")
    assert client.post("/admin/automation/emails", json={"enabled": False}, headers=headers).json() == {"enabled": False}
    _joined(client, "second@example.com", "Se Second", cohort="2023")
    assert _outbox() == []                                   # off: Fi does not hear that Se joined
    client.post("/admin/automation/emails", json={"enabled": True}, headers=headers)
    _joined(client, "third@example.com", "Th Third", cohort="2023")
    got = client.get("/admin/automation", headers=headers).json()
    assert got["emails"]["enabled"] is True and got["emails"]["sending"] is False
    assert got["emails"]["counts"] == {"just_joined": 2, "invite_worked": 0, "cohort_invite": 0}
    assert {e["to_email"] for e in got["emails"]["recent"]} == {"first@example.com", "second@example.com"}
    assert "job_refresh" not in got and got["newsletter"]["monthly_enabled"] is True   # the job refresh has no panel any more


# ---------------------------------------------------------------- admin newsletter controls
def _install_newsletter_tables():
    """The newsletter tables come from a separate, owner-approved migration (init_db does not create them)."""
    from pathlib import Path
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute((Path(__file__).resolve().parent.parent / "sql" / "newsletter.sql").read_text())
        conn.commit()


def _make_demo(email):
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute("UPDATE alumni SET is_demo = TRUE WHERE email = %s", (email,))
        conn.commit()


def test_newsletter_section_is_on_by_default_and_the_admin_can_pause_it(client):
    headers = admin_headers(client)
    got = client.get("/admin/automation", headers=headers).json()["newsletter"]
    assert got["monthly_enabled"] is True and got["mode"] == "dry_run" and got["next_send_at"]       # dry run unless set to "false"
    assert client.post("/admin/automation/newsletter", json={"enabled": False}).status_code == 401
    assert client.post("/admin/automation/newsletter", json={"enabled": False}, headers=headers).json() == {"enabled": False}
    assert client.get("/admin/automation", headers=headers).json()["newsletter"]["monthly_enabled"] is False
    client.post("/admin/automation/newsletter", json={"enabled": True}, headers=headers)
    assert client.get("/admin/automation", headers=headers).json()["newsletter"]["monthly_enabled"] is True


def test_newsletter_send_to_one_alum(client, monkeypatch):
    import os
    if os.environ.get("DATABASE_URL") != os.environ["TEST_DATABASE_URL"]:
        pytest.skip("The newsletter code reads DATABASE_URL: set it to the same scratch database as TEST_DATABASE_URL")
    from app.db import get_conn
    monkeypatch.setenv("NEWSLETTER_TOKEN_SECRET", "x" * 40)
    _install_newsletter_tables()
    headers = admin_headers(client)
    demo = _engineer(client, "demo.alum@example.com", "Dee Mo", "Acme Corp", "Newark, NJ")
    real = _engineer(client, "real.alum@example.com", "Rae Al", "Acme Corp", "Newark, NJ")
    _make_demo("demo.alum@example.com")
    status = client.get("/admin/automation", headers=headers).json()["newsletter"]
    assert status["available"] is True and status["subscribers"] == 0 and status["deliveries"] == {}

    # sending needs the alum's own opt-in: before it, nothing is recorded
    send = lambda email: client.post("/admin/automation/newsletter/send", json={"email": email}, headers=headers)
    assert send("demo.alum@example.com").json()["status"] == "not_subscribed"
    assert send("real.alum@example.com").status_code == 403
    assert send("nobody@example.com").status_code == 404
    assert client.post("/admin/automation/newsletter/send", json={"email": "demo.alum@example.com"}).status_code == 401
    with get_conn() as conn:
        conn.execute("INSERT INTO newsletter_subscriptions (alumni_id, subscribed, token_nonce) VALUES (%s, TRUE, 'n-1')", (demo,))
        conn.commit()
    sent = send("demo.alum@example.com").json()
    assert (sent["status"], sent["mode"], sent["name"]) == ("dry_run", "dry_run", "Dee Mo")   # logged, never emailed
    status = client.get("/admin/automation", headers=headers).json()["newsletter"]
    assert status["subscribers"] == 1 and status["deliveries"] == {"dry_run": 1}
    assert real  # the real alum stayed out of every count above


def test_just_joined_tag_marks_only_recent_app_sign_ups(client):
    from app.db import get_conn
    me = _engineer(client, "me2@example.com", "Me Two", "Acme Corp", "Hoboken, NJ")
    seeded = _engineer(client, "seeded@example.com", "Sam Seeded", "Acme Corp", "Hoboken, NJ")
    room = client.post("/auth/alumni/signup", json={"email": "room2@example.com", "full_name": "Rae Room", "cohort": "2025"}).json()["id"]
    upload_and_confirm(client, room, _software_resume("room2@example.com", "Acme Corp", "Hoboken, NJ", name="Rae Room"))
    with get_conn() as conn:  # a demo/seeded alum: created today, but no sign-up record
        conn.execute("UPDATE alumni SET is_demo = TRUE WHERE id = %s", (seeded,))
        conn.commit()
    tags = {p["name"]: p["just_joined"] for p in client.get(f"/profiles/{me}/network/peers").json()["items"]}
    assert tags == {"Sam Seeded": False, "Rae Room": True}
    with get_conn() as conn:  # a sign-up older than a week stops being "just joined"
        conn.execute("UPDATE signup_sources SET created_at = now() - interval '8 days' WHERE alumni_id = %s", (room,))
        conn.execute("UPDATE alumni SET created_at = now() - interval '8 days' WHERE id = %s", (room,))
        conn.commit()
    assert {p["name"]: p["just_joined"] for p in client.get(f"/profiles/{me}/network/peers").json()["items"]}["Rae Room"] is False
