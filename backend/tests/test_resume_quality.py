"""Synthetic resume layouts and PDF limits; no production data or database access."""
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.app.parsing.extract import PdfLimitError, extract_text
from backend.app.parsing.router import router
from backend.app.parsing.rule_parser import parse_date, parse_resume_text


CASES = [
    ("student_internships", """Alex Rivera
alex@example.org | Boston, MA
TECHNICAL EXPERIENCE
Software Engineering Intern | Northstar Labs | Boston, MA  Jun 2024 - Aug 2024
• Built accessible reporting tools
Data Analyst Intern | Acme Systems | Remote  Jun 2023 - Aug 2023
• Analyzed survey data
PROJECTS
Project Manager | Student Club | Boston, MA  2022 - Present
EDUCATION
City College
B.S. in Computer Science, 2025
CORE COMPETENCIES
Machine Learning, Data Analysis, Project Management, React Native
LICENSES AND CERTIFICATIONS
AWS Cloud Practitioner (2024)
""", {"name": "Alex Rivera", "jobs": {("Software Engineering Intern", "Northstar Labs"), ("Data Analyst Intern", "Acme Systems")},
         "skills": {"Machine Learning", "Data Analysis", "Project Management", "React Native"}, "certs": {"AWS Cloud Practitioner"}}),
    ("concurrent_roles", """Jordan Lee
jordan@example.org | New York, NY
EMPLOYMENT HISTORY
Software Engineer | Atlas Systems | New York, NY  2021 - Present
• Maintains platform APIs
Freelance Developer | Self-employed | Remote  Mar 2023 - Present
• Builds client sites
EDUCATION
State University
B.A. in Mathematics, 2020
TECHNICAL SKILLS
Python, Amazon Web Services, Microsoft Azure
""", {"name": "Jordan Lee", "jobs": {("Software Engineer", "Atlas Systems"), ("Freelance Developer", "Self-employed")},
         "skills": {"Python", "Amazon Web Services", "Microsoft Azure"}, "certs": set()}),
    ("no_experience", """Morgan Reed
morgan@example.org | Newark, NJ
PROJECTS
Founder | Robotics Club | Newark, NJ  2020 - Present
ACADEMIC BACKGROUND
County College
Associate of Science in Engineering, 2023
PROFESSIONAL SKILLS
Data Analysis, SQL
""", {"name": "Morgan Reed", "jobs": set(), "skills": {"Data Analysis", "SQL"}, "certs": set()}),
    ("duplicates", """Taylor Park
taylor@example.org | Chicago, IL
WORK HISTORY
Systems Engineer | Horizon Labs | Chicago, IL  Jan 2022 - Present
• Supported internal systems
WORK EXPERIENCE
Systems Engineer | Horizon Labs | Chicago, IL  Jan 2022 - Present
• Supported internal systems
SKILLS
Python, python, Machine Learning
CERTIFICATIONS
CompTIA A+ (2023)
CompTIA A+ (2023)
""", {"name": "Taylor Park", "jobs": {("Systems Engineer", "Horizon Labs")},
         "skills": {"Python", "Machine Learning"}, "certs": {"CompTIA A+"}}),
]


@pytest.mark.parametrize("_label,text,expected", CASES)
def test_structured_synthetic_corpus(_label, text, expected):
    result = parse_resume_text(text)
    assert result.full_name == expected["name"]
    assert {(j.title, j.employer) for j in result.work_experience} == expected["jobs"]
    assert len(result.work_experience) == len(expected["jobs"])
    assert set(result.skills) == expected["skills"]
    assert set(result.certifications) == expected["certs"]
    assert len(result.certifications) == len(expected["certs"])


@pytest.mark.parametrize("raw,expected", [
    ("03/14/2020", "2020-03-14"), ("2024-06-15", "2024-06-15"),
    ("09/2022", "2022-09"), ("2023", "2023"),
    ("02/30/2024", None), ("13/2024", None),
])
def test_date_precision_and_validation(raw, expected):
    assert parse_date(raw) == expected


def test_invalid_employment_date_is_flagged_for_review():
    result = parse_resume_text("Alex Rivera\nEXPERIENCE\nEngineer | Atlas Labs 02/30/2024 - Present")
    assert result.work_experience[0].start_date is None
    assert any("dates could not be validated" in warning for warning in result.warnings)


