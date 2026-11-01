
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import engine
from .models import Alumni, WorkExperience, Skill

# Synthetic demo data — not actual TKH alumni records.
DEMO_ALUMNI = [
    {
        "first_name": "Jordan",
        "last_name": "Brooks",
        "city": "New York",
        "cohort": "2022",
        "graduation_year": 2022,
        "roles": [
            ("Junior Developer", "Demo Tech Labs",
             date(2022, 8, 1), date(2024, 5, 31)),
            ("Software Engineer", "Demo Cloud Systems",
             date(2024, 6, 1), None),
        ],
        "skills": ["Python", "React", "PostgreSQL"],
    },
    {
        "first_name": "Taylor",
        "last_name": "Morgan",
        "city": "Atlanta",
        "cohort": "2023",
        "graduation_year": 2023,
        "roles": [
            ("Data Analyst", "Demo Analytics",
             date(2023, 9, 1), None),
        ],
        "skills": ["SQL", "Python", "Tableau"],
    },
    {
        "first_name": "Casey",
        "last_name": "Rivera",
        "city": "Los Angeles",
        "cohort": "2021",
        "graduation_year": 2021,
        "roles": [
            ("IT Support Specialist", "Demo Services",
             date(2021, 6, 1), date(2023, 3, 31)),
            ("Systems Administrator", "Demo Infrastructure",
             date(2023, 4, 1), None),
        ],
        "skills": ["Linux", "Networking", "AWS"],
    },
    {
        "first_name": "Alex",
        "last_name": "Kim",
        "city": "Chicago",
        "cohort": "2024",
        "graduation_year": 2024,
        "roles": [
            ("Frontend Developer", "Demo Digital",
             date(2024, 7, 1), None),
        ],
        "skills": ["React", "JavaScript", "CSS"],
    },
    {
        "first_name": "Morgan",
        "last_name": "Ellis",
        "city": "Newark",
        "cohort": "2022",
        "graduation_year": 2022,
        "roles": [
            ("QA Analyst", "Demo Quality",
             date(2022, 7, 1), None),
        ],
        "skills": ["Testing", "Python", "Selenium"],
    },
    {
        "first_name": "Sam",
        "last_name": "Parker",
        "city": "New York",
        "cohort": "2021",
        "graduation_year": 2021,
        "roles": [
            ("Business Analyst", "Demo Business Group",
             date(2021, 9, 1), date(2023, 12, 31)),
            ("Data Engineer", "Demo Data Systems",
             date(2024, 1, 1), None),
        ],
        "skills": ["SQL", "Python", "ETL"],
    },
    {
        "first_name": "Riley",
        "last_name": "Chen",
        "city": "Atlanta",
        "cohort": "2024",
        "graduation_year": 2024,
        "roles": [
            ("Cloud Support Associate", "Demo Cloud Co",
             date(2024, 8, 1), None),
        ],
        "skills": ["AWS", "Linux", "Docker"],
    },
    {
        "first_name": "Avery",
        "last_name": "Johnson",
        "city": "Los Angeles",
        "cohort": "2023",
        "graduation_year": 2023,
        "roles": [
            ("UX Designer", "Demo Design Studio",
             date(2023, 7, 1), None),
        ],
        "skills": ["Figma", "UX Research", "Prototyping"],
    },
    {
        "first_name": "Jamie",
        "last_name": "Patel",
        "city": "Chicago",
        "cohort": "2022",
        "graduation_year": 2022,
        "roles": [
            ("Junior Engineer", "Demo Software",
             date(2022, 9, 1), date(2024, 9, 30)),
            ("Senior Developer", "Demo Platform",
             date(2024, 10, 1), None),
        ],
        "skills": ["Java", "Spring Boot", "SQL"],
    },
    {
        "first_name": "Drew",
        "last_name": "Williams",
        "city": "Newark",
        "cohort": "2023",
        "graduation_year": 2023,
        "roles": [
            ("Security Analyst", "Demo Cybersecurity",
             date(2023, 8, 1), None),
        ],
        "skills": ["Security", "Linux", "Python"],
    },
]


def seed_database():
    inserted = 0
    skipped = 0

    with Session(engine) as session:
        for record in DEMO_ALUMNI:
            email = (
                f"{record['first_name']}.{record['last_name']}"
                "@example.com"
            ).lower()

            existing = session.scalar(
                select(Alumni).where(Alumni.email == email)
            )

            if existing:
                skipped += 1
                continue

            alumnus = Alumni(
                first_name=record["first_name"],
                last_name=record["last_name"],
                email=email,
                city=record["city"],
                cohort=record["cohort"],
                graduation_year=record["graduation_year"],
                is_demo=True,
            )

            session.add(alumnus)
            session.flush()

            for title, employer, start, end in record["roles"]:
                session.add(
                    WorkExperience(
                        alumni_id=alumnus.id,
                        employer=employer,
                        title=title,
                        location=record["city"],
                        start_date=start,
                        end_date=end,
                        is_current=end is None,
                        source="demo_seed",
                    )
                )

            for skill_name in record["skills"]:
                session.add(
                    Skill(
                        alumni_id=alumnus.id,
                        name=skill_name,
                    )
                )

            inserted += 1

        session.commit()

    print(f"Inserted: {inserted} alumni")
    print(f"Skipped existing: {skipped} alumni")
    print("Database seeding completed successfully!")


if __name__ == "__main__":
    seed_database()
