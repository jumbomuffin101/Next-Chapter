"""Add a SYNTHETIC alumni roster: people in each cohort who have NOT made a profile yet (is_demo = true).

    python -m backend.scripts.seed_demo_roster --yes

When someone in a cohort finishes onboarding, these people get an invite email in the outbox (logged, never sent).
Deterministic (same people every run) and safe to re-run: existing roster emails are skipped. Emails use example.com.
Refuses to run without --yes because it writes to whatever DATABASE_URL points at: use a scratch/demo database, never a live one.
"""
import random
import sys

from backend.app.db import get_conn
from work.database.config import get_database_url

COHORTS = range(2019, 2027)
PER_COHORT = 6
SEED = 2027
FIRST = ["Abena", "Bryan", "Celeste", "Dante", "Esperanza", "Femi", "Gloria", "Hector", "Ines", "Jamal", "Kiara", "Luis", "Mariama", "Nico",
         "Oluwaseun", "Paola", "Rashad", "Selena", "Terrell", "Ursula", "Vanessa", "Wesley", "Ximena", "Yusuf", "Zuri"]
LAST = ["Acosta", "Boateng", "Cabrera", "Dominguez", "Ellis", "Fofana", "Guzman", "Holloway", "Ibarra", "Jenkins", "Kone", "Lindo", "Mejia",
        "Nwosu", "Owusu", "Pena", "Quintero", "Rojas", "Salazar", "Toure", "Ulloa", "Valdez", "Whitaker", "Yeboah", "Zamora"]


def roster() -> list[tuple]:
    rng = random.Random(SEED)
    people, n = [], 0
    for cohort in COHORTS:
        for _ in range(PER_COHORT):
            n += 1
            first, last = rng.choice(FIRST), rng.choice(LAST)
            people.append((f"{first.lower()}.{last.lower()}.r{n}@example.com", first, last, str(cohort)))
    return people


def main() -> None:
    host = get_database_url().host
    if "--yes" not in sys.argv:
        sys.exit(f"Refusing to run without --yes. This writes a SYNTHETIC demo roster to the database at host '{host}'. Use a scratch/demo database, never a live one.")
    with get_conn() as conn, conn.cursor() as cur:
        added = 0
        for email, first, last, cohort in roster():
            cur.execute("""INSERT INTO alumni_roster (email, first_name, last_name, cohort, is_demo) VALUES (%s, %s, %s, %s, TRUE)
                           ON CONFLICT (email) DO NOTHING""", (email, first, last, cohort))
            added += cur.rowcount
        conn.commit()
    print(f"Demo roster on host '{host}': {added} new roster people across {len(COHORTS)} cohorts (no profiles yet).")


if __name__ == "__main__":
    main()
