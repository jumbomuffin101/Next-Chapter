"""Rule-based resume parser (no LLM). Resume text -> ParsedResume.

Strategy: split into sections by heading, then regex/heuristics per section.
It will not be perfect on odd layouts; the user review/edit screen is the safety net,
and `warnings` tells the UI what to double check.
"""
import re
from datetime import date
from typing import Optional

from .schema import Education, ParsedResume, WorkExperience
from .extract import find_linkedin

# ---------------------------------------------------------------- constants
BULLET_CHARS = "•●▪■◦○*·‣⁃-–—"
_PRIVATE_USE = re.compile(r"[-]")

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
SEASONS = {"spring": 1, "summer": 6, "fall": 9, "autumn": 9, "winter": 12}

_MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Spring|Summer|Fall|Autumn|Winter)"
_DATE_TOKEN = rf"(?:(?:{_MONTH_RE})\.?,?\s+\d{{4}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|\d{{1,2}}/\d{{4}}|\d{{4}}-\d{{2}}(?:-\d{{2}})?|\d{{4}}|Present|Current|Now|Ongoing|Today)"
DATE_TOKEN = re.compile(_DATE_TOKEN, re.I)
DATE_RANGE = re.compile(rf"(?P<start>{_DATE_TOKEN})\s*(?:-|–|—|to|until)\s*(?P<end>{_DATE_TOKEN})", re.I)

SECTION_HEADINGS = {
    "experience": {
        "experience", "work experience", "professional experience", "employment",
        "employment history", "work history", "technical experience", "relevant experience", "internships",
        "internship experience", "career history", "professional background",
    },
    "education": {"education", "academic background", "academic history", "education and training", "education & training"},
    "skills": {
        "skills", "technical skills", "core competencies", "technologies", "skills & interests",
        "skills and interests", "key skills", "relevant skills", "skills & abilities", "professional skills",
    },
    "certifications": {
        "certifications", "certificates", "licenses", "licenses & certifications",
        "certifications & training", "certifications and licenses", "licenses and certifications",
    },
    "other": {
        "projects", "summary", "objective", "profile", "professional summary", "awards",
        "honors", "activities", "leadership", "volunteer", "volunteer experience", "publications",
        "interests", "references", "extracurricular activities", "languages", "research",
        "research experience", "achievements", "community involvement", "additional information",
    },
}
HEADING_LOOKUP = {name: sec for sec, names in SECTION_HEADINGS.items() for name in names}

US_STATES = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY"
)
CITY_STATE = re.compile(rf"((?:[A-Z][\w.'\-]+\s){{0,2}}[A-Z][\w.'\-]+),\s*({US_STATES})\b")
_ENDS_WITH_LOCATION = re.compile(rf",\s*(?:{US_STATES})(?:\s*\(\w+\))?$")
# Same alphabetical order as US_STATES (DC sits after Delaware in both)
_STATE_NAMES = "alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|district of columbia|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming"
STATE_ABBR = dict(zip(_STATE_NAMES.split("|"), US_STATES.split("|")))
CITY_STATE_NAME = re.compile(
    rf"((?:[A-Z][\w.'\-]+\s){{0,2}}[A-Z][\w.'\-]+),\s*((?i:{_STATE_NAMES}))\b"
)
EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
PHONE = re.compile(r"(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")

TITLE_WORDS = {
    "engineer", "developer", "programmer", "analyst", "manager", "director", "coordinator",
    "specialist", "associate", "assistant", "intern", "internship", "representative", "rep",
    "technician", "administrator", "supervisor", "lead", "officer", "consultant", "designer",
    "architect", "scientist", "researcher", "teacher", "tutor", "instructor", "cashier",
    "clerk", "teller", "server", "barista", "cook", "driver", "operator", "agent", "advisor",
    "recruiter", "accountant", "bookkeeper", "receptionist", "mechanic", "electrician",
    "nurse", "aide", "counselor", "mentor", "trainee", "apprentice", "fellow", "owner",
    "founder", "president", "vp", "head", "executive", "paralegal", "sales", "support",
    "tester", "qa", "ta", "worker", "attendant", "stocker", "handler", "inspector", "organizer",
}
COMPANY_SUFFIX = re.compile(r"\b(inc|llc|ltd|corp|corporation|co|company|group|labs|technologies|systems|solutions|partners|university|college|hospital|bank|foundation|services)\b\.?", re.I)
SEPARATORS = re.compile(r"\s+[|–—·•@]\s+|\s*\|\s*|\s+-\s+|\s+at\s+|\s{3,}|\t")


