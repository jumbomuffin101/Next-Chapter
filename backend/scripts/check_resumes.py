"""Live resume check: python scripts/check_resumes.py path/to/resume1.pdf [more.pdf ...]

Prints what the parser extracted so you can eyeball failures. Add any miss to
tests/test_rule_parser.py as a text fixture and fix the parser.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.parsing.extract import EmptyPdfError, extract_text  # noqa: E402
from app.parsing.rule_parser import parse_resume_text  # noqa: E402
from app.parsing.validate import normalize  # noqa: E402

for path in [a for a in sys.argv[1:] if not a.startswith('--')]:
    print("=" * 70, f"\n{path}")
    try:
        text = extract_text(Path(path).read_bytes())
    except EmptyPdfError as e:
        print("  EXTRACT FAILED:", e)
        continue
    r = normalize(parse_resume_text(text))
    print(f"  {r.full_name} | {r.email} | {r.phone} | {r.location}")
    for w in r.work_experience:
        end = "Present" if w.is_current else w.end_date
        print(f"  WORK  {w.title!r} @ {w.employer!r} ({w.location}) {w.start_date} -> {end}")
    for e in r.education:
        print(f"  EDU   {e.school!r} | {e.degree} | {e.field_of_study} | {e.start_date}->{e.end_date}")
    print(f"  SKILLS {len(r.skills)}: {', '.join(r.skills[:12])}")
    print(f"  CERTS  {r.certifications}")
    print(f"  WARNINGS {r.warnings}")
    if "--text" in sys.argv:
        print("--- raw extracted text ---\n" + text)
