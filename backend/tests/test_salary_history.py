"""Offline: validation for dated salary entries (the endpoints themselves use the live database)."""
from datetime import date

import pytest
from fastapi import HTTPException

from backend.app.onboarding.router import SalaryIn, check_salary, month_start

TODAY = date(2026, 10, 17)


def test_past_and_current_months_are_accepted_as_the_first_of_the_month():
    assert check_salary(SalaryIn(salary_min=55000, salary_max=60000, month="2022-06"), TODAY) == date(2022, 6, 1)
    assert check_salary(SalaryIn(salary_min=90000, salary_max=90000, month="2026-10"), TODAY) == date(2026, 10, 1)


@pytest.mark.parametrize("month", ["2026-11", "2027-01", "1969-12", "2022-13", "2022-6", "June 2022", ""])
def test_future_old_or_malformed_months_are_rejected(month):
    with pytest.raises(HTTPException) as caught:
        month_start(month, TODAY)
    assert caught.value.status_code == 422


@pytest.mark.parametrize("low,high", [(0, 50000), (60000, 50000), (-1, 10), (1, 10_000_000_000)])
def test_impossible_ranges_are_rejected(low, high):
    with pytest.raises(HTTPException):
        check_salary(SalaryIn(salary_min=low, salary_max=high, month="2022-06"), TODAY)



def test_job_labels_and_clearing():
    import uuid
    from backend.app.onboarding.router import SalaryJobIn, job_label
    assert job_label("Software Engineer", "Demo Cloud") == "Software Engineer at Demo Cloud"
    assert job_label(None, "Demo Cloud") == "Demo Cloud" and job_label(None, None) == "Untitled role"
    assert SalaryJobIn().work_experience_id is None  # an empty body clears the job
    job = uuid.uuid4()
    assert SalaryJobIn(work_experience_id=str(job)).work_experience_id == job
