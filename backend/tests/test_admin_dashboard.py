"""Offline tests for the admin dashboard maths and the needs-action rules (no database)."""
from datetime import date, datetime, timedelta, timezone

from app.admin.dashboard import (action_status, build_actions, cohort_choices, flags_for, group_stats,
                                 location_breakdown, resolve_cohort, role_breakdown, salary_charts, select_members)

NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
TODAY = NOW.date()


def row(i, **kw):
    base = {"id": i, "first_name": f"First{i}", "last_name": f"Last{i}", "email": f"p{i}@x.com", "city": "New York, NY",
            "cohort": "2024", "graduation_year": 2024, "is_demo": False, "updated_at": NOW - timedelta(days=5),
            "employed": True, "roles": 1, "last_end": None, "role_title": "Software Engineer", "schools": 1, "skills": 2,
            "salary_records": 1, "last_confirmed": NOW - timedelta(days=10), "support_at": None, "support_message": None,
            "action_status": None, "action_note": None, "action_at": None}
    base.update(kw)
    return base


def types(r):
    return [f["type"] for f in flags_for(r, NOW)]


# ------------------------------------------------------------------ cohorts
def test_current_and_next_cohort():
    rows = [row(1, cohort="2024"), row(2, cohort="2022"), row(3, cohort="2027"), row(4, cohort=None)]
    c = cohort_choices(rows, {}, TODAY)
    assert (c["current"], c["next"]) == ("2024", "2025")  # 2027 is in the future, so it is not "current"
    assert [x["name"] for x in c["list"]] == ["2027", "2025", "2024", "2022"]
    assert next(x for x in c["list"] if x["name"] == "2025")["size"] == 0  # next cohort exists even when empty


def test_no_cohorts_means_this_year_is_current():
    c = cohort_choices([row(1, cohort=None)], {}, TODAY)
    assert (c["current"], c["next"]) == ("2026", "2027")


def test_resolve_and_select():
    c = cohort_choices([row(1), row(2, cohort="2022")], {}, TODAY)
    assert resolve_cohort("current", c) == "2024" and resolve_cohort("next", c) == "2025"
    assert resolve_cohort("all", c) == "all" and resolve_cohort("2022", c) == "2022"
    rows = [row(1), row(2, cohort="2022")]
    assert [r["id"] for r in select_members(rows, "2022")] == [2] and len(select_members(rows, "all")) == 2


# ------------------------------------------------------------------ KPI + charts
def test_group_stats_by_hand():
    members = [row(1), row(2, employed=False), row(3)]
    sal = {1: [(date(2025, 1, 1), 60000.0), (date(2026, 1, 1), 80000.0)], 2: [(date(2026, 1, 1), 100000.0)]}
    s = group_stats(members, sal)
    assert (s["size"], s["employed"], s["employment_rate"]) == (3, 2, 67)
    assert s["avg_salary"] == 90000  # mean of the LATEST midpoints: 80k and 100k
    assert (s["salary_growth_pct"], s["salary_growth_n"]) == (33.3, 1)  # only alumni 1 has two records


def test_no_salary_data_is_null_not_zero():
    s = group_stats([row(1)], {})
    assert s["avg_salary"] is None and s["salary_growth_pct"] is None and s["salary_growth_n"] == 0


def test_role_breakdown_groups_by_family_and_skips_missing_titles():
    members = [row(1, role_title="Software Engineer"), row(2, role_title="Backend Developer"),
               row(3, role_title="Data Analyst"), row(4, role_title="Barista"), row(5, role_title=None)]
    got = {r["family"]: r["count"] for r in role_breakdown(members)}
    assert got == {"software": 2, "data": 1, "other": 1}
    assert role_breakdown(members)[0]["label"] == "Software & engineering"


def test_locations_group_cities_and_leave_unknown_ones_unplaced():
    members = [row(1, city="New York, NY"), row(2, city="new york"), row(3, city="Newark"), row(4, city="Smallville"), row(5, city=None)]
    locs = location_breakdown(members)
    assert [(l["city"], l["alumni"]) for l in locs][:2] == [("New York", 2), ("Newark", 1)]
    small = next(l for l in locs if l["city"] == "Smallville")
    assert small["lat"] is None and small["lng"] is None
    assert next(l for l in locs if l["city"] == "New York")["lat"] == 40.71
    assert len(locs) == 3


