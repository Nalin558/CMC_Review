# backend/guidelines_rag/pdf_parser.py

import fitz  # PyMuPDF
import re

HEADER_FOOTER_RE = re.compile(
    r"^\s*(ICH\s+[A-Z0-9\(\)\/\-]+.*|Page\s*\d+|^\d{1,3}$)\s*$",
    re.IGNORECASE
)

def extract_text_from_pdf(path: str) -> str:
    """
    Extract text from an ICH PDF using PyMuPDF.

    - Works on scanned PDFs with text layer
    - Handles ICH headers/footers
    - Fixes spacing and broken lines
    """

    doc = fitz.open(path)
    pages = []

    for page in doc:
        text = page.get_text("text")  # best overall extractor
        if not text:
            text = page.get_text()  # fallback

        pages.append(text)

    raw = "\n".join(pages)

    # Remove common headers/footers
    cleaned_lines = []
    for ln in raw.split("\n"):
        if HEADER_FOOTER_RE.match(ln.strip()):
            continue
        cleaned_lines.append(ln)

    cleaned = "\n".join(cleaned_lines)

    # Fix hyphenated line breaks
    cleaned = re.sub(r"-\n\s*", "", cleaned)

    # Normalize spacing
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n\n", cleaned)

    return cleaned.strip()
