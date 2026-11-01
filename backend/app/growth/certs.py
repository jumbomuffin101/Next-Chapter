"""Certification and learning recommendations: a small curated catalog matched by role type and skills.

These are SUGGESTIONS, not endorsements: names are well-known public certifications and programs, links go to the
provider's landing page, and nothing about price, dates or eligibility is claimed. No ML: plain rules.
"""
from typing import Optional

from ..admin.dashboard import FAMILY_LABELS
from ..jobs.matching import title_family

LEVEL_RANK = {"Foundational": 0, "Associate": 1, "Professional": 2}

# name, provider, level, link (provider landing page), skills that make it a natural next step
CERTS: dict[str, list[tuple]] = {
    "software": [
        ("AWS Certified Cloud Practitioner", "Amazon Web Services", "Foundational", "https://aws.amazon.com/certification/", ("aws", "cloud", "docker")),
        ("Microsoft Azure Fundamentals (AZ-900)", "Microsoft", "Foundational", "https://learn.microsoft.com/credentials/", ("azure", "cloud")),
        ("AWS Certified Developer – Associate", "Amazon Web Services", "Associate", "https://aws.amazon.com/certification/", ("aws", "node", "python", "javascript")),
        ("Certified Kubernetes Application Developer (CKAD)", "Linux Foundation / CNCF", "Associate", "https://training.linuxfoundation.org/certification/", ("docker", "kubernetes", "devops")),
        ("HashiCorp Terraform Associate", "HashiCorp", "Associate", "https://www.hashicorp.com/certification", ("terraform", "aws", "devops")),
    ],
    "data": [
        ("Google Data Analytics Professional Certificate", "Google", "Foundational", "https://grow.google/certificates/", ("excel", "sql", "tableau")),
        ("Microsoft Power BI Data Analyst (PL-300)", "Microsoft", "Associate", "https://learn.microsoft.com/credentials/", ("power bi", "excel", "sql")),
        ("AWS Certified Data Engineer – Associate", "Amazon Web Services", "Associate", "https://aws.amazon.com/certification/", ("sql", "python", "etl", "aws")),
        ("Databricks Certified Data Engineer Associate", "Databricks", "Associate", "https://www.databricks.com/learn/certification", ("spark", "python", "etl", "sql")),
        ("Google Professional Data Engineer", "Google Cloud", "Professional", "https://cloud.google.com/learn/certification", ("sql", "python", "etl")),
    ],
    "support": [
        ("CompTIA A+", "CompTIA", "Foundational", "https://www.comptia.org/certifications", ("hardware", "troubleshooting", "windows")),
        ("Google IT Support Professional Certificate", "Google", "Foundational", "https://grow.google/certificates/", ("troubleshooting", "networking", "linux")),
        ("CompTIA Network+", "CompTIA", "Associate", "https://www.comptia.org/certifications", ("networking", "cisco")),
        ("CompTIA Security+", "CompTIA", "Associate", "https://www.comptia.org/certifications", ("security", "networking")),
        ("Cisco Certified Network Associate (CCNA)", "Cisco", "Associate", "https://learningnetwork.cisco.com/", ("networking", "cisco")),
    ],
    "design": [
        ("Google UX Design Professional Certificate", "Google", "Foundational", "https://grow.google/certificates/", ("figma", "ux", "prototyping")),
        ("Nielsen Norman Group UX Certification", "Nielsen Norman Group", "Professional", "https://www.nngroup.com/ux-certification/", ("ux", "research", "usability")),
        ("Adobe Certified Professional", "Adobe", "Associate", "https://www.adobe.com/learn/certification.html", ("photoshop", "illustrator", "design")),
    ],
    "product": [
        ("Certified Scrum Product Owner (CSPO)", "Scrum Alliance", "Associate", "https://www.scrumalliance.org/", ("agile", "scrum", "roadmap")),
        ("Google Project Management Certificate", "Google", "Foundational", "https://grow.google/certificates/", ("project management", "agile")),
        ("Certified Associate in Project Management (CAPM)", "Project Management Institute", "Foundational", "https://www.pmi.org/certifications", ("project management",)),
        ("Project Management Professional (PMP)", "Project Management Institute", "Professional", "https://www.pmi.org/certifications", ("project management", "stakeholder")),
    ],
    "ops": [
        ("Google Project Management Certificate", "Google", "Foundational", "https://grow.google/certificates/", ("project management", "excel")),
        ("Certified Associate in Project Management (CAPM)", "Project Management Institute", "Foundational", "https://www.pmi.org/certifications", ("project management",)),
        ("Lean Six Sigma Green Belt", "Various accredited providers", "Associate", "https://www.isixsigma.com/", ("process", "excel")),
    ],
    "sales": [
        ("HubSpot Sales Software Certification", "HubSpot Academy", "Foundational", "https://academy.hubspot.com/", ("crm", "prospecting")),
        ("Salesforce Certified Administrator", "Salesforce", "Associate", "https://trailhead.salesforce.com/credentials", ("crm", "salesforce")),
        ("Google Digital Marketing & E-commerce Certificate", "Google", "Foundational", "https://grow.google/certificates/", ("marketing", "analytics")),
    ],
    "other": [
        ("Google IT Support Professional Certificate", "Google", "Foundational", "https://grow.google/certificates/", ()),
        ("Google Data Analytics Professional Certificate", "Google", "Foundational", "https://grow.google/certificates/", ("excel",)),
        ("Google Project Management Certificate", "Google", "Foundational", "https://grow.google/certificates/", ("excel",)),
        ("Microsoft Office Specialist", "Microsoft", "Foundational", "https://learn.microsoft.com/credentials/", ("excel", "word")),
    ],
}