def test_salary_charts_quarters_and_distribution():
    members = [row(1), row(2)]
    sal = {1: [(date(2025, 2, 1), 60000.0), (date(2025, 8, 1), 70000.0)], 2: [(date(2025, 3, 15), 80000.0)],
           99: [(date(2025, 2, 1), 500000.0)]}  # 99 is not in this cohort
    out = salary_charts(members, sal)
    assert out["series"] == [{"period": "2025-Q1", "avg": 70000, "n": 2}, {"period": "2025-Q3", "avg": 70000, "n": 1}]
    assert [d["count"] for d in out["distribution"]] == [0, 0, 1, 1, 0, 0]  # 70k -> $60-80k, 80k -> $80-100k
    assert out["n_with_salary"] == 2


# ------------------------------------------------------------------ needs action
def test_healthy_alumni_are_not_flagged():
    assert build_actions([row(1)], NOW) == []


def test_career_gap_boundary_is_90_days():
    assert "career_gap" not in types(row(1, employed=False, last_end=TODAY - timedelta(days=90)))
    gap = flags_for(row(1, employed=False, last_end=TODAY - timedelta(days=200)), NOW)[0]
    assert gap["type"] == "career_gap" and gap["priority"] == "high"
    assert gap["detail"] == "No current job since Mar 2026 (6 months)"
    assert "career_gap" in types(row(1, employed=False, last_end=TODAY - timedelta(days=91)))
    assert "career_gap" not in types(row(1, employed=True, last_end=TODAY - timedelta(days=500)))  # working now


def test_missing_info_lists_what_is_missing_and_sets_priority():
    f = next(f for f in flags_for(row(1, city=None, schools=0), NOW) if f["type"] == "missing_info")
    assert f["detail"] == "Missing: city, education" and f["priority"] == "low"
    f = next(f for f in flags_for(row(1, roles=0, employed=False), NOW) if f["type"] == "missing_info")
    assert "work experience" in f["detail"] and f["priority"] == "medium"
    f = next(f for f in flags_for(row(1, city=None, skills=0, salary_records=0), NOW) if f["type"] == "missing_info")
    assert f["priority"] == "medium"  # three or more things missing


def test_stale_boundary_is_180_days():
    assert "stale" not in types(row(1, last_confirmed=NOW - timedelta(days=180)))
    old = next(f for f in flags_for(row(1, last_confirmed=NOW - timedelta(days=181)), NOW) if f["type"] == "stale")
    assert old["label"] == "Resume out of date" and old["priority"] == "low"
    never = next(f for f in flags_for(row(1, last_confirmed=None), NOW) if f["type"] == "stale")
    assert never["label"] == "No confirmed resume" and never["priority"] == "medium"


def test_support_request_is_high_priority_and_carries_the_message():
    f = next(f for f in flags_for(row(1, support_at=NOW - timedelta(days=1), support_message="Need help with interviews"), NOW)
             if f["type"] == "support")
    assert f["priority"] == "high" and "Need help with interviews" in f["detail"] and "Oct 16" in f["detail"]


def test_actions_sorted_by_priority_then_name_and_status_rules():
    rows = [row(1, first_name="Zed", last_confirmed=None),                                  # medium
            row(2, first_name="Amy", employed=False, last_end=TODAY - timedelta(days=300)),  # high
            row(3, first_name="Bob", city=None)]                                              # low
    out = build_actions(rows, NOW)
    assert [(i["name"].split()[0], i["priority"]) for i in out] == [("Amy", "high"), ("Zed", "medium"), ("Bob", "low")]
    assert all(i["status"] == "open" for i in out)

    log = NOW - timedelta(days=3)
    assert action_status(row(1, action_status="contacted", action_at=log)) == "contacted"
    assert action_status(row(1, action_status="resolved", action_at=log, support_at=log - timedelta(days=1))) == "resolved"
    assert action_status(row(1, action_status="resolved", action_at=log, support_at=log + timedelta(days=1))) == "open"  # new request reopens
    assert action_status(row(1)) == "open"
