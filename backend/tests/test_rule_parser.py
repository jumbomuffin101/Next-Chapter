import io

from app.parsing.extract import extract_text
from app.parsing.rule_parser import parse_date, parse_resume_text
from app.parsing.validate import normalize

# Layout A: pipe-separated single-line headers, bullets
RESUME_A = """JANE DOE
Chicago, IL | jane.doe@email.com | (312) 555-0187

EXPERIENCE
Systems Engineer | NASA | Houston, TX                      Mar 2024 – Present
• Built telemetry dashboards for mission operations
• Reduced report time by 30%
Help Desk Technician | City of Chicago | Chicago, IL        06/2021 – 02/2024
• Resolved 40+ tickets per week
• Trained 5 new hires

EDUCATION
Harold Washington College
Associate of Applied Science in Information Technology, 2019 – 2021

SKILLS
Languages: Python, SQL, Bash
Tools: Git, Linux, Excel

CERTIFICATIONS
CompTIA A+ (2021)
AWS Cloud Practitioner
"""

# Layout B: employer line then title+date line, non-tech roles
RESUME_B = """Marcus Johnson
marcus.j@gmail.com  773-555-0142
Oakland, CA

WORK HISTORY
Target Corporation, Oakland, CA
Team Lead   January 2022 to Present
- Supervised a team of 12 cashiers
- Handled cash audits
Starbucks
Barista   Summer 2019 - December 2021
- Served 200+ customers per shift

EDUCATION
Laney College
Certificate in Logistics, Expected May 2020

TECHNICAL SKILLS
Microsoft Office, Customer Service, Inventory Management
"""

# Layout C: title on its own line, company next, dates on the second
RESUME_C = """PRIYA RAMANATHAN
priya@example.org
Atlanta, GA

PROFESSIONAL EXPERIENCE
Junior Data Analyst
Acme Analytics, Inc.   2022 – 2024
Built weekly KPI reports in Excel and SQL
Operations Coordinator
Peach State Logistics   2019 – 2022
Scheduled deliveries for 30 drivers

EDUCATION
Georgia State University
B.S. in Business Administration, 2019
"""


def test_parse_date():
    assert parse_date("Jan 2021") == "2021-01"
    assert parse_date("September 2020") == "2020-09"
    assert parse_date("06/2021") == "2021-06"
    assert parse_date("2019") == "2019"
    assert parse_date("Summer 2019") == "2019-06"
    assert parse_date("Present") is None


def test_layout_a():
    r = parse_resume_text(RESUME_A)
    assert r.full_name == "Jane Doe" and r.email == "jane.doe@email.com"
    assert r.phone and r.location == "Chicago, IL"
    assert len(r.work_experience) == 2
    nasa, desk = r.work_experience
    assert (nasa.title, nasa.employer, nasa.location) == ("Systems Engineer", "NASA", "Houston, TX")
    assert nasa.start_date == "2024-03" and nasa.end_date is None and nasa.is_current
    assert "telemetry" in nasa.description
    assert (desk.title, desk.employer) == ("Help Desk Technician", "City of Chicago")
    assert (desk.start_date, desk.end_date) == ("2021-06", "2024-02")
    assert r.education[0].school == "Harold Washington College"
    assert r.education[0].field_of_study == "Information Technology"
    assert "Python" in r.skills and "Git" in r.skills
    assert any("CompTIA" in c for c in r.certifications)
    assert r.warnings == []


def test_layout_b_non_tech():
    r = parse_resume_text(RESUME_B)
    assert r.full_name == "Marcus Johnson" and r.location == "Oakland, CA"
    lead, barista = r.work_experience
    assert lead.title == "Team Lead" and "Target" in lead.employer and lead.is_current
    assert barista.title == "Barista" and barista.employer == "Starbucks"
    assert barista.start_date == "2019-06" and barista.end_date == "2021-12"
    assert r.education[0].school == "Laney College" and r.education[0].degree == "Certificate"
    assert "Customer Service" in r.skills


def test_layout_c_title_then_company():
    r = parse_resume_text(RESUME_C)
    assert r.full_name == "Priya Ramanathan"
    analyst, coord = r.work_experience
    assert analyst.title == "Junior Data Analyst" and "Acme" in analyst.employer
    assert (analyst.start_date, analyst.end_date) == ("2022", "2024")
    assert coord.title == "Operations Coordinator" and "Peach State" in coord.employer
    assert r.education[0].school == "Georgia State University"
    assert r.education[0].degree.replace(".", "") == "BS"


def test_empty_text_gives_warnings_not_crash():
    r = parse_resume_text("just some words with no structure at all")
    assert r.work_experience == [] and r.warnings


def test_pdf_round_trip():
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in RESUME_A.splitlines():
        c.drawString(50, y, line.replace("•", "-"))
        y -= 14
    c.save()
    text = extract_text(buf.getvalue())
    r = normalize(parse_resume_text(text))
    assert r.full_name == "Jane Doe"
    assert r.work_experience[0].title == "Systems Engineer"
    assert r.work_experience[0].employer == "NASA"


# Real resume layout: "Employer (parenthetical, with commas) City, ST" above "Title   Date range",
# with no separator between employer and city.
LAYOUT_D = """Test Person
Experience
Sigmantic AI (YC S25, Pear VC, Foundation Capital) San Francisco, CA
AI Software Engineering Intern May 2026 – Present
• Cut LLM token costs by 45% by rebuilding the core reasoning engine using Python and LangGraph.
Symbal (Founders Fund) San Francisco, CA (Remote)
Engineering Lead, Financial Platform (Contract) Jan. 2026 – May 2026
• Directed product requirements and end-to-end full-stack architecture to launch a financial AI
benchmarking platform in 6 weeks using Next.js and Java.
Office of Technical Consulting Research @ UIUC Champaign, IL
Lead Software Engineer Oct. 2025 – Apr. 2026
• Owned a secure search platform end-to-end.
Carnegie Mellon University Pittsburgh, PA
Machine Learning Research Intern Jun. 2025 – Aug. 2025
• Developed a streamlined Python signal-processing pipeline using NumPy and SciPy.
"""


