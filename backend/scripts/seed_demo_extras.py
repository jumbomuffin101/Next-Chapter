"""Add SYNTHETIC demo alumni (is_demo = true) so the admin charts, map and Needs-action page have data to show.

    python -m backend.scripts.seed_demo_extras --yes

Run Aryan's seed first (python -m work.database.seed). This script only ever inserts demo rows, is safe to re-run
(it skips people who already exist), and never touches real alumni. It refuses to run without --yes because it writes
to whatever DATABASE_URL points at: use a scratch/demo database, never a live one.
"""
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.app.db import get_conn
from work.database.config import get_database_url

NOW = datetime.now(timezone.utc)
D = date.fromisoformat

# name, city, cohort, roles [(title, employer, start, end|None)], salary [(date, min, max)], confirmed_days_ago, extras
EXTRAS = [
    ("Maya Torres", "Brooklyn, NY", "2026", [("Junior Software Engineer", "Demo Fintech", "2026-03-01", None)], [("2026-04-01", 65000, 75000)], 12, {}),
    ("Devon Reed", "Newark, NJ", "2026", [("IT Support Specialist", "Demo Schools", "2026-02-01", None)], [("2026-03-01", 48000, 56000)], 20, {}),
    ("Priya Nair", "Jersey City, NJ", "2026", [("Data Analyst Intern", "Demo Bank", "2026-01-05", "2026-04-30")], [], 40, {}),
    ("Omar Hassan", "New York, NY", "2026", [], [], None, {"no_profile": True}),
    ("Lena Brooks", "Atlanta, GA", "2025", [("Help Desk Technician", "Demo Health", "2025-06-01", "2026-01-31"), ("Systems Administrator", "Demo Health", "2026-02-01", None)],
     [("2025-07-01", 45000, 52000), ("2026-03-01", 58000, 66000)], 30, {}),
    ("Marcus Webb", "Atlanta, GA", "2025", [("QA Analyst", "Demo Logistics", "2025-05-01", None)], [("2025-06-01", 52000, 60000), ("2026-06-01", 60000, 70000)], 200, {}),
    ("Sofia Alvarez", "Los Angeles, CA", "2025", [("UX Designer", "Demo Studio", "2025-08-01", None)], [("2025-09-01", 60000, 70000)], 15, {}),
    ("Jamal Carter", "Chicago, IL", "2025", [("Junior Developer", "Demo Apps", "2025-04-01", "2025-12-15")], [("2025-05-01", 55000, 62000)], 70,
     {"support": "Laid off in December and looking for a new role. Could use help with interviews."}),
    ("Hannah Lee", "New York, NY", "2024", [("Software Engineer", "Demo Cloud", "2024-09-01", None)], [("2024-10-01", 70000, 80000), ("2025-10-01", 84000, 96000)], 25, {}),
    ("Isaac Moore", "Washington, DC", "2024", [("Cloud Support Associate", "Demo Gov Tech", "2024-08-01", "2025-09-30"), ("Cloud Engineer", "Demo Gov Tech", "2025-10-01", None)],
     [("2024-09-01", 58000, 66000), ("2025-11-01", 80000, 90000)], 60, {}),
    ("Grace Kim", "San Francisco, CA", "2023", [("Data Engineer", "Demo Data Co", "2023-09-01", None)],
     [("2023-10-01", 85000, 95000), ("2024-10-01", 100000, 115000), ("2025-10-01", 118000, 134000)], 10, {}),
    ("Tyrone Banks", "Houston, TX", "2023", [("Security Analyst", "Demo Secure", "2023-07-01", None)], [("2023-08-01", 60000, 70000), ("2025-08-01", 76000, 88000)], 400, {}),
    ("Elena Petrov", "Boston, MA", "2023", [("Business Analyst", "Demo Retail", "2023-06-01", "2024-12-31"), ("Associate Product Manager", "Demo Retail", "2025-01-01", None)],
     [("2023-07-01", 62000, 70000), ("2025-02-01", 85000, 95000)], 33, {}),
    ("Chris Daniels", "New York, NY", "2022", [("Support Engineer", "Demo SaaS", "2022-08-01", "2024-02-29"), ("Software Engineer", "Demo SaaS", "2024-03-01", None)],
     [("2022-09-01", 55000, 63000), ("2024-04-01", 90000, 100000)], 18, {}),
    ("Aisha Khan", "Philadelphia, PA", "2022", [("IT Administrator", "Demo University", "2022-07-01", None)], [("2022-08-01", 52000, 60000), ("2025-01-01", 68000, 78000)], 90, {}),
    ("Noah Simmons", "Dallas, TX", "2022", [("Sales Development Representative", "Demo Software", "2022-09-01", "2023-12-31"), ("Account Executive", "Demo Software", "2024-01-01", None)],
     [("2022-10-01", 50000, 60000), ("2024-02-01", 72000, 84000)], 45, {}),
    ("Zoe Martin", "New York, NY", "2021", [("Front End Developer", "Demo Media", "2021-07-01", "2023-06-30"), ("Senior Developer", "Demo Media", "2023-07-01", None)],
     [("2021-08-01", 60000, 70000), ("2023-08-01", 95000, 110000), ("2025-08-01", 120000, 140000)], 14, {}),
    ("Ethan Scott", "Newark, NJ", "2021", [("Help Desk Technician", "Demo ISP", "2021-06-01", "2022-12-31"), ("Network Administrator", "Demo ISP", "2023-01-01", None)],
     [("2021-07-01", 42000, 48000), ("2023-02-01", 62000, 70000)], 500, {}),
    ("Camille Dubois", "Los Angeles, CA", "2021", [("Operations Associate", "Demo Events", "2021-09-01", None)], [], None, {"bare": True}),
    ("Victor Nguyen", "Chicago, IL", "2021", [("Data Analyst", "Demo Insurance", "2021-08-01", "2024-03-15")], [("2021-09-01", 55000, 63000)], 365, {}),
]

