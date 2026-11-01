"""Step 1: PDF bytes -> plain text."""
import io
import re
from collections import defaultdict
from typing import Optional

import pdfplumber


class EmptyPdfError(ValueError):
    pass


class PdfLimitError(ValueError):
    pass


MAX_PAGES = 5
MAX_TEXT_CHARS = 100_000


def _is_date_row(row: str) -> bool:
    from .rule_parser import DATE_RANGE, DATE_TOKEN  # imported here: rule_parser itself imports this module
    row = row.strip()
    return bool(DATE_RANGE.fullmatch(row) or DATE_TOKEN.fullmatch(row))


def _column_text(page):
    """Read independent columns top to bottom when a sustained center gutter exists."""
    words = page.extract_words(x_tolerance=2, y_tolerance=3)
    middle = page.width / 2
    gutter = 18
    left, right = [], []
    crossing = 0
    for word in words:
        if word["x1"] < middle - gutter:
            left.append(word)
        elif word["x0"] > middle + gutter:
            right.append(word)
        else:
            crossing += 1
    if len(left) < 12 or len(right) < 12 or crossing > max(3, len(words) // 12):
        return None
    def rows(items):
        groups = defaultdict(list)
        for word in items:
            groups[round(word["top"] / 4)].append(word)
        return [" ".join(w["text"] for w in sorted(group, key=lambda w: w["x0"]))
                for _, group in sorted(groups.items())]
    left_rows, right_rows = rows(left), rows(right)
    # A date column or small sidebar is not a second resume column.
    if sum(len(row) >= 12 for row in left_rows) < 3 or sum(len(row) >= 12 for row in right_rows) < 3:
        return None
    # Right-aligned dates ("Jan 2026 - Present" on every job line) are the most common layout, not a second column:
    # reading them separately would detach each date from its job.
    if 2 * sum(_is_date_row(row) for row in right_rows) >= len(right_rows):
        return None
    return "\n".join(left_rows + right_rows)


def extract_text(pdf_bytes: bytes, max_pages: int = 5) -> str:
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if len(pdf.pages) > min(max_pages, MAX_PAGES):
            raise PdfLimitError("PDF exceeds the 5-page limit. Upload a shorter text-based PDF.")
        for page in pdf.pages:
            parts.append(_column_text(page) or page.extract_text() or "")
    text = "\n".join(parts).strip()
    if len(text) > MAX_TEXT_CHARS:
        raise PdfLimitError("PDF contains too much text. Upload a shorter PDF.")
    if len(text) < 50:
        # Likely a scanned/image PDF. OCR is out of scope for the hackathon;
        # surface a clear error so the UI can ask for a text-based PDF.
        raise EmptyPdfError("No extractable text found (scanned PDF?). Upload a text-based PDF.")
    return text


_LINKEDIN = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/([A-Za-z0-9%_\-]{3,100})", re.I)


def find_linkedin(text: str, links: Optional[list[str]] = None) -> Optional[str]:
    """A LinkedIn PROFILE link (/in/...) from the resume text, else from its hyperlinks. Company pages are ignored."""
    for source in [text, *(links or [])]:
        match = _LINKEDIN.search(source or "")
        if match:
            return f"https://www.linkedin.com/in/{match.group(1)}"
    return None


def pdf_links(pdf_bytes: bytes, max_pages: int = 5) -> list[str]:
    """Hyperlink targets in the PDF (covers a 'LinkedIn' label whose URL is not printed)."""
    links: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:max_pages]:
            links += [h["uri"] for h in page.hyperlinks if h.get("uri")]
    return links
