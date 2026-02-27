from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
import os
import uuid
import shutil
import fitz  # PyMuPDF
from xhtml2pdf import pisa
import re
import html as html_lib
from typing import Optional

# =====================================================
# APP SETUP
# =====================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = "temp"
os.makedirs(BASE_DIR, exist_ok=True)

FILES = {}

# =====================================================
# MODELS
# =====================================================

class SaveHtmlRequest(BaseModel):
    file_id: str
    html: str

class SearchRequest(BaseModel):
    file_id: str
    query: str

class GetPageRequest(BaseModel):
    file_id: str
    page_number: int

class SavePageRequest(BaseModel):
    file_id: str
    page_number: int
    html: str

# =====================================================
# PDF -> HTML (flowable) with paragraph grouping & metrics
# =====================================================

def pdf_page_to_html_flowable(pdf_path: str, page_num: Optional[int] = None) -> str:
    """
    Convert one PDF page into flowable HTML that reflows and
    tries to closely match content width. Group lines into paragraphs
    where appropriate (reduce one-line-per-p tag behavior).
    """
    doc = fitz.open(pdf_path)
    output_html = []

    if page_num is not None:
        pages_to_process = [page_num]
    else:
        pages_to_process = range(len(doc))

    for page_idx in pages_to_process:
        page = doc[page_idx]
        page_rect = page.rect
        page_width_pt = page_rect.width
        page_height_pt = page_rect.height

        # Use text blocks to compute content area
        blocks = page.get_text("dict")["blocks"]
        text_blocks = [b for b in blocks if b.get("type", -1) == 0]

        if text_blocks:
            min_x = min(b["bbox"][0] for b in text_blocks)
            max_x = max(b["bbox"][2] for b in text_blocks)
        else:
            min_x = 72
            max_x = page_width_pt - 72

        # Minimal buffers
        left_margin_pt = max(12, min_x - 0.5)
        right_margin_pt = max(12, page_width_pt - max_x - 0.5)
        content_width_pt = page_width_pt - left_margin_pt - right_margin_pt
        content_width_in = content_width_pt / 72.0

        # container
        output_html.append(
            f'<div class="pdf-page-container" data-page="{page_idx+1}" style="width: {content_width_in}in; max-width: {content_width_in}in; margin: 0 auto; padding: 0; box-sizing: border-box;">'
        )

        # Process blocks sorted by y coordinate
        text_blocks.sort(key=lambda b: b["bbox"][1])

        for block in text_blocks:
            # For each block, gather lines; grouping small lines together into paragraphs
            lines = block.get("lines", [])
            paragraph_buffer = []
            buffer_max_font = 0
            buffer_is_heading = False

            def flush_buffer():
                nonlocal paragraph_buffer, buffer_max_font, buffer_is_heading
                if not paragraph_buffer:
                    return
                
                # Get the text content to check if it's a page number
                inner_html = "".join(paragraph_buffer)
                text_content = re.sub(r'<[^>]+>', '', inner_html)  # Strip HTML tags
                
                # Detect if this is a page number (e.g., "Page 21/195" or just "21/195")
                is_page_number = bool(re.search(r'(Page\s+)?\d+\s*/\s*\d+', text_content, re.IGNORECASE))
                
                # Determine tag
                tag = "p" if not buffer_is_heading else "h3"
                style_parts = []
                
                # If it's a page number, align right
                if is_page_number:
                    style_parts.append("text-align: right;")
                else:
                    style_parts.append("text-align: justify;")
                
                style_parts.append("margin-top: 0;")
                style_parts.append("margin-bottom: 4pt;")
                style_parts.append("line-height: 1.25;")
                style_parts.append(f"font-size: {buffer_max_font}pt;")
                style = ' style="' + ' '.join(style_parts) + '"'
                output_html.append(f"<{tag}{style}>{inner_html}</{tag}>")
                paragraph_buffer = []
                buffer_max_font = 0
                buffer_is_heading = False

            for line in lines:
                # Build the line text and detect font/formatting
                max_font_size = 0
                is_bold = False
                is_italic = False
                line_text = ""
                spans_html = []

                for span in line.get("spans", []):
                    text = html_lib.escape(span.get("text", ""))
                    if not text.strip():
                        # keep whitespace, but skip pure-empty spans
                        text = text
                    span_bold = bool(span.get("flags", 0) & 16)
                    span_italic = bool(span.get("flags", 0) & 2)
                    font_size = span.get("size", 11)
                    max_font_size = max(max_font_size, font_size)

                    if span_bold and span_italic:
                        span_html = f"<strong><em>{text}</em></strong>"
                    elif span_bold:
                        span_html = f"<strong>{text}</strong>"
                    elif span_italic:
                        span_html = f"<em>{text}</em>"
                    else:
                        span_html = text

                    spans_html.append(span_html)
                    line_text += span.get("text", "")

                if not line_text.strip():
                    # blank line -> force paragraph break
                    flush_buffer()
                    continue

                # Determine if this line looks like a heading / section label
                is_section_pattern = bool(re.match(r'^\s*\d+(\.[A-Za-z0-9]+)+\.?\s', line_text))
                maybe_heading = (max_font_size >= 12 and len(line_text.strip()) < 160) or is_section_pattern or ("•" in line_text[:2])

                # If current buffer is empty, start buffering
                if not paragraph_buffer:
                    paragraph_buffer.append(" ".join(spans_html))
                    buffer_max_font = max_font_size
                    buffer_is_heading = maybe_heading
                else:
                    # If either this line or buffer is heading, flush buffer first
                    if maybe_heading or buffer_is_heading:
                        flush_buffer()
                        paragraph_buffer.append(" ".join(spans_html))
                        buffer_max_font = max_font_size
                        buffer_is_heading = maybe_heading
                    else:
                        # append to buffer as same paragraph (with a space)
                        paragraph_buffer.append(" ".join(spans_html))
                        buffer_max_font = max(buffer_max_font, max_font_size)

            # flush remaining buffer for block
            flush_buffer()

        output_html.append("</div>")
        if page_idx < len(doc) - 1 and page_num is None:
            output_html.append('<div class="page-break" style="page-break-after: always; height: 20px;"></div>')

    doc.close()
    return "".join(output_html)


