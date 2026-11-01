from app.jobs.matching import MatchProfile, title_family, top_matches
from app.parsing.schema import ParsedResume
from app.parsing.validate import normalize


def test_title_family():
    assert title_family("Senior Software Engineer") == "software"
    assert title_family("Customer Success Manager") == "support"


def test_short_keywords_only_match_whole_words():
    # "ui" inside "recruiter"/"guide", "it" inside "audit" are not UI design or IT support
    assert title_family("Recruiter") is None
    assert title_family("Recruiting Coordinator") is None
    assert title_family("Tour Guide") is None
    assert title_family("Audit Associate") == "ops"
    assert title_family("UI Designer") == "design"
    assert title_family("UX Researcher") == "design"
    assert title_family("UX/UI Designer") == "design"
    assert title_family("IT Support Specialist") == "support"
    assert title_family("Junior IT Technician") == "support"
    # a recruiter is not shown design jobs as a "Similar role"
    jobs = [{"id": 1, "title": "Senior UX Designer", "company": "Acme", "location": "New York, NY", "absolute_url": "https://x"}]
    assert top_matches(MatchProfile("Recruiter", "New York, NY"), jobs) == []


def test_hr_roles_that_mention_engineering_are_not_software():
    assert title_family("Engineering Compensation Partner") is None
    assert title_family("Director, People Partners - Product, Design & Engineering") is None
    assert title_family("Engineering Recruiter") is None
    assert title_family("Software Engineering Intern") == "software"
    jobs = [{"id": 1, "title": "Engineering Compensation Partner", "company": "Acme", "location": "New York, NY",
             "absolute_url": "https://x"}]
    assert top_matches(MatchProfile("Software Engineering Intern", "New York, NY"), jobs) == []


def test_top_matches_ranks_and_explains():
    profile = MatchProfile("Software Engineer", "Chicago, IL", 90000, 120000)
    jobs = [
        {"id": 1, "title": "Backend Software Engineer", "company": "A", "location": "Chicago, IL",
         "salary_min": 100000, "salary_max": 130000, "absolute_url": "u1"},
        {"id": 2, "title": "Account Executive", "company": "B", "location": "Austin, TX",
         "salary_min": None, "salary_max": None, "absolute_url": "u2"},
        {"id": 3, "title": "Data Analyst", "company": "C", "location": "Remote",
         "salary_min": None, "salary_max": None, "absolute_url": "u3"},
    ]
    res = top_matches(profile, jobs)
    assert res[0]["job_id"] == 1
    assert "Same city" in res[0]["why_matched"] and "Salary in range" in res[0]["why_matched"]
    assert all(r["job_id"] != 2 for r in res)


def test_normalize_current_role_and_order():
    r = ParsedResume.model_validate({"work_experience": [
        {"employer": "X", "title": "Old", "start_date": "2019-01", "end_date": "2020-05"},
        {"employer": "Y", "title": "New", "start_date": "2021-03", "end_date": "garbage"},
    ]})
    r = normalize(r)
    assert r.work_experience[0].title == "New" and not r.work_experience[0].is_current
    assert any("invalid end date" in warning for warning in r.warnings)


def test_location_is_required_when_city_known():
    profile = MatchProfile("Software Engineer", "Chicago, IL")
    def job(i, loc):
        return {"id": i, "title": "Software Engineer", "company": "A", "location": loc,
                "salary_min": None, "salary_max": None, "absolute_url": "u"}
    res = top_matches(profile, [job(1, "Dublin, Ireland"), job(2, "Springfield, IL"),
                                job(3, "Remote - US"), job(4, "San Francisco, CA • Chicago, IL"),
                                job(5, "Tokyo, Japan")])
    ids = [r["job_id"] for r in res]
    assert set(ids) == {2, 3, 4}  # Dublin and Tokyo dropped
    assert "Same state" in next(r for r in res if r["job_id"] == 2)["why_matched"]
    assert "Same city" in next(r for r in res if r["job_id"] == 4)["why_matched"]


def test_no_city_means_location_is_not_filtered():
    profile = MatchProfile("Software Engineer", None)
    jobs = [{"id": 1, "title": "Software Engineer", "company": "A", "location": "Dublin, Ireland",
             "salary_min": None, "salary_max": None, "absolute_url": "u"}]
    assert len(top_matches(profile, jobs)) == 1


def test_role_required_even_if_location_matches():
    profile = MatchProfile("Software Engineer", "Chicago, IL")
    jobs = [{"id": 1, "title": "Account Executive", "company": "A", "location": "Chicago, IL",
             "salary_min": None, "salary_max": None, "absolute_url": "u"}]
    assert top_matches(profile, jobs) == []


