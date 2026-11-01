"""Add ONE hand-written SYNTHETIC alum for the demo video: Catherine Kennedy, cohort 2020, Financial Analyst, tagged "Just joined".

    python -m backend.scripts.seed_demo_featured --yes

She is a demo row (is_demo = true) with a sign-up record from today, which is what the People tab's "Just joined" tag looks at, so the
tag shows for a week after you run this. Safe to re-run: the sign-up date is refreshed to now. Refuses to run without --yes because it
writes to whatever DATABASE_URL points at: use a scratch/demo database, never a live one.
"""
import sys
import uuid
from datetime import date

from backend.app.db import get_conn
from work.database.config import get_database_url

EMAIL = "catherine.kennedy@example.com"


def main() -> None:
    host = get_database_url().host
    if "--yes" not in sys.argv:
        sys.exit(f"Refusing to run without --yes. This writes a SYNTHETIC demo alum to the database at host '{host}'. Use a scratch/demo database, never a live one.")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM alumni WHERE lower(email) = %s", (EMAIL,))
        row = cur.fetchone()
        if row is None:
            alumni_id = uuid.uuid4()
            cur.execute("""INSERT INTO alumni (id, first_name, last_name, email, city, cohort, graduation_year, is_demo)
                           VALUES (%s, 'Catherine', 'Kennedy', %s, 'New York, NY', '2020', 2020, TRUE)""", (alumni_id, EMAIL))
            cur.execute("""INSERT INTO work_experience (id, alumni_id, employer, title, location, start_date, is_current, description, source)
                           VALUES (%s, %s, 'Harbor Capital', 'Financial Analyst', 'New York, NY', %s, TRUE,
                                   'Budgeting, forecasting and monthly reporting', 'demo_seed_featured')""",
                        (uuid.uuid4(), alumni_id, date(2025, 6, 1)))
            for skill in ("Excel", "SQL", "Financial modeling", "Tableau"):
                cur.execute("INSERT INTO skills (id, alumni_id, name) VALUES (%s, %s, %s)", (uuid.uuid4(), alumni_id, skill))
        else:
            alumni_id = row[0]
        cur.execute("""INSERT INTO signup_sources (alumni_id, source, cohort) VALUES (%s, 'room', '2020')
                       ON CONFLICT (alumni_id) DO UPDATE SET created_at = now()""", (alumni_id,))
        conn.commit()
    print(f"Featured demo alum on host '{host}': Catherine Kennedy (2020, Financial Analyst, New York) is tagged Just joined for the next 7 days.")


if __name__ == "__main__":
    main()
