import fitz  # PyMuPDF

def extract_text_from_pdf(path: str) -> str:
    """
    Extract text from a PDF using PyMuPDF (fitz).
    Returns a single big string with page texts joined by newlines.
    """
    doc = None
    try:
        doc = fitz.open(path)
        pages = []
        for page in doc:
            # "text" gives reading-order text, better than "blocks" for guidelines
            text = page.get_text("text") or ""
            pages.append(text)
        return "\n".join(pages)
    finally:
        if doc is not None:
            doc.close()