# =====================================================
# HTML -> PDF
# =====================================================

def html_to_pdf(html_content: str, pdf_path: str, page_width_pt: float = 612.0, page_height_pt: float = 792.0, margins: dict = None):
    """
    Convert HTML to PDF using xhtml2pdf (pisa).
    page_width_pt and page_height_pt are in points (1pt = 1/72 inch).
    margins keys are expected in points: {'top': '36pt', ...} or numeric pts.
    """
    # normalize margins
    if margins is None:
        margins = {"top": "36pt", "right": "36pt", "bottom": "36pt", "left": "36pt"}

    def norm(val):
        if isinstance(val, (int, float)):
            return f"{val}pt"
        if isinstance(val, str) and val.endswith("pt"):
            return val
        # fallback
        return f"{float(val):.0f}pt"

    margins_norm = {
        "top": norm(margins.get("top", "36pt")),
        "right": norm(margins.get("right", "36pt")),
        "bottom": norm(margins.get("bottom", "36pt")),
        "left": norm(margins.get("left", "36pt")),
    }

    page_w_in = page_width_pt / 72.0
    page_h_in = page_height_pt / 72.0
    content_width_pt = page_width_pt - float(margins_norm['left'].replace('pt', '')) - float(margins_norm['right'].replace('pt', ''))
    content_width_in = content_width_pt / 72.0 if content_width_pt > 0 else max(5.5, page_w_in - 1.0)

    # Clean HTML
    html_content = re.sub(r'\s*contenteditable\s*=\s*["\']?true["\']?', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<img[^>]*src="data:image[^"]*"[^>]*>', '', html_content, flags=re.IGNORECASE)

    styled_html = f"""
    <html>
    <head>
        <meta charset="utf-8" />
        <style>
            @page {{
                size: {page_w_in}in {page_h_in}in;
                margin-top: {margins_norm['top']};
                margin-right: {margins_norm['right']};
                margin-bottom: {margins_norm['bottom']};
                margin-left: {margins_norm['left']};
            }}

            * {{
                box-sizing: border-box;
                -webkit-font-smoothing: antialiased;
            }}

            body {{
                font-family: 'Times New Roman', Times, serif;
                font-size: 11pt;
                color: #000;
                line-height: 1.25;
                margin: 0;
                padding: 0;
            }}

            .pdf-page-container {{
                width: {content_width_in}in;
                max-width: {content_width_in}in;
                margin: 0 auto;
            }}

            p {{
                margin-top: 0;
                margin-bottom: 4pt;
                text-align: justify;
                line-height: 1.25;
                font-size: 11pt;
                word-break: break-word;
                overflow-wrap: break-word;
                hyphens: auto;
            }}

            h1,h2,h3 {{
                margin-top: 10pt;
                margin-bottom: 4pt;
                line-height: 1.2;
                page-break-after: avoid;
            }}

            strong{{font-weight: bold;}}
            em{{font-style: italic;}}

            .page-break {{
                page-break-after: always;
                height: 0;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    # write PDF
    with open(pdf_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(styled_html.encode("utf-8"), dest=pdf_file, encoding="utf-8")
    if pisa_status.err:
        raise Exception(f"PDF generation error: {pisa_status.err}")


# =====================================================
# API ENDPOINTS
# =====================================================

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    pdf_path = os.path.join(BASE_DIR, f"{file_id}.pdf")
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    FILES[file_id] = {"pdf": pdf_path}
    return JSONResponse({"file_id": file_id})


@app.post("/api/search-pdf")
def search_pdf(req: SearchRequest):
    if req.file_id not in FILES:
        raise HTTPException(404, "File not found")
    pdf_path = FILES[req.file_id]["pdf"]
    matches = []
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):
            hits = page.search_for(req.query)
            if hits:
                matches.append({"page": page_num + 1, "count": len(hits)})
        doc.close()
    except Exception as e:
        raise HTTPException(500, f"Search failed: {e}")
    return {"matches": matches}


@app.post("/api/get-page")
def get_page_html(req: GetPageRequest):
    if req.file_id not in FILES:
        raise HTTPException(404, "File not found")
    pdf_path = FILES[req.file_id]["pdf"]
    page_idx = req.page_number - 1
    try:
        html = pdf_page_to_html_flowable(pdf_path, page_idx)
        return {"html": html}
    except Exception as e:
        raise HTTPException(500, f"Page conversion failed: {e}")


@app.post("/api/save-page-edit")
def save_page_edit(req: SavePageRequest):
    if req.file_id not in FILES:
        raise HTTPException(404, "File not found")

    original_pdf_path = FILES[req.file_id]["pdf"]
    page_idx = req.page_number - 1
    page_pdf_path = os.path.join(BASE_DIR, f"{req.file_id}_page_{req.page_number}_new.pdf")

    try:
        # open original and compute page metrics
        doc_orig = fitz.open(original_pdf_path)
        if page_idx < 0 or page_idx >= len(doc_orig):
            doc_orig.close()
            raise HTTPException(400, "Page index out of range")

        page_orig = doc_orig[page_idx]
        blocks = page_orig.get_text("dict")["blocks"]
        text_blocks = [b for b in blocks if b.get("type", -1) == 0]

        if text_blocks:
            min_x = min(b["bbox"][0] for b in text_blocks)
            min_y = min(b["bbox"][1] for b in text_blocks)
            max_x = max(b["bbox"][2] for b in text_blocks)
            max_y = max(b["bbox"][3] for b in text_blocks)
        else:
            # fallback
            min_x = 72.0
            min_y = 72.0
            max_x = page_orig.rect.width - 72.0
            max_y = page_orig.rect.height - 72.0

        page_width = page_orig.rect.width
        page_height = page_orig.rect.height
        doc_orig.close()

        # Add minimal buffer to margins (in pts)
        margin_left = max(12, min_x - 1.0)
        margin_top = max(12, min_y - 1.0)
        margin_right = max(12, page_width - max_x - 1.0)
        margin_bottom = max(12, page_height - max_y - 1.0)

        margins = {
            "top": f"{margin_top}pt",
            "right": f"{margin_right}pt",
            "bottom": f"{margin_bottom}pt",
            "left": f"{margin_left}pt"
        }

        # Render HTML -> PDF (this may produce multiple pages if content longer)
        html_to_pdf(req.html, page_pdf_path, page_width_pt=page_width, page_height_pt=page_height, margins=margins)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"HTML render failed: {e}")

    output_merged_path = os.path.join(BASE_DIR, f"{req.file_id}_merged.pdf")
    try:
        # Open original and newly rendered PDF and splice: delete original page and insert all pages from new_page_doc
        doc = fitz.open(original_pdf_path)
        new_page_doc = fitz.open(page_pdf_path)

        # Delete the single original page
        doc.delete_page(page_idx)

        # Insert pages from new_page_doc starting at page_idx (this handles multiple new pages automatically)
        doc.insert_pdf(new_page_doc, from_page=0, to_page=-1, start_at=page_idx)

        # Save merged
        doc.save(output_merged_path)
        doc.close()
        new_page_doc.close()

        with open(output_merged_path, "rb") as f:
            pdf_content = f.read()

        # cleanup working files
        try:
            os.remove(page_pdf_path)
            os.remove(output_merged_path)
        except:
            pass

        return Response(content=pdf_content, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=edited.pdf"})
    except Exception as e:
        raise HTTPException(500, f"Splicing failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
