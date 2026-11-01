"""Add ~220 SYNTHETIC alumni (is_demo = true) so the network, admin charts and job monitor look busy in a demo.

    python -m backend.scripts.seed_demo_network --yes

Deterministic (same people every run) and safe to re-run: anyone whose email already exists is skipped. Only demo rows are
written. Employers are fictional so several people share a company (that is what makes 'same company' work). Emails use
example.com. Demo people have no LinkedIn profile: the network shows a LinkedIn people-search link for them, never a made-up profile URL. Run Aryan's seed and seed_demo_extras
first if you want those people too. Refuses to run without --yes because it writes to whatever DATABASE_URL points at:
use a scratch/demo database, never a live one.
"""
import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.app.db import get_conn
from backend.app.growth.certs import CERTS
from work.database.config import get_database_url

TODAY = date.today()
NOW = datetime.now(timezone.utc)
COUNT = 220
SEED = 2026

FIRST = ["Aaliyah", "Adrian", "Amara", "Andre", "Angel", "Aniyah", "Brandon", "Camila", "Carlos", "Chloe", "Damian", "Daniela", "Darius", "Destiny",
         "Diego", "Elijah", "Elena", "Emmanuel", "Fatima", "Gabriel", "Imani", "Isaiah", "Jada", "Jasmine", "Javier", "Jayden", "Joel", "Kai", "Kayla",
         "Keisha", "Kevin", "Layla", "Leo", "Malik", "Marisol", "Mateo", "Maya", "Mohamed", "Nadia", "Naomi", "Nia", "Omar", "Priya", "Rafael", "Rosa",
         "Samir", "Sofia", "Tariq", "Valentina", "Xavier", "Yasmin", "Zaire", "Ibrahim", "Aisha", "Jordan", "Taylor", "Morgan", "Riley", "Quinn", "Devin"]
LAST = ["Adeyemi", "Alvarez", "Baptiste", "Bell", "Brooks", "Castillo", "Chen", "Cruz", "Diallo", "Edwards", "Flores", "Garcia", "Gomez", "Hall", "Hernandez",
        "Hughes", "Jackson", "James", "Kamara", "Khan", "Lee", "Lopez", "Martinez", "Mensah", "Mitchell", "Morales", "Nguyen", "Nunez", "Okafor", "Ortiz",
        "Patel", "Perez", "Price", "Ramirez", "Reyes", "Rivera", "Robinson", "Rodriguez", "Sanchez", "Santos", "Singh", "Smith", "Soto", "Taylor", "Thomas",
        "Torres", "Turner", "Vargas", "Walker", "Washington", "Williams", "Wright", "Young", "Zhang", "Bailey", "Coleman", "Foster", "Grant", "Harris", "Ross"]
EMPLOYERS = ["Northwind Labs", "Brightline Systems", "Cobalt Health", "Harbor Analytics", "Maple & Main", "Orbit Logistics", "Summit Fintech", "Kestrel Cloud",
             "Lumen Media", "Granite Bank", "Riverbend Schools", "Pioneer Retail", "Atlas Insurance", "Beacon Software", "Juniper Studio", "Meridian Energy",
             "Quartz Security", "Redwood Labs", "Sable Networks", "Tidewater Travel", "Vanguard Apps", "Willow Education", "Zephyr Robotics", "Ironwood Capital",
             "Bluebird Foods", "Copperline Telecom", "Driftwood Games", "Emberly Health", "Foxglove Design", "Greystone Realty", "Halcyon Pharma", "Indigo Commerce",
             "Jasper Logistics", "Keystone Civic Tech", "Lantern Learning", "Mosaic Partners", "Nimbus Data", "Oakline Hospital", "Prism Creative", "Quill Publishing"]
METROS = [  # weight, cities, employer pool size, pay factor
    (0.46, ["New York, NY", "Brooklyn, NY", "Bronx, NY", "Queens, NY", "Newark, NJ", "Jersey City, NJ", "Hoboken, NJ"], 14, 1.12),
    (0.12, ["Atlanta, GA"], 8, 1.0), (0.10, ["Los Angeles, CA"], 8, 1.05), (0.10, ["Chicago, IL"], 8, 1.0), (0.05, ["San Francisco, CA"], 6, 1.25),
    (0.05, ["Washington, DC"], 6, 1.08), (0.04, ["Houston, TX"], 5, 0.97), (0.03, ["Boston, MA"], 5, 1.08), (0.03, ["Philadelphia, PA"], 5, 0.98),
    (0.02, ["Dallas, TX"], 5, 0.98)]