# ---------------------------------------------------------------- helpers
def _clean_line(line: str) -> str:
    line = re.sub(r"\(cid:\d+\)", "•", line)  # pdfplumber's name for bullet glyphs it can't decode
    line = _PRIVATE_USE.sub("•", line).replace(" ", " ").replace("–", "–")
    return line.strip()


def _is_bullet(line: str) -> bool:
    return bool(line) and (line[0] in "•●▪■◦○*·‣⁃" or re.match(r"^[-–—]\s", line) is not None)


def _strip_bullet(line: str) -> str:
    return line.lstrip(BULLET_CHARS + " \t").strip()


def _norm_heading(line: str) -> str:
    return re.sub(r"[:\s]+$", "", line.strip()).lower()


def _title_case_ratio(text: str) -> float:
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z.'&\-]*", text) if len(w) > 2 or w.isupper()]
    if not words:
        return 0.0
    return sum(1 for w in words if w[0].isupper()) / len(words)


def _has_title_word(text: str) -> bool:
    return any(w in TITLE_WORDS for w in re.findall(r"[a-z]+", text.lower()))


def _header_like(line: str) -> bool:
    """Could this line be a 'Title / Company / Location' header rather than a bullet sentence?"""
    if not line or _is_bullet(line) or len(line) > 90 or line.endswith((".", ",")):
        return False
    if DATE_RANGE.search(line):
        return False
    return _has_title_word(line) or bool(COMPANY_SUFFIX.search(line)) or (
        _title_case_ratio(line) >= 0.6 and (len(line.split()) <= 8 or bool(_ENDS_WITH_LOCATION.search(line)))
    )


def parse_date(token: str) -> Optional[str]:
    """'Jan 2021' -> '2021-01', '03/2020' -> '2020-03', '2019' -> '2019', 'Present' -> None."""
    t = token.strip().strip(",.").lower()
    if t in {"present", "current", "now", "ongoing", "today"}:
        return None
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})", t)
    if m:
        year = int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0)
        try:
            return date(year, int(m.group(1)), int(m.group(2))).isoformat()
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", t)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        return f"{year}-{month:02d}" if 1 <= month <= 12 else None
    if re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", t):
        try:
            date.fromisoformat(t + ("-01" if len(t) == 7 else ""))
            return t
        except ValueError:
            return None
    m = re.match(r"^([a-z]+)\.?,?\s+(\d{4})$", t)
    if m:
        name = m.group(1)
        month = SEASONS.get(name) or MONTHS.get(name[:3])
        if month:
            return f"{m.group(2)}-{month:02d}"
    m = re.fullmatch(r"\d{4}", t)
    return m.group(0) if m else None


def _is_present(token: str) -> bool:
    return token.strip().lower() in {"present", "current", "now", "ongoing", "today"}