def pdf_with_lines(pages):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    for lines in pages:
        for index, line in enumerate(lines):
            pdf.drawString(40, 750 - index * 18, line)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def test_multi_page_keeps_order_and_sixth_page_is_rejected():
    pages = [["Alex Rivera", "alex@example.org", "EXPERIENCE",
              "Engineer | Atlas Labs | Boston, MA  2021 - 2022"],
             ["EDUCATION", "City College", "B.S. in Engineering, 2020"]]
    parsed = parse_resume_text(extract_text(pdf_with_lines(pages)))
    assert parsed.work_experience[0].employer == "Atlas Labs"
    assert parsed.education[0].school == "City College"
    with pytest.raises(PdfLimitError, match="5-page"):
        extract_text(pdf_with_lines(pages + [["more text"]] * 4))


def test_two_column_pdf_does_not_mix_job_and_education():
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    left = ["Alex Rivera", "alex@example.org", "Boston, MA", "SKILLS",
            "Python, SQL", "Data Analysis", "Machine Learning"]
    right = ["EXPERIENCE", "Software Engineer | Atlas Labs", "Jan 2023 - Present",
             "Built systems for clients", "EDUCATION", "City College", "B.S. in Computing, 2022"]
    for lines, x in ((left, 40), (right, 325)):
        for index, line in enumerate(lines):
            pdf.drawString(x, 750 - index * 20, line)
    pdf.save()
    parsed = parse_resume_text(extract_text(output.getvalue()))
    assert parsed.full_name == "Alex Rivera"
    assert parsed.work_experience[0].employer == "Atlas Labs"
    assert parsed.education[0].school == "City College"


def test_tabular_pdf_keeps_title_employer_and_dates_together():
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    for index, line in enumerate(["Alex Rivera", "alex@example.org", "EXPERIENCE",
                                  "Engineer | Atlas Labs | Boston, MA", "Analyst | Northstar Inc | Boston, MA"]):
        pdf.drawString(40, 750 - index * 25, line)
    pdf.drawString(415, 675, "2023 - Present")
    pdf.drawString(415, 650, "2021 - 2022")
    pdf.save()
    jobs = parse_resume_text(extract_text(output.getvalue())).work_experience
    assert [(job.title, job.employer, job.start_date) for job in jobs] == [
        ("Engineer", "Atlas Labs", "2023"), ("Analyst", "Northstar Inc", "2021")]


def test_right_aligned_dates_are_not_mistaken_for_a_second_column():
    # The most common resume layout: short title lines on the left, a date range right-aligned on every line.
    # Four or more date rows used to look like a second column and were moved away from their jobs.
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    rows = [("Senior Systems Engineer | NASA | Houston, TX", "Jan 2026 - Present"),
            ("Systems Engineer | NASA | Houston, TX", "Mar 2024 - Dec 2025"),
            ("Help Desk Technician | City of Chicago | Chicago, IL", "06/2021 - 02/2024"),
            ("Intern | Acme Corp | Chicago, IL", "Jun 2019 - Aug 2019")]
    for index, line in enumerate(["Jane Doe", "jane.doe@example.com", "EXPERIENCE"]):
        pdf.drawString(40, 750 - index * 20, line)
    for index, (left, right) in enumerate(rows):
        pdf.drawString(40, 690 - index * 20, left)
        pdf.drawString(440, 690 - index * 20, right)
    pdf.save()
    jobs = parse_resume_text(extract_text(output.getvalue())).work_experience
    assert [(job.title, job.employer, job.start_date) for job in jobs] == [
        ("Senior Systems Engineer", "NASA", "2026-01"), ("Systems Engineer", "NASA", "2024-03"),
        ("Help Desk Technician", "City of Chicago", "2021-06"), ("Intern", "Acme Corp", "2019-06")]


def test_empty_corrupt_and_disguised_pdf_are_actionable():
    api = TestClient(FastAPI())
    api.app.include_router(router)
    for name, body, mime, code in [
        ("scan.pdf", pdf_with_lines([[]]), "application/pdf", 422),
        ("broken.pdf", b"%PDF- corrupted", "application/pdf", 422),
        ("fake.pdf", b"<html>not pdf</html>", "application/pdf", 422),
        ("text.txt", b"not a pdf", "text/plain", 400),
    ]:
        response = api.post("/resume/parse", files={"file": (name, body, mime)})
        assert response.status_code == code
        assert response.json()["detail"]
