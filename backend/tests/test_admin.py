from datetime import datetime, timedelta, timezone

from app.admin.router import build_overview, outreach_reasons

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def row(i, **kw):
    base = {"id": i, "first_name": f"First{i}", "last_name": f"Last{i}", "email": f"a{i}@x.com", "city": "New York",
            "cohort": "2024", "graduation_year": 2024, "updated_at": NOW - timedelta(days=10), "employed": True,
            "roles": 1, "schools": 1, "skills": 1, "salary_records": 1, "salary_now": 80000, "salary_first": 80000,
            "last_confirmed": NOW - timedelta(days=5)}
    base.update(kw)
    return base


def test_cohorts_current_vs_past_and_rates():
    rows = [
        row(1, cohort="2024", graduation_year=2024, employed=True, salary_now=100000),
        row(2, cohort="2024", graduation_year=2024, employed=False, salary_now=None, salary_records=0),
        row(3, cohort="2022", graduation_year=2022, employed=True, salary_now=60000, salary_first=50000, salary_records=2),
        row(4, cohort="2022", graduation_year=2022, employed=True, salary_now=90000, salary_first=60000, salary_records=2),
    ]
    out = build_overview(rows, NOW)
    cur = out["current_cohort"]
    assert (cur["name"], cur["size"], cur["employment_rate"], cur["avg_salary"]) == ("2024", 2, 50, 100000)
    assert cur["salary_growth_pct"] is None  # nobody has two salary records: no invented number
    past = out["past_cohorts"][0]
    assert (past["name"], past["size"], past["employment_rate"], past["avg_salary"]) == ("2022", 2, 100, 75000)
    assert past["salary_growth_pct"] == 35.0  # mean of +20% and +50%


def test_locations_group_by_city_before_the_comma():
    rows = [row(1, city="San Francisco, CA"), row(2, city="san francisco"), row(3, city="Newark"), row(4, city=None)]
    locs = {l["city"]: l for l in build_overview(rows, NOW)["locations"]}
    assert locs["San Francisco"]["alumni"] == 2 and locs["Newark"]["alumni"] == 1
    assert "None" not in locs and len(locs) == 2


def test_outreach_reasons():
    assert outreach_reasons(row(1), NOW) == []
    assert outreach_reasons(row(1, updated_at=NOW - timedelta(days=200)), NOW) == ["No update in 6+ months"]
    assert outreach_reasons(row(1, employed=False), NOW) == ["No current job"]
    assert outreach_reasons(row(1, last_confirmed=None), NOW) == ["No confirmed resume yet"]
    assert outreach_reasons(row(1, salary_records=0), NOW) == ["Missing salary"]
    assert outreach_reasons(row(1, city=None, skills=0), NOW) == ["Incomplete profile: no city, skills"]


def test_outreach_list_sorted_by_number_of_reasons_and_skips_healthy_alumni():
    rows = [row(1), row(2, salary_records=0), row(3, salary_records=0, employed=False, updated_at=None, last_confirmed=None)]
    out = build_overview(rows, NOW)["outreach"]
    assert [o["id"] for o in out] == ["3", "2"]
    assert out[0]["reasons"] == ["No update in 6+ months", "No confirmed resume yet", "No current job", "Missing salary"]


def test_empty_database_gives_empty_but_valid_overview():
    out = build_overview([], NOW)
    assert out["current_cohort"] is None and out["past_cohorts"] == [] and out["locations"] == [] and out["outreach"] == []
    assert out["totals"]["size"] == 0 and out["totals"]["employment_rate"] is None


def test_alumni_without_a_cohort_are_not_in_cohort_stats_but_are_in_totals():
    out = build_overview([row(1, cohort=None, graduation_year=None), row(2)], NOW)
    assert out["current_cohort"]["size"] == 1 and out["totals"]["size"] == 2
