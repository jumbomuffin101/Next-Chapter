"""POST /resume/parse  -> returns ParsedResume for the user to review.
POST /resume/confirm/{profile_id} -> atomically persists user-confirmed data.
"""
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.psparser import PSEOF
from pdfplumber.utils.exceptions import PdfminerException

from ..automation.emails import on_resume_confirmed
from .extract import EmptyPdfError, PdfLimitError, extract_text, find_linkedin, pdf_links
from .rule_parser import parse_resume_text
from .schema import ParsedResume
from .store import ConfirmPayload, save_resume
from .validate import normalize

router = APIRouter(prefix="/resume", tags=["resume"])

MAX_BYTES = 5 * 1024 * 1024


@router.post("/parse", response_model=ParsedResume)
async def parse_resume(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Please upload a PDF")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "PDF too large (5MB max)")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(422, "Unable to read this PDF. Upload a valid text-based PDF.")
    try:
        text = extract_text(data)
    except (EmptyPdfError, PdfLimitError) as e:
        raise HTTPException(422, str(e))
    except (PDFSyntaxError, PSEOF, PdfminerException, ValueError):
        raise HTTPException(422, "Unable to read this PDF. Upload a valid text-based PDF.") from None
    resume = normalize(parse_resume_text(text))
    try:
        # The hyperlink's real target is exact; a URL printed in the text can wrap across lines and be cut short.
        resume.linkedin_url = find_linkedin("", pdf_links(data)) or resume.linkedin_url
    except Exception:  # noqa: BLE001 - a link we cannot read must never fail the whole parse
        pass
    return resume


@router.post("/confirm/{profile_id}")
def confirm_resume(profile_id: uuid.UUID, payload: ConfirmPayload):
    """Body: {"resume": <ParsedResume, as edited by the user>, "salary_min": 90000, "salary_max": 110000}
    Salary fields are optional and must be supplied together. Updates alumni.updated_at."""
    try:
        result = save_resume(profile_id, payload)
    except LookupError:
        raise HTTPException(404, "Profile not found")
    except ValueError as e:
        raise HTTPException(422, str(e))
    # First confirmed resume = onboarding done: log the automated emails (switchable on the admin Automation page)
    on_resume_confirmed(profile_id)
    return result
