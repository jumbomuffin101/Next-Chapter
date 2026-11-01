"""Offline: outcomes by years since graduation (the 3-5 year view)."""
from datetime import date

from backend.app.admin.outcomes import employed_on, outcomes_by_year, salary_on, years_after

TODAY = date(2026, 10, 17)


def role(start, end=None, current=False):
    return {"start_date": start, "end_date": end, "is_current": current}


def pay(day, low, high):
    return {"effective_date": day, "salary_min": low, "salary_max": high}


def test_employment_on_a_date_follows_recorded_roles():
    roles = [role(date(2021, 9, 1), date(2023, 2, 1)), role(date(2024, 1, 1), current=True)]
    assert employed_on(roles, date(2022, 7, 1))
    assert not employed_on(roles, date(2023, 7, 1))  # the gap between jobs
    assert employed_on(roles, date(2025, 7, 1))
    assert not employed_on(roles, date(2021, 7, 1))  # before the first job


def test_salary_on_a_date_is_the_latest_entry_within_a_year():
    entries = [pay(date(2022, 1, 1), 50000, 60000), pay(date(2023, 3, 1), 70000, 80000)]
    assert salary_on(entries, date(2023, 7, 1)) == 75000
    assert salary_on(entries, date(2022, 7, 1)) == 55000
    assert salary_on(entries, date(2025, 7, 1)) is None  # nothing in the year before


def test_years_out_counts_only_alumni_who_got_that_far_and_treats_no_history_as_unknown():
    alumni = [{"id": "a", "graduation_year": 2021}, {"id": "b", "graduation_year": 2021},
              {"id": "c", "graduation_year": 2025}, {"id": "d", "graduation_year": 2021}]  # d has no roles: unknown
    roles = {"a": [role(date(2021, 8, 1), current=True)], "b": [role(date(2023, 1, 1), current=True)],
             "c": [role(date(2025, 8, 1), current=True)]}
    salaries = {"a": [pay(date(2021, 8, 1), 60000, 70000), pay(date(2024, 6, 1), 90000, 100000)]}
    rows = {r["years_out"]: r for r in outcomes_by_year(alumni, roles, salaries, TODAY)}
    assert rows[1] == {"years_out": 1, "alumni": 4, "with_work_history": 3, "employed_pct": 67, "with_salary": 1, "median_salary": 65000}
    assert rows[3]["alumni"] == 3 and rows[3]["employed_pct"] == 100 and rows[3]["median_salary"] == 95000  # c hasn't reached year 3
    assert rows[6]["alumni"] == 0 and rows[6]["employed_pct"] is None


def test_leap_day_graduations_do_not_crash():
    assert years_after(date(2024, 2, 29), 1) == date(2025, 2, 28)
