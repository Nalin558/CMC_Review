import re

# -------------------------------------------------------------------
# 1. Strong ICH/CTD Heading Recognition
# -------------------------------------------------------------------

HEADING_RE = re.compile(
    r"""^\s*(
        (\d+(\.\d+)*\s+.+) |                # 1 / 1.1 / 1.2.3 text
        (\d+(\.[A-Za-z0-9]+)+\s+.+) |       # 3.2.P.3.3 text
        ([IVXLC]{1,4}\.\s+.+) |             # I. / II. / III.
        ([A-Z][A-Z0-9 ,\-]{4,})             # ALL CAPS headings
    )\s*$""",
    re.VERBOSE
)

# NEW → detect TOC lines like: "1.2 Scope ..................... 3"
TOC_LINE_RE = re.compile(r"^\s*\d+(\.\d+)*\s+.+\s+\.{5,}\s+\d+\s*$")

# Remove headers/footers
HEADER_FOOTER_RE = re.compile(
    r"^(Page\s*\d+|ICH\s+[A-Z0-9\(\)\/\-]+.*)$",
    re.IGNORECASE
)

def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n")

    cleaned = []
    for ln in text.split("\n"):
        if HEADER_FOOTER_RE.match(ln.strip()):
            continue
        cleaned.append(ln)

    text = "\n".join(cleaned)
    text = re.sub(r"-\n\s*", "", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def split_into_sections(text: str, max_chars=1200):
    text = clean_text(text)
    lines = text.split("\n")

    sections = []
    current_heading = None
    current_lines = []

    for ln in lines:
        stripped = ln.strip()

        # 1) Treat TOC lines as headings
        if TOC_LINE_RE.match(stripped):
            heading = stripped.split(".")[0]  # turn "1.2 Scope .... 3" into "1.2"
            stripped = heading  # treat as real heading

        # 2) Detect main headings
        if HEADING_RE.match(stripped):
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


def chunk_if_too_large(text: str, max_chars: int):
    if len(text) <= max_chars:
        return [text]

    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    cur = ""

    for p in paragraphs:
        if len(cur) + len(p) < max_chars:
            cur += p + "\n\n"
        else:
            chunks.append(cur.strip())
            cur = p + "\n\n"

    if cur.strip():
        chunks.append(cur.strip())

    return chunks