def test_newark_user_sees_nyc_jobs_but_not_la():
    profile = MatchProfile("Software Engineer", "Newark, NJ")
    def job(i, loc):
        return {"id": i, "title": "Software Engineer", "company": "A", "location": loc,
                "salary_min": None, "salary_max": None, "absolute_url": "u"}
    res = top_matches(profile, [job(1, "New York, NY"), job(2, "Los Angeles, CA"), job(3, "Newark, NJ")])
    assert {r["job_id"] for r in res} == {1, 3}
    assert "Same metro area" in next(r for r in res if r["job_id"] == 1)["why_matched"]


def _job(i, title, loc="Chicago, IL"):
    return {"id": i, "title": title, "company": "A", "location": loc,
            "salary_min": None, "salary_max": None, "absolute_url": "u"}


def test_generic_words_are_not_a_role_match():
    # Only "assistant" is shared: not the same kind of work
    profile = MatchProfile("Course Assistant", "Hoboken, NJ")
    jobs = [_job(1, "Executive Assistant", "Hoboken, NJ"), _job(2, "Administrative Assistant", "Remote")]
    assert top_matches(profile, jobs) == []


def test_seniority():
    from app.jobs.matching import seniority
    assert [seniority(t) for t in [
        "Software Engineer Intern", "Associate Product Manager", "Backend Software Engineer",
        "Senior Product Manager", "Product Manager II", "Engineering Manager", "Staff Software Engineer",
        "Senior Director of Product"]] == [0, 1, 2, 3, 2, 4, 4, 5]


def test_intern_does_not_see_manager_or_senior_roles():
    profile = MatchProfile("AI Software Engineering Intern", "San Francisco, CA")
    jobs = [_job(1, "Software Engineer Intern", "San Francisco, CA"),
            _job(2, "Backend Software Engineer", "San Francisco, CA"),   # entry-level step up: ok
            _job(3, "Senior Software Engineer", "San Francisco, CA"),
            _job(4, "Engineering Manager", "San Francisco, CA")]
    assert {r["job_id"] for r in top_matches(profile, jobs)} == {1, 2}


def test_senior_pm_sees_pm_roles_not_directors_or_interns():
    profile = MatchProfile("Senior Product Manager", "New York, NY")
    jobs = [_job(1, "Senior Product Manager, Growth", "New York, NY"),
            _job(2, "Product Manager", "New York, NY"),
            _job(3, "Principal Product Manager", "New York, NY"),
            _job(4, "Senior Director of Product", "New York, NY"),
            _job(5, "Product Manager Intern", "New York, NY")]
    assert {r["job_id"] for r in top_matches(profile, jobs)} == {1, 2, 3}


def test_only_us_remote_counts():
    profile = MatchProfile("Software Engineer", "Chicago, IL")
    locs = {1: "Remote", 2: "Remote - USA", 3: "Remote - Argentina", 4: "Remote, UK",
            5: "Remote - Ontario, Canada", 6: "United States - Remote"}
    res = top_matches(profile, [_job(i, "Software Engineer", loc) for i, loc in locs.items()])
    assert {r["job_id"] for r in res} == {1, 2, 6}


def test_foreign_remote_dropped_even_without_a_city():
    profile = MatchProfile("Software Engineer", None)
    assert top_matches(profile, [_job(1, "Software Engineer", "Remote - India")]) == []


def test_product_family_needs_a_product_management_title():
    assert title_family("Senior Product Manager") == "product"
    assert title_family("Group Product Manager, Ads") == "product"
    assert title_family("Technical Program Manager") == "product"
    # the word "product" alone is not a product-manager role
    assert title_family("Account Executive, Product Sales - Billing") == "sales"
    assert title_family("Senior Product Marketing Manager") != "product"


def test_pm_roles_outrank_sales_roles_even_when_the_sales_title_sorts_first():
    profile = MatchProfile("Senior Product Manager", "New York, NY")
    jobs = [_job(1, "Account Executive, Product Sales", "New York, NY"),
            _job(2, "Senior Product Manager, Growth", "New York, NY")]
    res = top_matches(profile, jobs)
    assert res[0]["job_id"] == 2 and res[0]["score"] > res[-1]["score"]  # sales role is at most a weak extra


def test_top_matches_pass_through_when_the_posting_was_last_updated():
    from datetime import datetime, timezone
    stamp = datetime(2026, 10, 1, tzinfo=timezone.utc)
    profile = MatchProfile("Software Engineer", "Chicago, IL")
    res = top_matches(profile, [{**_job(1, "Software Engineer"), "updated_at": stamp}, _job(2, "Backend Software Engineer")])
    by_id = {r["job_id"]: r for r in res}
    assert by_id[1]["updated_at"] == stamp and by_id[2]["updated_at"] is None
