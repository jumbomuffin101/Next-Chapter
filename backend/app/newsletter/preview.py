"""Offline, synthetic-only preview: python -m backend.app.newsletter.preview --output-dir PATH."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..jobs.matching import MatchProfile
from .content import CohortCounts, Profile, compose
from .render import Newsletter, render
from .links import frontend_url


def demo_newsletter(*, app_url: str | None = None, today=None) -> Newsletter:
    today = today or datetime.now(timezone.utc).date()
    jobs = [{"id": f"example-{i}", "title": title, "company": "Example Employer (synthetic)",
             "location": "New York, NY", "absolute_url": f"https://example.org/jobs/example-{i}",
             "salary_min": None, "salary_max": None,
             "updated_at": datetime.combine(today - timedelta(days=i), datetime.min.time(), timezone.utc)}
            for i, title in enumerate(["Software Engineer", "Backend Developer", "Full Stack Developer"], 1)]
    content = compose(Profile("Jordan (example)", "New York, NY", "2022", True),
                      MatchProfile("Software Engineer", "New York, NY"), jobs,
                      CohortCounts(10, 8, 6), app_url=frontend_url(app_url), today=today, example_jobs=True)
    return render(content)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic-only newsletter files offline; never connects to a database or sends email.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--app-url", help="Override NEWSLETTER_APP_URL for this preview")
    args = parser.parse_args()
    newsletter = demo_newsletter(app_url=args.app_url)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids overwriting teammates' artifacts.
    for name, body in [("next-chapter-monthly.html", newsletter.html), ("next-chapter-monthly.txt", newsletter.text)]:
        with (args.output_dir / name).open("x", encoding="utf-8") as output:
            output.write(body)
    print("Created synthetic HTML and plain-text previews. No database access; no email sent.")


if __name__ == "__main__":
    main()