COMMON_SKILLS = {
    "software": ["TypeScript", "SQL", "Docker", "AWS", "CI/CD", "REST APIs", "Testing"],
    "data": ["SQL", "Python", "Tableau", "Power BI", "Excel", "Statistics", "ETL"],
    "support": ["Networking", "Linux", "Active Directory", "Cloud basics", "Ticketing systems", "Troubleshooting"],
    "design": ["Figma", "User research", "Prototyping", "Accessibility", "Design systems"],
    "product": ["Roadmapping", "SQL", "A/B testing", "Agile / Scrum", "Stakeholder management"],
    "ops": ["Excel", "Project management", "Process improvement", "SQL", "Reporting"],
    "sales": ["CRM (Salesforce / HubSpot)", "Prospecting", "Negotiation", "Pipeline management"],
    "other": ["Excel", "Communication", "Project management"],
}

# Learning programs open to adults and career changers. Suggestions only; check each site for current details.
PROGRAMS = [
    {"name": "Google Career Certificates", "provider": "Google / Coursera", "about": "Self-paced certificates in IT support, data analytics, UX design and project management.", "url": "https://grow.google/certificates/"},
    {"name": "freeCodeCamp", "provider": "freeCodeCamp", "about": "Free, self-paced web development, data and security curriculum with projects.", "url": "https://www.freecodecamp.org/"},
    {"name": "Per Scholas", "provider": "Per Scholas", "about": "Nonprofit tuition-free tech training in several US cities, including IT support and cybersecurity.", "url": "https://perscholas.org/"},
    {"name": "Year Up", "provider": "Year Up", "about": "Nonprofit workforce program combining skills training with internships for young adults.", "url": "https://www.yearup.org/"},
]


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("–", "-").split())


def _holds(held_norm: list[str], cert_name: str) -> bool:
    name = _norm(cert_name)
    return any(name in h or h in name for h in held_norm if len(h) >= 4)


def recommend(skills: list[str], held: list[str], role_title: Optional[str]) -> dict:
    family = (title_family(role_title) if role_title else None) or "other"
    skills_norm = [_norm(s) for s in skills]
    held_norm = [_norm(h) for h in held]

    def signal(entry) -> Optional[str]:
        return next((s for s in skills_norm for key in entry[4] if key in s), None)

    # never suggest a lower level from a provider where the person already holds a higher one
    top_held: dict[str, int] = {}
    for e in CERTS[family]:
        if _holds(held_norm, e[0]):
            top_held[e[1]] = max(top_held.get(e[1], -1), LEVEL_RANK[e[2]])
    candidates = [e for e in CERTS[family] if not _holds(held_norm, e[0]) and LEVEL_RANK[e[2]] >= top_held.get(e[1], -1)]
    have_foundational = any(_holds(held_norm, e[0]) and e[2] == "Foundational" for e in CERTS[family])
    ranked = sorted(candidates, key=lambda e: (
        signal(e) is None,
        LEVEL_RANK[e[2]] if not have_foundational else abs(LEVEL_RANK[e[2]] - 1),
        e[0]))
    recommended = []
    for name, provider, level, url, _ in ranked[:4]:
        entry = next(e for e in CERTS[family] if e[0] == name)
        hit = signal(entry)
        why = (f"Builds on your {next((s for s in skills if _norm(s) == hit), hit)} skill" if hit
               else f"A common next step for {FAMILY_LABELS[family].lower()} roles")
        recommended.append({"name": name, "provider": provider, "level": level, "url": url, "why": why})
    skills_to_add = [s for s in COMMON_SKILLS[family] if not any(_norm(s).split(" (")[0] in sk or sk in _norm(s) for sk in skills_norm)][:6]
    return {"family": family, "family_label": FAMILY_LABELS[family], "held": held, "recommended": recommended,
            "skills_to_add": skills_to_add, "programs": PROGRAMS,
            "note": "Suggestions based on your role type and skills, not endorsements. Check each provider for current requirements and cost."}
