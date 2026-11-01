"""Job title -> closest BLS occupation (SOC code). First pattern that matches wins, so specific ones come first."""
import re
from typing import Optional

OCCUPATIONS = [
    ("11-3021", "Computer and Information Systems Managers", r"\b(it|engineering|technology|software|data) (manager|director)\b|head of (engineering|it|technology)|\bcto\b|\bcio\b"),
    ("15-1212", "Information Security Analysts", r"secur|cyber|penetration|\bsoc analyst"),
    ("15-2051", "Data Scientists", r"data scien|machine learning|\bml engineer|\bai engineer|data analyst|analytics|business intelligence|\bbi (analyst|developer)"),
    ("15-1242", "Database Administrators and Architects", r"database|\bdba\b"),
    ("15-1241", "Computer Network Architects", r"network architect|cloud architect|solutions architect"),
    ("15-1244", "Network and Computer Systems Administrators", r"systems? admin|sysadmin|network (admin|engineer)|cloud engineer|devops|site reliability|\bsre\b|infrastructure"),
    ("15-1253", "Software Quality Assurance Analysts and Testers", r"\bqa\b|quality assurance|\btest(er|ing)?\b|\bsdet\b"),
    ("15-1255", "Web and Digital Interface Designers", r"\bux\b|\bui\b|product designer|interaction designer|web designer"),
    ("15-1254", "Web Developers", r"web developer|front[- ]?end"),
    ("15-1252", "Software Developers", r"software|developer|programmer|full[- ]?stack|back[- ]?end|mobile|\bios\b|android|engineer"),
    ("15-1211", "Computer Systems Analysts", r"systems analyst|business analyst|\bit analyst"),
    ("43-4051", "Customer Service Representatives", r"customer (service|success|support|care)|call center"),
    ("15-1231", "Computer Network Support Specialists", r"network (support|technician)|\bnoc\b"),
    ("15-1232", "Computer User Support Specialists", r"help ?desk|\bit (support|specialist|technician)|desktop support|technical support|support (specialist|technician|analyst)"),
    ("13-1082", "Project Management Specialists", r"project manager|program manager|product manager|product owner|scrum"),
    ("27-1024", "Graphic Designers", r"graphic|visual designer"),
    ("13-1161", "Market Research Analysts and Marketing Specialists", r"marketing|\bseo\b|social media|content (strategist|specialist)"),
    ("41-3091", "Sales Representatives of Services", r"sales|account (executive|manager)|business development"),
]
_COMPILED = [(soc, name, re.compile(pattern, re.I)) for soc, name, pattern in OCCUPATIONS]


def occupation_for(title: Optional[str]) -> Optional[tuple[str, str]]:
    """(soc, name) of the closest BLS occupation, or None when the title matches nothing we track."""
    for soc, name, pattern in _COMPILED:
        if title and pattern.search(title):
            return soc, name
    return None
