
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import engine
from .models import Alumni, WorkExperience, ResumeUpload
from .crud import save_confirmed_resume


TEST_RESUME = {
    "full_name": "Jordan Brooks",
    "email": "jordan.brooks@example.com",
    "phone": "555-0100",
    "location": "New York",
    "education": [
        {
            "school": "Demo University",
            "degree": "BS",
            "field_of_study": "Computer Science",
            "start_date": "2018-09-01",
            "end_date": "2022-05-15",
        }
    ],
    "work_experience": [
        {
            "employer": "Demo Tech Labs",
            "title": "Junior Developer",
            "location": "New York",
            "start_date": "2022-08-01",
            "end_date": "2024-05-31",
            "is_current": False,
            "description": "Developed internal applications",
        },
        {
            "employer": "Demo Cloud Systems",
            "title": "Software Engineer",
            "location": "New York",
            "start_date": "2024-06-01",
            "end_date": "2026-09-30",
            "is_current": False,
            "description": "Built backend services",
        },
        {
            "employer": "NASA",
            "title": "Systems Engineer",
            "location": "New York",
            "start_date": "2026-10-01",
            "end_date": None,
            "is_current": True,
            "description": "Developing engineering systems",
        },
    ],
    "skills": [
        "Python",
        "React",
        "PostgreSQL",
        "Systems Engineering",
    ],
    "certifications": ["AWS Cloud Practitioner"],
    "warnings": [],
}


def main():
    with Session(engine) as session:
        alumni = session.scalar(
            select(Alumni).where(
                Alumni.email == "jordan.brooks@example.com"
            )
        )

        if alumni is None:
            raise RuntimeError(
                "Demo alumnus not found. Run seed.py first."
            )

        alumni_id = str(alumni.id)

    print("Testing resume persistence...")

    result = save_confirmed_resume(
        alumni_id=alumni_id,
        parsed_resume=TEST_RESUME,
        file_name="synthetic_jordan_resume.pdf",
    )

    print("Save result:", result)

    with Session(engine) as session:
        jobs = session.scalars(
            select(WorkExperience)
            .where(WorkExperience.alumni_id == alumni_id)
            .order_by(WorkExperience.start_date)
        ).all()

        uploads = session.scalars(
            select(ResumeUpload).where(
                ResumeUpload.alumni_id == alumni_id
            )
        ).all()

        print("\nCareer history:")

        for job in jobs:
            print(
                f"- {job.title} at {job.employer} "
                f"({job.start_date} to {job.end_date})"
            )

        print(f"\nTotal career records: {len(jobs)}")
        print(f"Total resume uploads: {len(uploads)}")

        assert len(jobs) == 3, (
            "Expected three career records without duplicates."
        )

        assert any(
            job.employer == "NASA"
            and job.title == "Systems Engineer"
            and job.is_current
            for job in jobs
        ), "NASA career milestone was not persisted."

    print("\nDatabase integration test passed!")


if __name__ == "__main__":
    main()