SKILLS = {"software": ["Python", "JavaScript", "Git"], "data": ["SQL", "Python", "Tableau"], "support": ["Networking", "Linux", "Troubleshooting"],
          "design": ["Figma", "UX Research"], "sales": ["CRM", "Prospecting"], "other": ["Communication", "Excel"]}


def family(title: str) -> str:
    t = title.lower()
    for key, words in (("software", ("software", "developer", "engineer")), ("data", ("data", "analyst")), ("design", ("design",)),
                       ("sales", ("sales", "account")), ("support", ("support", "help desk", "administrator", "security", "qa"))):
        if any(w in t for w in words):
            return key
    return "other"


def seed_extras(cur) -> int:
    added = 0
    for name, city, cohort, roles, salary, confirmed, extra in EXTRAS:
        first, last = name.split(" ", 1)
        email = f"{first}.{last}@example.com".lower().replace(" ", "")
        cur.execute("SELECT 1 FROM alumni WHERE lower(email) = %s", (email,))
        if cur.fetchone():
            continue
        aid = uuid.uuid4()
        updated = NOW - timedelta(days=confirmed if confirmed is not None else 250)
        cur.execute("INSERT INTO alumni (id, first_name, last_name, email, city, cohort, graduation_year, is_demo, updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE,%s)", (aid, first, last, email, None if extra.get("no_profile") else city, cohort, int(cohort), updated))
        for title, employer, start, end in roles:
            cur.execute("INSERT INTO work_experience (id, alumni_id, employer, title, location, start_date, end_date, is_current, source) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'demo_seed_extras')", (uuid.uuid4(), aid, employer, title, city, D(start), D(end) if end else None, end is None))
        if roles and not extra.get("bare"):
            for skill in SKILLS[family(roles[-1][0])]:
                cur.execute("INSERT INTO skills (id, alumni_id, name) VALUES (%s,%s,%s)", (uuid.uuid4(), aid, skill))
            cur.execute("INSERT INTO education (id, alumni_id, school, degree, field_of_study, graduation_year) VALUES (%s,%s,'Demo University','Certificate',NULL,%s)",
                        (uuid.uuid4(), aid, int(cohort)))
        for when, lo, hi in salary:
            cur.execute("INSERT INTO salary_records (id, alumni_id, salary_min, salary_max, source, effective_date) VALUES (%s,%s,%s,%s,'self_reported',%s)",
                        (uuid.uuid4(), aid, lo, hi, D(when)))
        if confirmed is not None:
            cur.execute("INSERT INTO resume_uploads (id, alumni_id, file_name, parsed_data, confirmed, uploaded_at) VALUES (%s,%s,'demo_resume.pdf',%s,TRUE,%s)",
                        (uuid.uuid4(), aid, Jsonb({"demo": True}), NOW - timedelta(days=confirmed)))
        if extra.get("support"):
            cur.execute("INSERT INTO support_requests (id, alumni_id, message, created_at) VALUES (%s,%s,%s,%s)",
                        (uuid.uuid4(), aid, extra["support"], NOW - timedelta(days=2)))
        added += 1
    return added


def enrich_existing_demo(cur) -> int:
    """Aryan's 10 demo alumni have roles but no salary history or confirmed resume: give them some (demo rows only)."""
    cur.execute("""SELECT a.id, min(w.start_date) AS first_start, max(w.start_date) AS last_start FROM alumni a
                   JOIN work_experience w ON w.alumni_id = a.id
                   WHERE a.is_demo AND NOT EXISTS (SELECT 1 FROM salary_records r WHERE r.alumni_id = a.id)
                     AND w.source = 'demo_seed' GROUP BY a.id ORDER BY a.email""")
    people = cur.fetchall()
    for i, p in enumerate(people):
        base = 50000 + i * 4000
        first = p["first_start"] + timedelta(days=30)
        cur.execute("INSERT INTO salary_records (id, alumni_id, salary_min, salary_max, source, effective_date) VALUES (%s,%s,%s,%s,'self_reported',%s)",
                    (uuid.uuid4(), p["id"], base, base + 8000, first))
        if p["last_start"] > p["first_start"]:
            cur.execute("INSERT INTO salary_records (id, alumni_id, salary_min, salary_max, source, effective_date) VALUES (%s,%s,%s,%s,'self_reported',%s)",
                        (uuid.uuid4(), p["id"], round(base * 1.3), round(base * 1.3) + 9000, p["last_start"] + timedelta(days=30)))
        if i % 3 != 0:
            cur.execute("INSERT INTO resume_uploads (id, alumni_id, file_name, parsed_data, confirmed, uploaded_at) VALUES (%s,%s,'demo_resume.pdf',%s,TRUE,%s)",
                        (uuid.uuid4(), p["id"], Jsonb({"demo": True}), NOW - timedelta(days=10 + i * 22)))
    return len(people)


def main() -> None:
    host = get_database_url().host
    if "--yes" not in sys.argv:
        sys.exit(f"Refusing to run without --yes. This writes SYNTHETIC demo rows to the database at host '{host}'. "
                 "Use a scratch/demo database, never a live one.")
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        enriched = enrich_existing_demo(cur)
        added = seed_extras(cur)
        conn.commit()
    print(f"Demo extras on host '{host}': {added} new demo alumni, {enriched} existing demo alumni enriched.")


if __name__ == "__main__":
    main()
