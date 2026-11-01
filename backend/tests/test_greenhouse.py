from app.jobs.config import GREENHOUSE_URL
from app.jobs.greenhouse import _extract_salary


def _range(title, lo, hi):
    return {"title": title, "min_cents": lo, "max_cents": hi}


def test_url_requests_pay_transparency():
    assert "pay_transparency=true" in GREENHOUSE_URL


def test_uses_pay_input_ranges():
    job = {"pay_input_ranges": [_range("Annual Base Salary", 12000000, 15000000)]}
    assert _extract_salary(job, "") == (120000, 150000)


def test_skips_hourly_range():
    job = {"pay_input_ranges": [_range("Hourly Rate:", 4000, 5000)]}
    assert _extract_salary(job, "") == (None, None)


def test_skips_equal_min_max():
    job = {"pay_input_ranges": [_range("Salary", 9000000, 9000000)]}
    assert _extract_salary(job, "") == (None, None)


def test_picks_first_usable_range():
    job = {"pay_input_ranges": [_range("Hourly Rate:", 4000, 5000), _range("Salary", 8000000, 9000000)]}
    assert _extract_salary(job, "") == (80000, 90000)


def test_falls_back_to_description_regex():
    job = {"pay_input_ranges": [_range("Hourly Rate:", 4000, 4000)]}
    assert _extract_salary(job, "Pay: $100,000 - $120,000") == (100000, 120000)


def test_implausible_annual_ranges_are_ignored():
    # hourly rate without "hourly" in the title, and a figure that is not a salary
    assert _extract_salary({"pay_input_ranges": [_range("Pay", 2000, 2100)]}, "") == (None, None)
    assert _extract_salary({"pay_input_ranges": [_range("Pay", 942400000, 942450000)]}, "") == (None, None)
    assert _extract_salary({}, "Pay: $20 - $21") == (None, None)
    assert _extract_salary({}, "Pay: $9,424,000 - $9,424,500") == (None, None)
    assert _extract_salary({"pay_input_ranges": [_range("Pay", 2000, 2100), _range("Salary", 9000000, 11000000)]}, "") == (90000, 110000)