FAMILIES = [  # weight, key, ladder (junior -> senior), base pay, skills
    (0.34, "software", ["Junior Software Engineer", "Software Engineer", "Full Stack Developer", "Senior Software Engineer"], 62000,
     ["Python", "JavaScript", "React", "Node.js", "SQL", "Git", "Docker", "AWS", "REST APIs", "TypeScript"]),
    (0.18, "data", ["Data Analyst", "Business Analyst", "Data Engineer", "Senior Data Analyst"], 58000,
     ["SQL", "Python", "Excel", "Tableau", "Power BI", "Statistics", "ETL", "Pandas"]),
    (0.16, "support", ["IT Support Specialist", "Help Desk Technician", "Customer Support Specialist", "IT Support Lead"], 46000,
     ["Troubleshooting", "Networking", "Windows", "Linux", "Active Directory", "Ticketing systems", "Hardware"]),
    (0.08, "design", ["UX Designer", "UI Designer", "Product Designer", "Senior Product Designer"], 56000,
     ["Figma", "Prototyping", "User research", "Wireframing", "Accessibility", "Adobe Creative Suite"]),
    (0.08, "product", ["Associate Product Manager", "Product Manager", "Program Manager", "Technical Program Manager"], 66000,
     ["Roadmapping", "Agile", "SQL", "Stakeholder management", "A/B testing", "Jira"]),
    (0.08, "ops", ["Operations Associate", "Operations Coordinator", "Project Coordinator", "Administrative Coordinator"], 44000,
     ["Excel", "Scheduling", "Process improvement", "Reporting", "Communication"]),
    (0.08, "sales", ["Sales Development Representative", "Sales Associate", "Business Development Representative", "Account Executive"], 48000,
     ["CRM", "Prospecting", "Negotiation", "Salesforce", "Cold outreach"]),
]
COHORTS = [(2019, .06), (2020, .08), (2021, .12), (2022, .16), (2023, .18), (2024, .18), (2025, .14), (2026, .08)]
SUPPORT_MESSAGES = ["Laid off recently and looking for my next role.", "Would love help preparing for interviews.", "Looking to move into a more senior role.",
                    "Need advice on negotiating salary.", "Interested in switching fields, where do I start?"]