# ---------------------------------------------------------------- sections
def split_sections(lines: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current: Optional[str] = None
    for line in lines:
        key = _norm_heading(line)
        if len(line) <= 45 and key in HEADING_LOOKUP:
            current = HEADING_LOOKUP[key]
            # Several headings can map to the same bucket (e.g. two experience sections)
            sections.setdefault(current, [])
            continue
        if current is None:
            header.append(line)
        else:
            sections[current].append(line)
    return header, sections


# ---------------------------------------------------------------- header / contact
def parse_contact(header_lines: list[str], full_text: str) -> dict:
    email = EMAIL.search(full_text)
    phone = PHONE.search("\n".join(header_lines) or full_text)
    name = None
    for line in header_lines[:6]:
        if EMAIL.search(line) or PHONE.search(line) or any(c.isdigit() for c in line):
            continue
        words = line.replace(",", " ").split()
        if 2 <= len(words) <= 4 and all(re.match(r"^[A-Za-z.'\-]+$", w) for w in words):
            name = " ".join(w.capitalize() if line.isupper() else w for w in words)
            break
    location = None
    for line in header_lines[:8]:
        m = CITY_STATE.search(line)
        if m:
            location = f"{m.group(1)}, {m.group(2)}"
            break
        m = CITY_STATE_NAME.search(line)
        if m:
            location = f"{m.group(1)}, {STATE_ABBR[m.group(2).lower()]}"
            break
    return {
        "full_name": name,
        "email": email.group(0) if email else None,
        "phone": phone.group(0).strip() if phone else None,
        "location": location,
    }


# ---------------------------------------------------------------- experience
_ORG_WORD = re.compile(COMPANY_SUFFIX.pattern + r"|technology|institute|school|academy|department", re.I)


def _trim_city(city: str) -> str:
    """'Mellon University Pittsburgh' -> 'Pittsburgh', 'UIUC Champaign' -> 'Champaign'.

    CITY_STATE grabs up to 3 capitalised words, so employer words can leak in when there is no
    separator. Drop everything up to the last company word or acronym (never the final word).
    """
    words = city.split()
    for i in range(len(words) - 2, -1, -1):
        if _ORG_WORD.fullmatch(words[i]) or (words[i].isupper() and len(words[i]) >= 2):
            return " ".join(words[i + 1:])
    return city


def _split_header_text(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """'Software Engineer | Acme, Inc. | Chicago, IL' -> (title, employer, location)."""
    text = re.sub(r",\s*(Inc|LLC|Ltd|Corp|Co)\b", r" \1", text)
    location = None
    if re.search(r"\bremote\b", text, re.I):
        location = "Remote"
        text = re.sub(r"[\(\[,]?\s*\bremote\b\s*[\)\]]?", " | ", text, flags=re.I)
    m = CITY_STATE.search(text)
    if m:
        city = _trim_city(m.group(1))
        location = f"{city}, {m.group(2)}"
        text = text[: m.end(1) - len(city)] + " " + text[m.end():]
    # "(YC S25, Pear VC)" / "(Contract)": commas inside parentheses must not split the header
    text = re.sub(r"\([^)]*\)", " ", text)
    parts = [p.strip(" ,;:|–—-()[]") for p in re.split(SEPARATORS.pattern + r"|,\s+", text)]
    parts = [p for p in parts if p]
    title = employer = None
    for p in parts:
        if title is None and _has_title_word(p):
            title = p
        elif employer is None:
            employer = p
    if title is None and parts:
        title, employer = parts[0], (parts[1] if len(parts) > 1 else employer)
    # "Acme Corp" matched as a title word? prefer company-looking part as employer
    if title and employer is None and COMPANY_SUFFIX.search(title) and not _has_title_word(title):
        title, employer = None, title
    return title, employer, location


def parse_experience(lines: list[str]) -> list[WorkExperience]:
    # "Other Experience: A, B, C" is a summary line, not part of the last job's description
    for i, l in enumerate(lines):
        if re.match(r"^other experience\s*:", l, re.I):
            lines = lines[:i]
            break
    anchors = [
        i for i, l in enumerate(lines)
        if DATE_RANGE.search(l) and not _is_bullet(l) and len(l) <= 130
    ]
    if not anchors:
        return []

    # header block start for each anchor (up to 2 header-like lines directly above it)
    starts = []
    for n, a in enumerate(anchors):
        floor = anchors[n - 1] if n > 0 else -1
        s, j = a, a - 1
        while j > floor and a - j <= 2 and _header_like(lines[j]):
            s, j = j, j - 1
        starts.append(s)

    entries: list[WorkExperience] = []
    for n, a in enumerate(anchors):
        end = starts[n + 1] if n + 1 < len(anchors) else len(lines)
        m = DATE_RANGE.search(lines[a])
        header_lines = lines[starts[n]:a] + [DATE_RANGE.sub(" ", lines[a], count=1)]
        body_start = a + 1

        # Date-only anchor line: header text sits on the following lines instead
        if not any(h.strip(" ,;:|–—-()") for h in header_lines):
            k = a + 1
            while k < end and k - a <= 2 and _header_like(lines[k]):
                header_lines.append(lines[k])
                k += 1
            body_start = k

        title, employer, location = _split_header_text("   ".join(h for h in header_lines if h.strip()))
        # Two separate lines like "Acme Corp, Chicago IL" / "Software Engineer  2020 - 2021"
        if title and not employer and len(header_lines) > 1:
            title2, employer2, loc2 = _split_header_text(header_lines[0])
            employer = employer2 or title2 if title2 != title else employer
            location = location or loc2
        if not title and not employer:
            continue

        # Promotion ladder: company listed once, several roles under it
        if not employer and entries:
            employer = entries[-1].employer
            location = location or entries[-1].location

        end_tok = m.group("end")
        is_current = _is_present(end_tok)
        desc = "\n".join(_strip_bullet(l) for l in lines[body_start:end] if l.strip())
        entries.append(
            WorkExperience(
                employer=employer or "",
                title=title or "",
                location=location,
                start_date=parse_date(m.group("start")),
                end_date=None if is_current else parse_date(end_tok),
                is_current=is_current,
                description=desc or None,
            )
        )
    unique = {}
    for entry in entries:
        key = (entry.employer.strip().casefold(), entry.title.strip().casefold(), entry.start_date)
        if key not in unique:
            unique[key] = entry
        elif entry.description and not unique[key].description:
            unique[key] = entry
    return list(unique.values())


# ---------------------------------------------------------------- education
_SEPARATORS_NO_AT = re.compile(SEPARATORS.pattern.replace(r"|\s+at\s+", ""))
_DEGREE_WORDS = re.compile(
    r"(?P<deg>(?:Bachelor|Master|Associate)(?:'s|s)?(?:\s+of\s+(?:Science|Arts|Applied Science|Fine Arts|Business Administration|Engineering))?"
    r"|Ph\.?D\.?|Doctorate|Certificate|Diploma|GED)(?:\s+(?:in|of)\s+(?P<field>[^,|–—\n(]+))?",
    re.I,
)
_DEGREE_ABBR = re.compile(
    r"\b(?P<deg>B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|MBA|A\.?A\.?S?|A\.?S\.?)(?:,?\s+(?:in\s+)?(?P<field>[A-Z][A-Za-z&/ ]+?))?(?=\s*(?:,|\||–|—|\(|$|\s{2,}|Expected|\d))"
)
_SCHOOL = re.compile(r"\b(university|college|institute|school|academy|polytechnic)\b", re.I)


_CITY_PREFIX = {"new", "san", "los", "las", "st.", "st", "saint", "fort", "salt", "el", "la", "santa", "baton"}


def _drop_trailing_city(school: str) -> str:
    """'Stevens Institute of Technology Hoboken' -> 'Stevens Institute of Technology' (city precedes ', ST')."""
    words = school.split()
    n = 2 if len(words) > 3 and words[-2].lower() in _CITY_PREFIX else 1
    return " ".join(words[:-n]) if len(words) > n + 1 else school


def parse_education(lines: list[str]) -> list[Education]:
    entries: list[dict] = []
    cur: dict = {}

    def flush():
        nonlocal cur
        if cur.get("school") or cur.get("degree"):
            entries.append(cur)
        cur = {}

    for raw in lines:
        if _is_bullet(raw):
            continue  # GPA / coursework bullets: ignore
        line = raw
        dm = DATE_RANGE.search(line)
        dates: list[str] = []
        if dm:
            start, end = parse_date(dm.group("start")), (None if _is_present(dm.group("end")) else parse_date(dm.group("end")))
        else:
            dates = [parse_date(t.group(0)) for t in DATE_TOKEN.finditer(line)]
            dates = [d for d in dates if d]
            start, end = None, (dates[-1] if dates else None)
        text = DATE_TOKEN.sub(" ", line)
        text = re.sub(r"\b(expected|anticipated|graduat\w*|class of|gpa[: ]*[\d.]+(?:/[\d.]+)?)\b", " ", text, flags=re.I)

        has_school = bool(_SCHOOL.search(text))
        deg = _DEGREE_WORDS.search(text) or _DEGREE_ABBR.search(text)
        if has_school and cur.get("school"):
            flush()
        if deg and cur.get("degree"):
            flush()
        if has_school:
            parts = [p.strip(" ,;|–—-") for p in re.split(_SEPARATORS_NO_AT.pattern + r"|,\s+", text)]
            school = next((p for p in parts if _SCHOOL.search(p)), None)
            if school and re.search(re.escape(school) + rf",\s*(?:{US_STATES})\b", text):
                school = _drop_trailing_city(school)
            cur["school"] = school
        if deg:
            cur["degree"] = deg.group("deg").strip()
            if deg.groupdict().get("field"):
                cur["field_of_study"] = deg.group("field").strip(" ,.")
        if (has_school or deg) and (start or end):
            cur["start_date"], cur["end_date"] = start or cur.get("start_date"), end or cur.get("end_date")
    flush()
    return [
        Education(
            school=e.get("school") or "",
            degree=e.get("degree"),
            field_of_study=e.get("field_of_study"),
            start_date=e.get("start_date"),
            end_date=e.get("end_date"),
        )
        for e in entries
    ]


# ---------------------------------------------------------------- skills / certs
_NON_SKILL_LABELS = {"projects", "interests", "hobbies", "activities", "honors", "awards"}


def parse_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    skipping = False  # inside a wrapped "Interests: ..." line
    for raw in lines:
        line = _strip_bullet(raw)
        label = re.match(r"^([A-Za-z][A-Za-z /&+#\-]{1,30}):\s*", line)
        if label:
            skipping = label.group(1).strip().lower() in _NON_SKILL_LABELS
        if skipping:
            continue
        line = re.sub(r"^[A-Za-z][A-Za-z /&+#\-]{1,30}:\s*", "", line)  # "Languages: Python, ..."
        for piece in re.split(r"[,;|•·](?![^()]*\))", line):  # not inside "(GitHub Actions, Jenkins)"
            piece = piece.strip(" .")
            if 1 < len(piece) <= 40 and not piece.endswith("."):
                skills.append(piece)
    seen, out = set(), []
    for s in skills:
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


_CERT_LABEL = re.compile(r"^certifications?\s*:\s*", re.I)


def parse_certifications(lines: list[str]) -> list[str]:
    out, seen = [], set()
    for raw in lines:
        for piece in re.split(r"\s*\|\s*", _CERT_LABEL.sub("", _strip_bullet(raw))):
            piece = DATE_TOKEN.sub("", piece).strip(" ,;|–—-()")
            piece = re.sub(r"\(\s*\)", "", piece).strip(" ,;|–—-")
            if (2 < len(piece) <= 100 and piece.casefold() not in seen
                    and not re.search(r"\b(?:bachelor|master|ph\.?d|coursework|training course)\b", piece, re.I)):
                out.append(piece)
                seen.add(piece.casefold())
    return out


# ---------------------------------------------------------------- entry point
def parse_resume_text(text: str) -> ParsedResume:
    lines = [l for l in (_clean_line(x) for x in text.splitlines()) if l]
    header, sections = split_sections(lines)
    contact = parse_contact(header, text)

    experience = parse_experience(sections.get("experience", []))
    education = parse_education(sections.get("education", []))
    # "Certifications: ..." sometimes sits inside the Skills section
    skill_lines = [l for l in sections.get("skills", []) if not _CERT_LABEL.match(_strip_bullet(l))]
    cert_lines = sections.get("certifications", []) + [
        l for l in sections.get("skills", []) if _CERT_LABEL.match(_strip_bullet(l))
    ]
    skills = parse_skills(skill_lines)
    certs = parse_certifications(cert_lines)

    warnings: list[str] = []
    if not contact["full_name"]:
        warnings.append("Couldn't find your name; please enter it.")
    if not contact["email"]:
        warnings.append("Couldn't find an email address.")
    if not contact["location"]:
        warnings.append("Couldn't find your city; please enter it so we can match you to nearby jobs.")
    if "experience" not in sections or not experience:
        warnings.append("No work experience detected; please add your roles manually.")
    if "education" not in sections or not education:
        warnings.append("No education detected.")
    if any(not e.title or not e.employer for e in experience):
        warnings.append("Some roles are missing a title or employer; please check them.")
    if any((parse_date(match.group("start")) is None
            or (not _is_present(match.group("end")) and parse_date(match.group("end")) is None))
           for line in sections.get("experience", []) for match in DATE_RANGE.finditer(line)):
        warnings.append("One or more employment dates could not be validated; please review them.")

    return ParsedResume(
        **contact,
        linkedin_url=find_linkedin(text),
        education=education,
        work_experience=experience,
        skills=skills,
        certifications=certs,
        warnings=warnings,
    )