def test_layout_d_parenthetical_employer_and_unseparated_city():
    jobs = parse_resume_text(LAYOUT_D).work_experience
    got = [(j.title, j.employer, j.location) for j in jobs]
    assert got == [
        ("AI Software Engineering Intern", "Sigmantic AI", "San Francisco, CA"),
        ("Engineering Lead", "Symbal", "San Francisco, CA"),
        ("Lead Software Engineer", "Office of Technical Consulting Research", "Champaign, IL"),
        ("Machine Learning Research Intern", "Carnegie Mellon University", "Pittsburgh, PA"),
    ]
    assert jobs[0].is_current and jobs[0].start_date == "2026-05"


# Real resume layout: "Company   Remote" above "Title | tech stack   dates", full state name in the
# header, and a "Certifications:" line inside the Skills section.
LAYOUT_E = """Test Person
Hoboken, New Jersey | test@example.edu
EDUCATION
Stevens Institute of Technology – B.S. Computer Science, Minor in Applied Mathematics Aug 2024 – Dec 2027
EXPERIENCE
Department of Computer Science, Stevens Institute of Technology Hoboken, NJ
Course Assistant, Introduction to Computer Science | Python Sep 2026 – Present
• Lead recitations, hold office hours, and grade for 30+ students.
GENIE AI Remote
Software Engineering Intern | NestJS, Node.js, PostgreSQL, Next.js, Docker, Jenkins Oct 2025 – May 2026
• Architected and shipped RESTful APIs for a property analytics platform.
TruClaim Remote
Software Engineering Intern | Flask, Python, PostgreSQL, REST APIs May 2025 – Aug 2025
• Built and deployed backend services for a production claims screening platform.
SKILLS
Languages: Python, TypeScript, Java
Technologies: Docker, CI/CD (GitHub Actions, Jenkins), REST APIs
Certifications: AWS Cloud Practitioner (2025) | AWS AI Practitioner (2026)
"""


def test_layout_e_remote_header_state_name_and_certs_in_skills():
    r = parse_resume_text(LAYOUT_E)
    assert r.location == "Hoboken, NJ"
    got = [(j.title, j.employer, j.location) for j in r.work_experience]
    assert got == [
        ("Course Assistant", "Department of Computer Science", "Hoboken, NJ"),
        ("Software Engineering Intern", "GENIE AI", "Remote"),
        ("Software Engineering Intern", "TruClaim", "Remote"),
    ]
    assert "CI/CD (GitHub Actions, Jenkins)" in r.skills
    assert not any("Practitioner" in s for s in r.skills)
    assert r.certifications == ["AWS Cloud Practitioner", "AWS AI Practitioner"]


# Real resume layout: one employer with a promotion ladder (company once, several titles), right-aligned
# locations/dates, "(cid:N)" bullets from pdfplumber, "B.S., Field" degree, school followed by city,
# and Projects/Interests lines inside Skills.
LAYOUT_F = """Test Person
New York City | test@example.com
Experience
Reddit, Inc. New York, NY
Senior Product Manager March 2026 - Present
(cid:127) Currently leading growth for over 10M daily contributors through growth experiments
Product Manager II Aug 2024 - Mar 2026
(cid:127) Launched AI-powered 0-to-1 Post Check to help users avoid getting posts removed
Product Intern June 2021 - August 2021
(cid:127) Developed content attribution strategy for Reddit creators
Amazon Web Services Remote (COVID)
Solutions Architect Intern June 2020 - August 2020
(cid:127) Developed several technical customer facing guides
Other Experience: Federal Home Loan Bank of Chicago (Application Development Intern), Tennis Coach
Education
University of Illinois at Urbana-Champaign Champaign, IL
B.S., Computer Engineering | Minor in Psychology | GPA: 3.89/4.00 May 2022
Skills
Projects: Resy Bot, Personal Habits Tracker, FPGA Pac Man, RISC-V Pipelined Processor, Linux Kernel OS,
COVID-19 tracker
Core Competencies & Skills: Product Strategy, Data Analysis, Git
Programming Languages: SQL, C++, Python
Interests: French Horn performance, Tennis, Manchester United FC,
Vibe Coding, Film, Electronic Music
"""


def test_layout_f_promotion_ladder_and_noise_lines():
    r = parse_resume_text(LAYOUT_F)
    got = [(j.title, j.employer, j.location) for j in r.work_experience]
    assert got == [
        ("Senior Product Manager", "Reddit Inc.", "New York, NY"),
        ("Product Manager II", "Reddit Inc.", "New York, NY"),
        ("Product Intern", "Reddit Inc.", "New York, NY"),
        ("Solutions Architect Intern", "Amazon Web Services", "Remote"),
    ]
    assert all("cid:" not in (j.description or "") for j in r.work_experience)
    assert "Federal Home Loan" not in r.work_experience[-1].description
    e = r.education[0]
    assert (e.school, e.degree, e.field_of_study) == (
        "University of Illinois at Urbana-Champaign", "B.S.", "Computer Engineering")
    assert sorted(r.skills) == ["C++", "Data Analysis", "Git", "Product Strategy", "Python", "SQL"]
    assert any("city" in w for w in r.warnings)  # no state in the header, so no location