def build_person(i: int) -> dict:
    """Everything about person #i, drawn from a random source seeded by i alone, so skipping or re-running never changes anyone."""
    rng = random.Random(SEED * 1000 + i)
    pick = lambda options, weights=None: rng.choices(options, weights=weights, k=1)[0]
    first, last = rng.choice(FIRST), rng.choice(LAST)
    metro = pick(METROS, [m[0] for m in METROS])
    city = rng.choice(metro[1])
    pool_start = (i * 3) % (len(EMPLOYERS) - metro[2])
    employers = EMPLOYERS[pool_start:pool_start + metro[2]]
    fam = pick(FAMILIES, [f[0] for f in FAMILIES])
    cohort = pick([c[0] for c in COHORTS], [c[1] for c in COHORTS])
    earliest = date(cohort, 8, 1)
    span = (TODAY - earliest).days
    state = "employed" if span < 330 else pick(["employed", "gap", "none"], [0.88, 0.08, 0.04])
    roles, ladder = [], fam[2]
    if state != "none":
        end = None if state == "employed" else TODAY - timedelta(days=rng.randint(100, 420))
        last_start = (TODAY - timedelta(days=rng.randint(60, 900))) if end is None else end - timedelta(days=rng.randint(180, 700))
        last_start = max(last_start, earliest)
        if end is not None and end <= last_start:
            end, state = None, "employed"
        n = max(1, min(3, ((last_start - earliest).days // 400) + 1))
        base = rng.randint(0, 1)
        cursor, chain = last_start, []
        for k in range(n):
            lvl = min(base + (n - 1 - k), len(ladder) - 1)
            start = last_start if k == 0 else max(earliest, cursor - timedelta(days=rng.randint(360, 720)))
            stop = end if k == 0 else cursor - timedelta(days=1)
            chain.append((ladder[max(0, lvl - 0)], rng.choice(employers) if k == 0 or rng.random() < .6 else None, start, stop, lvl))
            cursor = start
        prev_employer = None
        for title, employer, start, stop, lvl in reversed(chain):  # oldest first
            employer = employer or prev_employer or rng.choice(employers)
            prev_employer = employer
            roles.append({"title": title, "employer": employer, "start": start, "end": stop, "level": lvl})
    salary = []
    for r in roles:
        if rng.random() < (0.95 if r["end"] is None else 0.6):
            mid = fam[3] * (1.12 ** r["level"]) * metro[3] * rng.uniform(0.9, 1.1)
            lo = round(mid * 0.93 / 1000) * 1000
            salary.append((min(r["start"] + timedelta(days=30), TODAY), lo, lo + round(mid * 0.14 / 1000) * 1000))
    if rng.random() < 0.2:
        salary = []
    confirmed = rng.randint(3, 420) if rng.random() < 0.72 else None
    return {"first": first, "last": last, "email": f"{first}.{last}{i}@example.com".lower(), "city": city, "cohort": str(cohort), "fam": fam,
            "roles": roles, "salary": salary, "confirmed": confirmed, "skills": rng.sample(fam[4], rng.randint(3, min(6, len(fam[4])))) if roles else [],
            "certs": [c[0] for c in rng.sample(CERTS[fam[1]], rng.randint(1, min(2, len(CERTS[fam[1]]))))] if roles and rng.random() < .4 else [],
            "visible": rng.random() < 0.82, "linkedin": rng.random() < 0.6, "support": rng.random() < 0.03,
            "action": pick([None, "contacted", "resolved"], [0.93, 0.04, 0.03]),
            "idle_days": rng.randint(30, 300), "support_message": rng.choice(SUPPORT_MESSAGES), "support_days": rng.randint(1, 20),
            "action_days": rng.randint(2, 30)}


def seed(cur) -> tuple[int, int]:
    added = 0
    for i in range(COUNT):
        p = build_person(i)
        cur.execute("SELECT 1 FROM alumni WHERE email = %s", (p["email"],))
        if cur.fetchone():
            continue
        aid = uuid.uuid4()
        touched = NOW - timedelta(days=p["confirmed"] if p["confirmed"] is not None else p["idle_days"])
        cur.execute("INSERT INTO alumni (id, first_name, last_name, email, city, cohort, graduation_year, is_demo, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE,%s)",
                    (aid, p["first"], p["last"], p["email"], p["city"] if p["roles"] else None, p["cohort"], int(p["cohort"]), touched))
        cur.executemany("INSERT INTO work_experience (id, alumni_id, employer, title, location, start_date, end_date, is_current, source) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'demo_seed_network')",
                        [(uuid.uuid4(), aid, r["employer"], r["title"], p["city"], r["start"], r["end"], r["end"] is None) for r in p["roles"]])
        cur.executemany("INSERT INTO salary_records (id, alumni_id, salary_min, salary_max, source, effective_date) VALUES (%s,%s,%s,%s,'self_reported',%s)",
                        [(uuid.uuid4(), aid, lo, hi, when) for when, lo, hi in p["salary"]])
        cur.executemany("INSERT INTO skills (id, alumni_id, name) VALUES (%s,%s,%s)", [(uuid.uuid4(), aid, s) for s in p["skills"]])
        cur.executemany("INSERT INTO certifications (id, alumni_id, name, issuer) VALUES (%s,%s,%s,NULL)", [(uuid.uuid4(), aid, c) for c in p["certs"]])
        if p["roles"]:
            cur.execute("INSERT INTO education (id, alumni_id, school, degree, field_of_study, graduation_year) VALUES (%s,%s,'The Knowledge House','Program graduate',NULL,%s)",
                        (uuid.uuid4(), aid, int(p["cohort"])))
        if p["confirmed"] is not None:
            cur.execute("INSERT INTO resume_uploads (id, alumni_id, file_name, parsed_data, confirmed, uploaded_at) VALUES (%s,%s,'demo_resume.pdf',%s,TRUE,%s)",
                        (uuid.uuid4(), aid, Jsonb({"demo": True}), NOW - timedelta(days=p["confirmed"])))
        cur.execute("INSERT INTO network_profiles (alumni_id, visible, linkedin_url) VALUES (%s,%s,NULL)",
                    (aid, p["visible"] and bool(p["roles"])))
        if p["support"]:
            cur.execute("INSERT INTO support_requests (id, alumni_id, message, created_at) VALUES (%s,%s,%s,%s)",
                        (uuid.uuid4(), aid, p["support_message"], NOW - timedelta(days=p["support_days"])))
        if p["action"]:
            cur.execute("INSERT INTO action_log (id, alumni_id, status, note, created_at) VALUES (%s,%s,%s,%s,%s)",
                        (uuid.uuid4(), aid, p["action"], "Demo follow-up note", NOW - timedelta(days=p["action_days"])))
        added += 1
    # the earlier demo people (Aryan's seed + seed_demo_extras) join the network too, most of them
    cur.execute("SELECT id FROM alumni a WHERE is_demo AND NOT EXISTS (SELECT 1 FROM network_profiles n WHERE n.alumni_id = a.id) ORDER BY email")
    joined = 0
    for row in cur.fetchall():
        rng = random.Random(str(row["id"]))
        cur.execute("INSERT INTO network_profiles (alumni_id, visible, linkedin_url) VALUES (%s,%s,NULL)", (row["id"], rng.random() < 0.85))
        joined += 1
    return added, joined


def main() -> None:
    host = get_database_url().host
    if "--yes" not in sys.argv:
        sys.exit(f"Refusing to run without --yes. This writes SYNTHETIC demo rows to the database at host '{host}'. Use a scratch/demo database, never a live one.")
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        added, joined = seed(cur)
        # earlier versions stored dead example.com LinkedIn placeholders: remove them (demo people get a LinkedIn search link instead)
        cur.execute("UPDATE network_profiles SET linkedin_url = NULL WHERE linkedin_url LIKE 'https://example.com/%'")
        conn.commit()
    print(f"Demo network on host '{host}': {added} new demo alumni, {joined} earlier demo alumni added to the network table.")


if __name__ == "__main__":
    main()
