# backend/cmc_rag/section_parser.py

import re

# -------------------------------------------------------------------
# 1. Strong CTD / pharma Heading Recognition
# -------------------------------------------------------------------
# Detects headings like:
#  - 3.2.P.3.3 Control Strategy
#  - 1.2 Background
#  - II. INTRODUCTION
#  - MANUFACTURING PROCESS
HEADING_RE = re.compile(
    r"""^\s*(
        (\d+(\.\d+)*\s+.+) |               # 1 / 1.1 / 1.2.3 text
        (\d+(\.[A-Za-z0-9]+)+\s+.+) |      # 3.2.P.3.3 text
        ([IVXLC]{1,4}\.\s+.+) |            # I. / II. / III.
        ([A-Z][A-Z0-9 ,\-]{4,})            # ALL CAPS headings (min length 4)
    )\s*$""",
    re.VERBOSE,
)

# Many PDFs repeat headers/footers: ICH code, page numbers, EMA assessment reports, etc.
HEADER_FOOTER_RE = re.compile(
    r"^\s*(ICH\s+[A-Z0-9\(\)\/\-]+.*|Page\s*\d+|^\d{1,3}$|Assessment\s+report\s+EMA\/\d+\/\d+\s+Page\s+\d+\/\d+)\s*$",
    re.IGNORECASE,
)


# -------------------------------------------------------------------
# 2. Cleaning
# -------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Sanitize extracted text for consistent chunking."""
    text = text.replace("\r\n", "\n")

    # Remove headers/footers
    cleaned_lines = []
    for ln in text.split("\n"):
        if HEADER_FOOTER_RE.match(ln.strip()):
            continue
        cleaned_lines.append(ln)

    text = "\n".join(cleaned_lines)

    # Fix hyphenated line breaks
    text = re.sub(r"-\n\s*", "", text)

    # Normalize multiple newlines
    text = re.sub(r"\n{2,}", "\n\n", text)

    # Normalize spaces
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


# -------------------------------------------------------------------
# 3. Section Splitting Logic
# -------------------------------------------------------------------

def split_into_sections(text: str, max_chars: int = 1200):
    """
    Splits CMC / CTD text into structured sections.
    Returns clean chunks with headings on top.
    """
    text = clean_text(text)
    lines = text.split("\n")

    sections = []
    current_heading = None
    current_lines = []

    for ln in lines:
        stripped = ln.strip()
        if HEADING_RE.match(stripped):
            # Push previous section
            if current_heading and current_lines:
                full = current_heading + "\n" + "\n".join(current_lines)
                sections.extend(chunk_if_too_large(full, max_chars))

            current_heading = stripped
            current_lines = []
        else:
            if current_heading:
                current_lines.append(ln)

    # Final section
    if current_heading and current_lines:
        full = current_heading + "\n" + "\n".join(current_lines)
        sections.extend(chunk_if_too_large(full, max_chars))

    return sections


# -------------------------------------------------------------------
# 4. Chunk large sections
# -------------------------------------------------------------------

def chunk_if_too_large(text: str, max_chars: int):
    """Split oversized sections but preserve semantic continuity."""
    if len(text) <= max_chars:
        return [text]

    # Split by paragraphs
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = ""

    for p in paragraphs:
        if len(current) + len(p) < max_chars:
            current += p + "\n\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            current = p + "\n\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks
