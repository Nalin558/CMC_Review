import io
import tempfile
import pickle
from flask import Flask, request, jsonify
from flask_cors import CORS
from llm_client import llm  # our Gemini wrapper
from guidelines_rag.retriever import ICHRetriever
from cmc_rag.retriever import CMCRetriever
import numpy as np
import re
from sentence_transformers import SentenceTransformer
import json
import difflib  # add this with the other imports
import os
from PyPDF2 import PdfReader
from logger import write_log, LOG_FILE
from validator import run_validator, save_validator_results
from paragraph_fetcher import find_and_highlight_paragraph, extract_key_concepts

app = Flask(__name__)
CORS(app)

app_is_ready = True  # Placeholder - actual routes defined below after uploads_dir is created
import fitz  # PyMuPDF
from flask import send_file
import logging
from datetime import datetime
from pdf_paragraph_replace import replace_paragraph_anchored
import uuid
import shutil
from pdf_manager import (
    save_uploaded_pdf, get_current_pdf_path, has_pdf, 
    get_pdf_config, ensure_uploads_dir, save_pdf_config
)
from werkzeug.utils import secure_filename

# ============ SETUP CONSOLE LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Custom handler to write logs to jsonl
class JsonlHandler(logging.Handler):
    def emit(self, record):
        entry = {
            "time": datetime.utcnow().isoformat(),
            "event": "console_log",
            "data": {
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name
            }
        }
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"Error writing to log file: {e}")

jsonl_handler = JsonlHandler()
jsonl_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(jsonl_handler)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Allow PDF uploads
ALLOWED_EXTENSIONS = {'pdf'}
MAX_PDF_SIZE = 100 * 1024 * 1024  # 100MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

logger.info("=" * 70)
logger.info("🚀 BACKEND INITIALIZATION STARTED")

# ============ GLOBAL SESSION STATE ============
# Track when PDF was last uploaded to force fresh FAISS retrieval
last_pdf_upload_time = None
last_indexed_pdf_path = None
logger.info("=" * 70)
logger.info(f"📂 BASE_DIR: {BASE_DIR}")
logger.info(f"📂 PROJECT_ROOT: {PROJECT_ROOT}")

# Initialize uploads directory
ensure_uploads_dir()

GUIDELINE_KEYWORDS = {
  "Q": ["stability","stability studies","quality","pharmaceutical quality","impurity","impurities testing","impurity thresholds",
"analytical",
    "specification",
    "control strategy",
    "GMP",
    "GMP risk management",
    "risk-based quality",
    "CMC",
    "Quality by Design"
  ],

  "S": [
    "toxicology",
    "carcinogenicity",
    "genotoxicity",
    "reprotoxicity",
    "reproductive toxicity",
    "safety pharmacology",
    "non-clinical safety",
    "nonclinical",
    "QT prolongation",
    "cardiotoxicity"
  ],

  "E": [
    "clinical",
    "clinical studies",
    "clinical trials",
    "efficacy",
    "trial design",
    "study design",
    "biotech products",
    "biotechnological processes",
    "pharmacogenetics",
    "pharmacogenomics",
    "genomics",
    "clinical reporting",
    "GCP",
    "Good Clinical Practice"
  ],

  "M": [
    "bioavailability",
    "bioequivalence",
    "pharmacokinetics",
    "PK",
    "multidisciplinary",
    "cross-cutting",
    "MedDRA",
    "medical terminology",
    "CTD",
    "Common Technical Document",
    "ESTRI",
    "electronic standards",
    "regulatory information transfer"
  ]
}




compress_model = SentenceTransformer("all-MiniLM-L6-v2")
logger.info("✅ SentenceTransformer model loaded: all-MiniLM-L6-v2")

app = Flask(__name__)

# Configure static file serving for uploads
from flask import send_from_directory
uploads_dir = os.path.join(BASE_DIR, "uploads")
app.config['UPLOAD_FOLDER'] = uploads_dir

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded PDF files"""
    try:
        logger.info(f"📥 GET /uploads/{filename}")
        logger.info(f"   uploads_dir: {uploads_dir}")
        logger.info(f"   requested file: {filename}")
        full_path = os.path.join(uploads_dir, filename)
        logger.info(f"   full path: {full_path}")
        logger.info(f"   exists: {os.path.exists(full_path)}")
        
        if not os.path.exists(full_path):
            logger.error(f"❌ File not found: {full_path}")
            logger.info(f"   Files in uploads dir: {os.listdir(uploads_dir)}")
            return jsonify({"error": "File not found"}), 404
            
        return send_from_directory(uploads_dir, filename, mimetype='application/pdf')
    except Exception as e:
        logger.error(f"❌ Error serving file {filename}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": "File not found"}), 404

CORS(app)  # allow React frontend to call this later
logger.info("✅ Flask app created and CORS enabled")

# ============ CLEAR DOCUMENT ROUTE ============
@app.route("/cmc/clear-document", methods=["POST"])
def clear_document():
    """Delete all uploaded PDFs and reset config"""
    try:
        logger.info(f"🗑️  POST /cmc/clear-document")
        logger.info(f"   uploads_dir: {uploads_dir}")
        
        # Ensure directory exists
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir, exist_ok=True)
            logger.info(f"   Created uploads dir: {uploads_dir}")
        
        # Delete all files in uploads folder except .gitkeep
        files_before = os.listdir(uploads_dir)
        logger.info(f"   Files before clearing: {files_before}")
        
        for f in files_before:
            fp = os.path.join(uploads_dir, f)
            if f != '.gitkeep' and os.path.isfile(fp):
                try:
                    os.remove(fp)
                    logger.info(f"   ✅ Deleted: {f}")
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not delete {f}: {e}")
        
        # Reset config to None using pdf_manager
        save_pdf_config({"current_pdf": None, "current_pdf_path": None})
        logger.info("   ✅ PDF config reset to None")
        
        # Verify files are actually deleted
        files_after = os.listdir(uploads_dir)
        logger.info(f"   Files after clearing: {files_after}")
        
        return jsonify({"status": "ok", "message": "All PDFs and config cleared"}), 200
    except Exception as e:
        logger.error(f"   ❌ Error clearing document: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

# ============ SESSION MANAGEMENT FOR PDF WORKING COPIES ============
# Global dict to track working copies per session
working_copies = {}  # session_id -> working_copy_path

def get_session_id():
    """Generate or retrieve session ID from request headers"""
    session_id = request.headers.get('X-Session-ID')
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id

def infer_guideline_category(comment, cmc_text):
    text = (comment + " " + cmc_text).lower()

    scores = {"Q":0, "S":0, "E":0, "M":0}

    for cat, keys in GUIDELINE_KEYWORDS.items():
        for kw in keys:
            if kw.lower() in text:
                scores[cat] += 1

    # choose the highest scoring category
    best = max(scores, key=scores.get)

    # if no match → default = Q (most regulatory topics are Q)
    if scores[best] == 0:
        return "Q"

    return best

def build_text_diff(original: str, suggested: str):
    """
    Build a simple character-level diff between original and suggested text.
    Output is a list of segments:
      { "op": "equal" | "insert" | "delete" | "replace",
        "orig": "...",
        "suggested": "..." }
    Frontend will render:
      - equal: normal
      - insert: green
      - delete: red strikethrough
      - replace: show red (old) + green (new)
    """
    original = original or ""
    suggested = suggested or ""

    sm = difflib.SequenceMatcher(None, original, suggested)
    segments = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        segments.append({
            "op": tag,                      # 'equal', 'insert', 'delete', 'replace'
            "orig": original[i1:i2],
            "suggested": suggested[j1:j2],
        })

    return segments


def compress_text(text, query, max_sentences=4):
    """Extract the most relevant sentences using embeddings."""
    # split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

    if not sentences:
        return ""

    # embed
    q_emb = compress_model.encode([query])[0]
    s_embs = compress_model.encode(sentences)

    # cosine similarity
    sims = np.dot(s_embs, q_emb) / (np.linalg.norm(s_embs, axis=1) * np.linalg.norm(q_emb))

    # top N sentences
    idxs = sims.argsort()[-max_sentences:][::-1]

    return "\n".join([sentences[i] for i in idxs])

@app.route("/debug/uploads-list", methods=["GET"])
def debug_uploads_list():
    """Debug endpoint to list uploaded files"""
    try:
        if os.path.exists(uploads_dir):
            files = os.listdir(uploads_dir)
            file_details = []
            for f in files:
                fpath = os.path.join(uploads_dir, f)
                file_details.append({
                    "name": f,
                    "size": os.path.getsize(fpath),
                    "exists": os.path.exists(fpath)
                })
            return jsonify({
                "uploads_dir": uploads_dir,
                "files": file_details,
                "config": get_pdf_config()
            }), 200
        else:
            return jsonify({"error": "Uploads directory doesn't exist"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/cmc/results/clear", methods=["POST"])
def clear_results():
    """Clear cached results for a session"""
    try:
        session_id = get_session_id()
        logger.info(f"🗑️ POST /cmc/results/clear - Clearing results for session {session_id}")
        # Results are stored in memory during session, so nothing to clear from disk
        return jsonify({"status": "ok", "message": "Results cleared"}), 200
    except Exception as e:
        logger.error(f"Error clearing results: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    logger.info("✅ GET /health - Health check received")
    has_pdf_loaded = has_pdf()
    return jsonify({
        "status": "ok", 
        "message": "CMC Review P3 backend running",
        "has_pdf": has_pdf_loaded
    }), 200


@app.route("/api/pdf/upload", methods=["POST"])
def upload_pdf():
    """
    Handle PDF file upload
    Expects multipart/form-data with file parameter
    Returns: { "success": true, "message": "...", "pdf_path": "...", "filename": "..." }
    """
    try:
        logger.info("📤 POST /api/pdf/upload - PDF upload request received")
        logger.info(f"   Request files: {list(request.files.keys())}")
        
        # Check if file is present
        if 'file' not in request.files:
            logger.error("❌ No file part in request")
            return jsonify({"success": False, "error": "No file part"}), 400
        
        file = request.files['file']
        logger.info(f"   File received: {file.filename}")
        
        if file.filename == '':
            logger.error("❌ No selected file")
            return jsonify({"success": False, "error": "No selected file"}), 400
        
        if not allowed_file(file.filename):
            logger.error(f"❌ Invalid file type: {file.filename}")
            return jsonify({"success": False, "error": "Only PDF files are allowed"}), 400
        
        # Check file size
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        logger.info(f"   File size: {file_size} bytes")
        
        if file_size > MAX_PDF_SIZE:
            logger.error(f"❌ File too large: {file_size} bytes")
            return jsonify({"success": False, "error": "File too large (max 100MB)"}), 400
        
        # Save the uploaded PDF
        filename = secure_filename(file.filename)
        logger.info(f"   Secure filename: {filename}")
        pdf_path = save_uploaded_pdf(file, filename)
        logger.info(f"   Saved path: {pdf_path}")
        logger.info(f"   File exists after save: {os.path.exists(pdf_path)}")
        
        # Update global session state to mark PDF as uploaded
        global last_pdf_upload_time, last_indexed_pdf_path
        import time
        last_pdf_upload_time = time.time()
        last_indexed_pdf_path = pdf_path
        logger.info(f"   🔔 Session state updated: PDF upload timestamp = {last_pdf_upload_time}")
        
        # Verify config was saved PROPERLY (not empty or corrupted)
        config = get_pdf_config()
        logger.info(f"   Config after save: {config}")
        
        # Check that config actually has the PDF info
        if config.get("current_pdf") is None:
            logger.error(f"❌ PDF config not properly saved! Config: {config}")
            return jsonify({
                "success": True,  # Still true since file was saved
                "message": "PDF uploaded but config not saved yet",
                "pdf_path": pdf_path,
                "filename": filename,
                "warning": "Config may update shortly"
            }), 200
        
        logger.info(f"✅ PDF uploaded successfully with config: {config}")
        write_log("pdf_upload", {
            "filename": filename,
            "file_size": file_size,
            "pdf_path": pdf_path
        })
        return jsonify({
            "success": True,
            "message": "PDF uploaded successfully",
            "pdf_path": pdf_path,
            "filename": filename
        }), 200
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error uploading PDF: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500



@app.route("/api/pdf/status", methods=["GET"])
def pdf_status():
    """Get current PDF status"""
    try:
        config = get_pdf_config()
        current_pdf = config.get("current_pdf")
        current_path = config.get("current_pdf_path")
        has_pdf_loaded = has_pdf()
        
        logger.info(f"📊 GET /api/pdf/status")
        logger.info(f"   current_pdf: {current_pdf}")
        logger.info(f"   current_pdf_path: {current_path}")
        path_exists = os.path.exists(current_path) if current_path else False
        logger.info(f"   path exists: {path_exists}")
        logger.info(f"   has_pdf: {has_pdf_loaded}")
        
        # List files in uploads directory
        try:
            files_in_uploads = os.listdir(uploads_dir) if os.path.exists(uploads_dir) else []
            logger.info(f"   Files in uploads dir: {files_in_uploads}")
        except Exception as e:
            logger.warning(f"   Could not list uploads dir: {e}")
        
        return jsonify({
            "has_pdf": has_pdf_loaded,
            "current_pdf": current_pdf,
            "current_pdf_path": current_path,
            "uploads_dir": uploads_dir
        }), 200
    except Exception as e:
        logger.error(f"❌ Error in pdf_status: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            "has_pdf": False,
            "current_pdf": None,
            "current_pdf_path": None,
            "error": str(e)
        }), 500


@app.route("/test-llm", methods=["POST"])
def test_llm():
    """
    Quick sanity check:
    Body: { "prompt": "Say hello" }
    """
    data = request.get_json(force=True) or {}
    prompt = data.get("prompt", "").strip()
    
    logger.info(f"🧪 POST /test-llm - Testing LLM with prompt: {prompt[:50]}...")

    if not prompt:
        logger.error("❌ Missing 'prompt' in request body")
        return jsonify({"error": "Missing 'prompt' in request body"}), 400

    try:
        logger.info("📡 Calling LLM...")
        output = llm.generate_text(prompt)
        logger.info(f"✅ LLM returned output: {output[:100]}...")
        return jsonify({"prompt": prompt, "output": output}), 200
    except Exception as e:
        logger.error(f"❌ LLM Error: {str(e)}")
        return jsonify({"error": str(e)}), 500
@app.route("/search/guidelines", methods=["POST"])
def search_guidelines():
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    k = int(data.get("k", 5))
    category = data.get("category", None)

    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        retriever = ICHRetriever()
        results = retriever.search(query, k=k, category=category)

        formatted = [
            {
                "score": r[0],
                "text": r[1],
                "meta": r[2]
            }
            for r in results
        ]

        write_log("search_guidelines", {
            "query": query,
            "k": k,
            "category": category,
            "results_count": len(formatted),
            "top_result_score": formatted[0]["score"] if formatted else 0
        })

        return jsonify({"results": formatted}), 200

    except Exception as e:
        write_log("search_guidelines_error", {"query": query, "error": str(e)})
        return jsonify({"error": str(e)}), 500
    
@app.route("/search/cmc", methods=["POST"])
def search_cmc():
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    k = int(data.get("k", 5))

    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        retriever = CMCRetriever()
        results = retriever.search(query, k=k)

        write_log("search_cmc", {
            "query": query,
            "k": k,
            "results_count": len(results),
            "top_result_score": results[0]["score"] if results else 0
        })

        return jsonify({"results": results}), 200

    except Exception as e:
        write_log("search_cmc_error", {"query": query, "error": str(e)})
        return jsonify({"error": str(e)}), 500

@app.route("/cmc/map-comment", methods=["POST"])
def map_comment():
    data = request.get_json(force=True) or {}
    comment = data.get("comment", "").strip()
    k = int(data.get("k", 5))

    if not comment:
        return jsonify({"error": "Missing 'comment'"}), 400

    try:
        from cmc_rag.retriever import CMCRetriever
        ret = CMCRetriever()

        results = ret.search(comment, k=k)

        write_log("map_comment", {
            "comment": comment,
            "k": k,
            "results_count": len(results)
        })

        return jsonify({
            "comment": comment,
            "results": results
        }), 200

    except Exception as e:
        write_log("map_comment_error", {"comment": comment, "error": str(e)})
        return jsonify({"error": str(e)}), 500
def build_cmc_answer_json(comment: str,
                          cmc_text: str,
                          guideline_texts: list[str],
                          category: str) -> dict:
    """
    Ask the LLM to return a structured JSON object:
      - short_answer: brief answer for tracking
      - suggested_cmc_rewrite: revised CMC section text
    """
    logger.info(f"  📋 build_cmc_answer_json called")
    logger.info(f"    Category: {category}")
    logger.info(f"    Guideline sections: {len(guideline_texts)}")
    
    guideline_context = "\n\n---\n\n".join(guideline_texts)

    prompt = f"""
You are a senior regulatory CMC writer.

Your job:
1. Understand  the reviewer comment in a regulatory-compliant way.
2. Propose an improved rewrite of the CMC excerpt that addresses the comment input and give answer to it using given CMC excerpt and relevant ICH guidelines.
3. Use the ICH {category} guideline snippets only as SUPPORT, not to copy-paste huge blocks.

Return your output as VALID JSON ONLY, no extra text, with this exact schema:

{{
  "short_answer": "1–3 sentence summary of the response containg what all guidelines the comment can mention",
  
  "suggested_cmc_rewrite": "it should be revised CMC text, rewritten to address the comment appropriately which old CMC text did not address adequately but the length generated should be similar to the original CMC excerpt it should not be a massive output"
}}

Comment:
{comment}

CMC excerpt:
{cmc_text}

Relevant ICH {category} guidelines:
{guideline_context}
"""

    try:
        logger.info("    📡 Calling LLM...")
        raw = llm.generate_text(prompt)
        logger.info("    ✅ LLM response received")
    except Exception as e:
        # Log LLM errors and fallback to an empty raw response so we can produce
        # a deterministic, local fallback below instead of returning HTTP 500.
        error_msg = str(e)
        logger.error(f"    ❌ LLM Error: {error_msg}")
        
        # Check if it's a quota error
        is_quota_error = "429" in error_msg or "quota" in error_msg.lower()
        
        try:
            write_log("llm_error", {"error": error_msg, "is_quota_error": is_quota_error})
        except Exception:
            pass
        raw = ""

    # --- CLEAN JSON WRAPPER ---
    raw = (
        (raw or "").replace("```json", "").replace("```", "").strip()
    )

    # If LLM returned nothing (or raised), provide a deterministic fallback
    # using the local compress_text() utility so the endpoint still returns
    # a helpful suggested rewrite and a clear short answer.
    if not raw:
        try:
            fallback_rewrite = compress_text(cmc_text or "", comment or "", max_sentences=6)
            
            # Provide more specific message based on error type
            if is_quota_error:
                short = (
                    "LLM API quota exceeded (free tier limit reached) — returning a compressed CMC summary."
                )
            else:
                short = (
                    "LLM unavailable — returned a compressed CMC summary as a fallback."
                )
            
            return {
                "short_answer": short,
                "suggested_cmc_rewrite": fallback_rewrite,
            }
        except Exception as e:
            try:
                write_log("fallback_error", {"error": str(e)})
            except Exception:
                pass
            return {"short_answer": "", "suggested_cmc_rewrite": ""}

    # Try to parse JSON; if it fails, fall back to the deterministic summary as well
    try:
        obj = json.loads(raw)
        # basic sanity
        if not isinstance(obj, dict):
            raise ValueError("Not a dict")
    except Exception:
        try:
            fallback_rewrite = compress_text(cmc_text or "", comment or "", max_sentences=6)
            short = (
                "LLM returned unparsable output — returning a compressed CMC summary as fallback."
            )
            return {
                "short_answer": short,
                "suggested_cmc_rewrite": fallback_rewrite,
            }
        except Exception:
            return {"short_answer": "", "suggested_cmc_rewrite": ""}

    return obj

def clean_cmc_text(text: str) -> str:
    """
    Clean CMC text by removing headers, footers, and metadata.
    Removes patterns like:
    - "Assessment report EMA/464842/2024 Page 78/195"
    - "Page 78/195"
    - "EMA/464842/2024"
    - "Assessment report"
    """
    if not text:
        return text
    
    cleaned = text
    
    # Remove "Assessment report EMA/XXXXXX/YYYY Page X/Y" pattern
    cleaned = re.sub(r'Assessment\s+report\s+EMA/\d+/\d+\s+Page\s+\d+/\d+', '', cleaned, flags=re.IGNORECASE)
    
    # Remove standalone "Page X/Y" patterns
    cleaned = re.sub(r'Page\s+\d+/\d+', '', cleaned, flags=re.IGNORECASE)
    
    # Remove standalone "EMA/XXXXXX/YYYY" patterns
    cleaned = re.sub(r'EMA/\d+/\d+', '', cleaned, flags=re.IGNORECASE)
    
    # Remove "Assessment report" if it appears alone
    cleaned = re.sub(r'Assessment\s+report', '', cleaned, flags=re.IGNORECASE)
    
    # Remove extra whitespace and normalize
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def process_single_comment(comment, cmc_k=5, guideline_k=1, score_threshold=0.4):
    """
    Helper function to process a single comment.
    Returns all CMC hits with scores >= score_threshold.
    Does NOT call LLM yet (to save cost).
    LLM generation happens lazily in /cmc/answer-section when user selects a section.
    """
    try:
        # Check if FAISS index needs to be rebuilt (e.g., after PDF upload)
        from pdf_manager import has_pdf, get_current_pdf_path, reindex_pdf
        
        global last_pdf_upload_time, last_indexed_pdf_path
        
        current_pdf_path = get_current_pdf_path()
        
        # Handle case: PDF uploaded but FAISS not indexed yet
        if current_pdf_path and has_pdf():
            # Check if FAISS index exists
            faiss_dir = os.path.join(BASE_DIR, "cmc_rag", "faiss_store")
            faiss_index_exists = os.path.exists(os.path.join(faiss_dir, "index.faiss"))
            
            logger.info(f"🔍 FAISS status check:")
            logger.info(f"   - Current PDF path: {current_pdf_path}")
            logger.info(f"   - PDF exists: {os.path.exists(current_pdf_path)}")
            logger.info(f"   - FAISS index exists: {faiss_index_exists}")
            logger.info(f"   - Last indexed PDF: {last_indexed_pdf_path}")
            
            # Rebuild if: PDF path changed OR FAISS doesn't exist
            if (last_indexed_pdf_path != current_pdf_path) or not faiss_index_exists:
                logger.info(f"🔄 Rebuilding FAISS index...")
                logger.info(f"   - PDF path changed: {last_indexed_pdf_path != current_pdf_path}")
                logger.info(f"   - FAISS exists: {faiss_index_exists}")
                try:
                    reindex_pdf(current_pdf_path)
                    last_indexed_pdf_path = current_pdf_path
                    logger.info(f"✅ FAISS index rebuilt successfully")
                except Exception as e:
                    logger.error(f"❌ Could not rebuild FAISS index: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return {"error": f"Failed to build search index. Please upload a PDF. Details: {str(e)}"}
        else:
            logger.warning(f"⚠️  No PDF available")
            logger.warning(f"   - Current PDF path: {current_pdf_path}")
            logger.warning(f"   - Has PDF: {has_pdf()}")
            return {"error": "No PDF uploaded yet. Please upload a PDF first."}
        
        # Step 1 — Find relevant CMC text
        try:
            cmc_ret = CMCRetriever()
            cmc_results = cmc_ret.search(comment, k=cmc_k)
        except RuntimeError as e:
            logger.error(f"❌ CMCRetriever error: {e}")
            logger.info(f"   Attempting emergency FAISS rebuild...")
            try:
                reindex_pdf(current_pdf_path)
                cmc_ret = CMCRetriever()
                cmc_results = cmc_ret.search(comment, k=cmc_k)
            except Exception as rebuild_err:
                logger.error(f"❌ Emergency rebuild failed: {rebuild_err}")
                return {"error": f"Search index error: {str(rebuild_err)}"}

        if not cmc_results:
            return {"error": "No CMC sections found"}

        # Filter by score threshold
        filtered_cmc = [r for r in cmc_results if r.get("score", 0) >= score_threshold]
        if not filtered_cmc:
            filtered_cmc = cmc_results[:1]  # fallback to top result

        top_cmc = filtered_cmc[0]
        top_cmc_text = top_cmc["text"]

        # Step 2 — Auto-detect guideline category (Q/S/E/M) using top result
        category = infer_guideline_category(comment, top_cmc_text)

        # Step 3 — Return structured result with ALL filtered CMC hits (no LLM calls yet)
        return {
            "comment": comment,
            "category_used": category,
            "cmc_hits": [
                {
                    "score": r.get("score", 0),
                    "text": clean_cmc_text(r.get("text", ""))[:1500],  # Clean and trim for compact UI
                    "meta": r.get("meta", {}),
                    "heading": r.get("meta", {}).get("heading", "")
                }
                for r in filtered_cmc
            ],
        }

    except Exception as e:
        return {"error": str(e), "comment": comment}


@app.route("/cmc/answer", methods=["POST"])
def cmc_answer():
    data = request.get_json(force=True)
    comment = data.get("comment", "").strip()

    cmc_k = int(data.get("cmc_k", 1))
    guideline_k = int(data.get("guideline_k", 1))

    if not comment:
        return jsonify({"error": "Missing 'comment'"}), 400

    try:
        result = process_single_comment(comment, cmc_k, guideline_k)
        
        if "error" in result:
            write_log("cmc_answer_error", {"comment": comment, "error": result.get("error")})
            return jsonify(result), 404 if "No CMC" in result.get("error", "") else 500
        
        write_log("cmc_answer_success", {
            "comment": comment,
            "category_used": result.get("category_used"),
            "affected_sections": result.get("llm_result", {}).get("affected_sections", []),
            "impact_analysis": result.get("llm_result", {}).get("impact_analysis", {}),
            "highlighting_needed": bool(result.get("llm_result", {}).get("highlights"))
        })
        return jsonify(result), 200

    except Exception as e:
        write_log("cmc_answer_exception", {"comment": comment, "exception": str(e)})
        return jsonify({"error": str(e)}), 500


@app.route("/cmc/answer-batch", methods=["POST"])
def cmc_answer_batch():
    """
    Process multiple comments sequentially.
    Body: { 
        "comments": ["comment1", "comment2", ...],
        "cmc_k": 3,
        "guideline_k": 5
    }
    Returns: {
        "results": [
            {
                "comment": "...",
                "category_used": "Q",
                "llm_result": {...},
                ...
            },
            ...
        ],
        "total_processed": N,
        "total_errors": M
    }
    """
    data = request.get_json(force=True)
    comments = data.get("comments", [])
    
    logger.info(f"📝 POST /cmc/answer-batch - Processing {len(comments)} comments")
    
    if not isinstance(comments, list) or not comments:
        logger.error("❌ Missing or empty 'comments' array")
        return jsonify({"error": "Missing or empty 'comments' array"}), 400

    cmc_k = int(data.get("cmc_k", 1))
    guideline_k = int(data.get("guideline_k", 1))
    
    logger.info(f"⚙️  CMC_K={cmc_k}, GUIDELINE_K={guideline_k}")

    results = []
    total_errors = 0

    try:
        for idx, comment in enumerate(comments):
            comment = comment.strip()
            if not comment:
                continue
            
            logger.info(f"  └─ Processing comment {idx + 1}/{len(comments)}: {comment[:50]}...")
            result = process_single_comment(comment, cmc_k, guideline_k)
            results.append(result)

            if "error" in result:
                logger.warning(f"    ⚠️  Error in comment {idx + 1}: {result.get('error')}")
                total_errors += 1
            else:
                logger.info(f"    ✅ Comment {idx + 1} processed successfully")

        logger.info(f"✅ Batch complete: {len(results)} processed, {total_errors} errors")
        write_log("cmc_answer_batch", {
            "total_comments": len(comments),
            "total_processed": len(results),
            "total_errors": total_errors,
            "comments": comments,
            "results_summary": [
                {
                    "comment": r.get("comment"),
                    "category_used": r.get("category_used"),
                    "affected_sections": r.get("llm_result", {}).get("affected_sections", []) if "llm_result" in r else [],
                    "impact_analysis": r.get("llm_result", {}).get("impact_analysis", {}) if "llm_result" in r else {},
                    "error": r.get("error") if "error" in r else None
                } for r in results
            ]
        })
        return jsonify({
            "results": results,
            "total_processed": len(results),
            "total_errors": total_errors
        }), 200

    except Exception as e:
        logger.error(f"❌ Batch processing error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/cmc/answer-section", methods=["POST"])
def cmc_answer_section():
    """
    Generate LLM response (summary + rewrite) for a specific CMC section.
    Called lazily when user selects a section from the picker.
    Body: {
        "comment": "user comment",
        "section_text": "the selected CMC section text",
        "category": "Q|S|E|M",
        "guideline_k": 5
    }
    Returns: {
        "short_answer": "...",
        "suggested_cmc_rewrite": "...",
        "diff_segments": [...]
    }
    """
    data = request.get_json(force=True) or {}
    comment = data.get("comment", "").strip()
    section_text = data.get("section_text", "").strip()
    category = data.get("category", "Q")
    guideline_k = int(data.get("guideline_k", 5))

    logger.info(f"🎯 POST /cmc/answer-section - Generating LLM response for section")
    logger.info(f"  Comment: {comment[:50]}...")
    logger.info(f"  Section length: {len(section_text)} chars")
    logger.info(f"  Category: {category}, Guideline K: {guideline_k}")

    if not comment or not section_text:
        logger.error("❌ Missing 'comment' or 'section_text'")
        return jsonify({"error": "Missing 'comment' or 'section_text'"}), 400

    try:
        logger.info("📚 Retrieving ICH guidelines...")
        # Retrieve guideline sections using comment + section text
        ich_ret = ICHRetriever()
        combined_text = comment + " " + section_text
        guideline_results = ich_ret.search(
            combined_text,
            k=guideline_k,
            category=category
        )
        logger.info(f"  ✅ Found {len(guideline_results)} guideline sections")

        # Trim guideline contexts
        guideline_contexts = [g[1][:1500] for g in guideline_results]

        # Generate LLM response for this specific section
        logger.info("🤖 Calling LLM to generate rewrite...")
        llm_obj = build_cmc_answer_json(
            comment=comment,
            cmc_text=section_text[:2000],
            guideline_texts=guideline_contexts,
            category=category
        )
        logger.info(f"  ✅ LLM response generated successfully")

        # Build diff
        suggested_rewrite = llm_obj.get("suggested_cmc_rewrite", "") or ""
        diff_segments = build_text_diff(section_text[:2000], suggested_rewrite)

        # Include guideline context so the frontend's validator can show it immediately
        guideline_context_combined = "\n\n---\n\n".join(guideline_contexts)

        return jsonify({
            "short_answer": llm_obj.get("short_answer", ""),
            "suggested_cmc_rewrite": llm_obj.get("suggested_cmc_rewrite", ""),
            "diff_segments": diff_segments,
            "guideline_context": guideline_context_combined,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/validate", methods=["POST"])
def validate_endpoint():
    """
    Validate a paragraph against given guidelines using the validator module.
    Body: {
      "guidelines": "...",
      "paragraph": "...",
      "session_id": "optional",
      "entry_id": "optional"
    }

    Returns: { "highlighted_html": "...", "violated": "...", "reasoning": "...", "raw": "..." }
    """
    data = request.get_json(force=True) or {}
    guidelines = data.get("guidelines", "").strip()
    paragraph = data.get("paragraph", "").strip()
    session_id = data.get("session_id") or request.headers.get('X-Session-ID')
    entry_id = data.get("entry_id")

    logger.info("🔍 POST /validate - Running guideline validation")

    if not guidelines or not paragraph:
        logger.error("Missing guidelines or paragraph in /validate request")
        return jsonify({"error": "Missing 'guidelines' or 'paragraph' in request"}), 400

    try:
        raw, violated, reasoning, highlighted_html = run_validator(guidelines, paragraph)

        # Save results for later inspection (non-blocking best-effort)
        try:
            save_validator_results(guidelines, paragraph, violated, reasoning, highlighted_html)
            logger.info("✅ Validator results saved")
        except Exception as e:
            logger.warning(f"Could not save validator results: {e}")

        write_log("validate_success", {
            "guidelines": guidelines[:500],
            "paragraph": paragraph[:500],
            "violated": violated,
            "reasoning": reasoning,
            "highlighted_html": highlighted_html[:500]
        })

        return jsonify({
            "highlighted_html": highlighted_html,
            "violated": violated,
            "reasoning": reasoning,
            "raw": raw
        }), 200

    except Exception as e:
        logger.error(f"Error in /validate: {e}")
        write_log("validate_error", {"guidelines": guidelines[:200], "paragraph": paragraph[:200], "error": str(e)})
        return jsonify({"error": str(e)}), 500

@app.route("/cmc/document", methods=["GET"])
def load_cmc_document():
    try:
        json_path = os.path.join(BASE_DIR, "cmc_full.json")

        if not os.path.exists(json_path):
            logger.error(f"cmc_full.json not found at {json_path}")
            return jsonify({"error": "cmc_full.json not found"}), 404

        logger.info(f"Loading cmc_full.json from {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info(f"File read, length: {len(content)}")

        try:
            data = json.loads(content)
            logger.info("JSON loaded successfully")
        except Exception as json_err:
            logger.error(f"JSON load error: {str(json_err)}")
            return jsonify({
                "error": "Invalid JSON format in cmc_full.json",
                "details": str(json_err)
            }), 500

        return jsonify(data), 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route("/cmc/document/save", methods=["POST"])
def save_cmc_document():
    """
    Save an updated CMC document JSON back to cmc_full.json.
    Expects body:
      {
        "document": { ... }  # same structure as /cmc/document returns
      }
    """
    try:
        data = request.get_json(force=True) or {}
        document = data.get("document")

        if not isinstance(document, dict):
            return jsonify({
                "error": "Request body must contain a 'document' object"
            }), 400

        json_path = "cmc_full.json"

        # Write as UTF-16 to match your current reader
        with open(json_path, "w", encoding="utf-16") as f:
            f.write(json.dumps(document, ensure_ascii=False, indent=2))

        write_log("cmc_document_save", {
            "sections_count": len(document.get("sections", [])),
            "total_changes": "document updated"  # Could be more detailed if we track diffs
        })

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        return jsonify({
            "error": "Failed to save CMC document",
            "details": str(e)
        }), 500

@app.route("/log/event", methods=["POST", "OPTIONS"])
def log_event():
    """Log events from frontend"""
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return "", 204
    try:
        data = request.get_json()
        logger.info(f"📊 LOG EVENT: {data}")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error logging event: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/log/recent", methods=["GET"])
def get_recent_logs():
    """Get recent logs"""
    limit = int(request.args.get('limit', 10))
    try:
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-limit:]  # get last limit lines
                for line in lines:
                    if line.strip():
                        entry = json.loads(line.strip())
                        logs.append({
                            "event_type": entry["event"],
                            "timestamp": entry["time"],
                            "payload": entry["data"]
                        })
        return jsonify({"logs": logs})
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return jsonify({"error": str(e)}), 500
        
        return jsonify({
            "session_id": session_id,
            "status": "created"
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error creating working copy: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/pdf/download-working-copy", methods=["GET"])
def download_working_copy():
    """
    Download the final working copy and clean up.
    """
    try:
        session_id = request.headers.get('X-Session-ID')
        
        logger.info(f"📥 Download request for session: {session_id}")
        
        if not session_id or session_id not in working_copies:
            logger.error(f"❌ No working copy found for session: {session_id}")
            return jsonify({"error": "No working copy found"}), 404
        
        working_copy_path = working_copies[session_id]
        
        if not os.path.exists(working_copy_path):
            logger.error(f"❌ Working copy file not found: {working_copy_path}")
            return jsonify({"error": "Working copy file not found"}), 404
        
        # Read PDF
        with open(working_copy_path, 'rb') as f:
            pdf_data = f.read()
        
        logger.info(f"✅ PDF read successfully, size: {len(pdf_data)} bytes")
        
        # Clean up
        try:
            os.unlink(working_copy_path)
            del working_copies[session_id]
            logger.info(f"🧹 Cleaned up working copy for session: {session_id}")
        except Exception as e:
            logger.warning(f"⚠️ Cleanup error: {e}")
        
        return send_file(
            io.BytesIO(pdf_data),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="cmc_edited_final.pdf"
        )
        
    except Exception as e:
        logger.error(f"❌ Error downloading working copy: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/cmc/find-paragraph", methods=["POST"])
def find_paragraph_endpoint():
    """
    Find paragraphs in the PDF that match the given text using LLM-guided cosine similarity.
    
    This endpoint uses:
    1. LLM to extract key concepts from the user's paragraph
    2. Cosine similarity to find matching paragraphs in the PDF
    3. LLM to verify the best match
    
    Body:
      {
        "text": "paragraph to find",
        "top_k": 5,  # optional, default 5
        "similarity_threshold": 0.3  # optional, default 0.3
      }
    
    Returns:
      {
        "best_match": { "text": "...", "page": 1, "similarity": 0.85, ... },
        "candidates": [ { ... }, ... ],  # top-k candidates
        "key_concepts": "extracted concepts from user paragraph"
      }
    """
    try:
        data = request.get_json(force=True) or {}
        user_text = (data.get("text") or "").strip()
        top_k = data.get("top_k", 5)
        sim_threshold = data.get("similarity_threshold", 0.3)
        
        logger.info(f"🔍 POST /cmc/find-paragraph - Finding paragraph with similarity")
        
        if not user_text:
            logger.error("❌ Missing 'text' in request")
            return jsonify({"error": "Missing 'text' field"}), 400
        
        # Get the current PDF path
        pdf_path = get_current_pdf_path()
        if not pdf_path or not os.path.exists(pdf_path):
            logger.error(f"❌ Base PDF not found: {pdf_path}")
            return jsonify({"error": "PDF not found. Please upload a PDF first."}), 500
        
        logger.info(f"📄 Using PDF: {pdf_path}")
        logger.info(f"📝 Finding {top_k} paragraphs with threshold {sim_threshold}")
        
        # Find paragraphs using intelligent matching
        best_match, candidates = find_and_highlight_paragraph(
            pdf_path=pdf_path,
            user_paragraph=user_text,
            top_k=top_k,
            similarity_threshold=sim_threshold
        )
        
        # Extract key concepts
        try:
            key_concepts = extract_key_concepts(user_text)
        except Exception as e:
            logger.warning(f"Could not extract key concepts: {e}")
            key_concepts = user_text[:200]
        
        # Format response
        response = {
            "key_concepts": key_concepts,
            "best_match": best_match,
            "candidates": candidates[:top_k],
            "total_candidates": len(candidates)
        }
        
        logger.info(f"✅ Found {len(candidates)} candidates, best_match: {best_match is not None}")
        
        write_log("find_paragraph", {
            "user_text_length": len(user_text),
            "candidates_found": len(candidates),
            "has_best_match": best_match is not None,
            "top_k": top_k,
            "similarity_threshold": sim_threshold
        })
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"❌ Error finding paragraph: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/cmc/smart-replace-paragraph", methods=["POST"])
def smart_replace_paragraph():
    """
    Intelligently find and replace a paragraph in the PDF.
    
    Uses LLM-guided cosine similarity to find the best matching paragraph,
    then replaces it with the new text.
    
    Body:
      {
        "old_text": "paragraph to find and replace",
        "new_text": "replacement text",
        "use_anchor_points": true,  # optional, use start/end anchors for precision
        "similarity_threshold": 0.3  # optional
      }
    
    Returns:
      {
        "success": true,
        "found_match": { ... },
        "pdf_path": "path to modified PDF",
        "page": 1,
        "block_idx": 0
      }
    """
    try:
        data = request.get_json(force=True) or {}
        old_text = (data.get("old_text") or "").strip()
        new_text = (data.get("new_text") or "").strip()
        use_anchors = data.get("use_anchor_points", False)
        sim_threshold = data.get("similarity_threshold", 0.3)
        
        logger.info(f"🔄 POST /cmc/smart-replace-paragraph - Smart paragraph replacement")
        
        if not old_text or not new_text:
            logger.error("❌ Missing 'old_text' or 'new_text' in request")
            return jsonify({"error": "Missing 'old_text' or 'new_text' field"}), 400
        
        # Get the current PDF path
        pdf_path = get_current_pdf_path()
        if not pdf_path or not os.path.exists(pdf_path):
            logger.error(f"❌ Base PDF not found: {pdf_path}")
            return jsonify({"error": "PDF not found. Please upload a PDF first."}), 500
        
        logger.info(f"📄 Using PDF: {pdf_path}")
        logger.info(f"🔍 Finding best matching paragraph...")
        
        # Find the best matching paragraph
        best_match, candidates = find_and_highlight_paragraph(
            pdf_path=pdf_path,
            user_paragraph=old_text,
            top_k=3,
            similarity_threshold=sim_threshold
        )
        
        if not best_match:
            logger.warning("❌ Could not find matching paragraph in PDF")
            return jsonify({
                "success": False,
                "error": "Could not find matching paragraph",
                "candidates": candidates[:3]  # Return candidates for user to choose from
            }), 404
        
        logger.info(f"✅ Found matching paragraph on page {best_match['page']}")
        logger.info(f"   Similarity: {best_match['similarity']:.2%}")
        
        # Now replace the paragraph in the PDF
        # Strategy: use the matched text as anchor to find and replace
        try:
            doc = fitz.open(pdf_path)
            page_num = best_match['page']
            matched_para = best_match['text']
            
            # Strategy: find the text on the page and replace it
            # We'll use a direct text replacement with the actual matched paragraph
            page = doc[page_num - 1]
            
            # Get all text blocks on the page
            blocks = page.get_text("blocks")
            block_idx = best_match.get('block_idx', 0)
            
            # Replace the text in the identified block
            if block_idx < len(blocks):
                # Delete the old block text and insert new text
                # For now, we'll use the paragraph replacement with the matched text as anchor
                
                # Split the matched paragraph to create anchor points
                words = matched_para.split()
                if len(words) > 2:
                    # Use first few words as start anchor
                    start_anchor = " ".join(words[:min(3, len(words))])
                    # Use last few words as end anchor
                    end_anchor = " ".join(words[max(0, len(words)-3):])
                    
                    if use_anchors and start_anchor and end_anchor and start_anchor != end_anchor:
                        logger.info(f"   Using anchor-based replacement...")
                        logger.info(f"   Start anchor: {start_anchor}")
                        logger.info(f"   End anchor: {end_anchor}")
                        
                        # Use the anchor-based replacement
                        output_path = replace_paragraph_anchored(
                            input_pdf_path=pdf_path,
                            page_number=page_num,
                            start_anchor=start_anchor,
                            end_anchor=end_anchor,
                            replacement_text=new_text
                        )
                        
                        logger.info(f"✅ PDF replaced successfully")
                        
                        write_log("smart_replace_paragraph", {
                            "old_text_length": len(old_text),
                            "new_text_length": len(new_text),
                            "page": page_num,
                            "matched_similarity": best_match['similarity'],
                            "used_anchors": True
                        })
                        
                        return jsonify({
                            "success": True,
                            "message": "Paragraph replaced successfully",
                            "found_match": best_match,
                            "pdf_path": output_path,
                            "page": page_num,
                            "matched_similarity": best_match['similarity']
                        }), 200
            
            doc.close()
            
            # If anchor approach fails, return the match for user to confirm
            logger.info("⚠️  Could not apply replacement automatically; returning match for confirmation")
            return jsonify({
                "success": False,
                "error": "Could not apply replacement automatically",
                "found_match": best_match,
                "suggestion": "Please use the returned match details to manually verify the paragraph"
            }), 202  # 202 Accepted (needs confirmation)
            
        except Exception as e:
            logger.error(f"❌ Error replacing paragraph: {e}")
            return jsonify({
                "success": False,
                "error": str(e),
                "found_match": best_match  # Return the found match anyway
            }), 500
        
    except Exception as e:
        logger.error(f"❌ Error in smart replace: {str(e)}")
        return jsonify({"error": str(e)}), 500

        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"❌ Error finding paragraph: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/cmc/highlight", methods=["POST"])
def cmc_highlight():
    """
    Return a *new* PDF with highlight annotations for the given text or mapped section.
    
    BOUNDARY-AWARE HIGHLIGHTING: Only highlights text within its EXACT paragraph/block.
    This prevents highlights from bleeding into adjacent paragraphs and damaging PDF layout.
    
    Body can be one of:
      - { "text": "..." }
      - { "section_text": "..." }
      - { "section_id": "CMC-12" }
      - { "meta": {"id": "CMC-12"} }
    """
    try:
        data = request.get_json(force=True) or {}
        text = (data.get("text") or "").strip()
        section_text = (data.get("section_text") or "").strip()
        section_id = (data.get("section_id") or "").strip()
        meta_obj = data.get("meta") or {}
        meta_id = (meta_obj.get("id") if isinstance(meta_obj, dict) else None) or None

        logger.info(f"🎨 POST /cmc/highlight - Boundary-aware highlighting enabled")

        # At least one source of text must be provided
        if not any([text, section_text, section_id, meta_id]):
            logger.error("❌ Missing 'text' or 'section_text' or 'section_id'/'meta' in request")
            return jsonify({"error": "Missing 'text' or 'section_text' or 'section_id'/'meta'"}), 400

        # Get the current PDF path dynamically
        cmc_pdf_path = get_current_pdf_path()
        if not cmc_pdf_path or not os.path.exists(cmc_pdf_path):
            logger.error(f"❌ Base PDF not found: {cmc_pdf_path}")
            return jsonify({"error": f"Base PDF not found. Please upload a PDF first."}), 500

        logger.info(f"📄 Opening PDF: {cmc_pdf_path}")
        doc = fitz.open(cmc_pdf_path)

        # Determine source text to use for highlighting
        source = "text"
        norm_text = ""

        if section_text:
            source = "section_text"
            norm_text = section_text
        elif section_id or meta_id:
            try:
                store_dir = os.path.join(BASE_DIR, "cmc_rag", "faiss_store")
                meta_path = os.path.join(store_dir, "metadata.pkl")
                chunks_path = os.path.join(store_dir, "chunks.pkl")

                if os.path.exists(meta_path) and os.path.exists(chunks_path):
                    with open(meta_path, "rb") as f:
                        stored_meta = pickle.load(f)
                    with open(chunks_path, "rb") as f:
                        stored_chunks = pickle.load(f)

                    match_idx = None
                    lookup_id = meta_id or section_id
                    for i, m in enumerate(stored_meta):
                        if m.get("id") == lookup_id or m.get("id") == section_id:
                            match_idx = i
                            break
                        if meta_obj and isinstance(meta_obj, dict):
                            if m.get("heading") == meta_obj.get("heading") and m.get("file") == meta_obj.get("file"):
                                match_idx = i
                                break

                    if match_idx is not None:
                        source = "mapped_section"
                        norm_text = stored_chunks[match_idx]
                        logger.info(f"  Using mapped section from faiss_store index {match_idx}")
            except Exception as e:
                logger.warning(f"  Error loading faiss_store: {e}")

        if not norm_text and text:
            source = "text"
            norm_text = text

        # --- NORMALIZATION ---
        import unicodedata
        norm_text = unicodedata.normalize('NFKD', norm_text)
        norm_text = norm_text.replace("\n", " ").replace("\r", " ")
        norm_text = re.sub(r'\s+', ' ', norm_text).strip()
        logger.info(f"  Source: {source}, text length: {len(norm_text)}")

        # === HYBRID HIGHLIGHTING: Stage 1 - Block-Aware (Precise) ===
        # First, try to find text within specific paragraph blocks
        # This prevents highlighting from bleeding across paragraphs
        
        total_hits = 0
        highlighted_pages = set()  # Track which pages have highlights
        found_blocks = {}  # Maps (page_num, block_index) -> bounding box
        
        logger.info(f"🔍 Stage 1: Searching for text within paragraph blocks...")
        
        # Step 1: Find which text blocks contain our search text
        for page_num, page in enumerate(doc, 1):
            blocks = page.get_text("blocks")
            
            for block_idx, block in enumerate(blocks):
                if block[6] != 0:  # Skip non-text blocks
                    continue
                    
                block_text = block[4]
                block_bbox = fitz.Rect(block[0], block[1], block[2], block[3])
                
                # Normalize block text the same way
                norm_block = unicodedata.normalize('NFKD', block_text)
                norm_block = norm_block.replace("\n", " ").replace("\r", " ")
                norm_block = re.sub(r'\s+', ' ', norm_block).strip()
                
                # Check if our search text is within this block
                if norm_text in norm_block:
                    logger.info(f"  ✓ Found text in block on page {page_num}")
                    found_blocks[(page_num, block_idx)] = (block_bbox, norm_block)
        
        logger.info(f"  Stage 1: Found {len(found_blocks)} blocks containing text")
        
        # Step 2: Highlight within found blocks (respects boundaries)
        if found_blocks:
            for (page_num, block_idx), (bbox, norm_block) in found_blocks.items():
                page = doc[page_num - 1]
                search_bbox = bbox
                
                # Try full text first, then sentences
                phrases_to_try = [norm_text]
                sentences = norm_text.split(". ")
                for sent in sentences:
                    s = sent.strip()
                    if len(s) > 20 and s not in phrases_to_try:
                        phrases_to_try.append(s)
                
                for phrase in phrases_to_try:
                    rects = page.search_for(phrase, quads=False)
                    
                    # Filter: only keep rectangles within the block's bounding box
                    valid_rects = []
                    for rect in rects:
                        if (rect.x0 >= search_bbox.x0 - 1 and 
                            rect.y0 >= search_bbox.y0 - 1 and 
                            rect.x1 <= search_bbox.x1 + 1 and 
                            rect.y1 <= search_bbox.y1 + 1):
                            valid_rects.append(rect)
                    
                    if valid_rects:
                        logger.info(f"  ✓ Stage 1: Highlighting {len(valid_rects)} matches (block-aware)")
                        for rect in valid_rects:
                            highlight = page.add_highlight_annot(rect)
                            highlight.set_colors(stroke=(1, 1, 0))
                            highlight.set_opacity(0.35)
                            highlight.update()
                            total_hits += 1
                            highlighted_pages.add(page_num)  # Track this page
                        break
        
        # === HYBRID HIGHLIGHTING: Stage 2 - Global Fallback (Finds Everything) ===
        # If Stage 1 found nothing, use global search to ensure highlights appear
        # This is more permissive but catches all instances
        
        if total_hits == 0:
            logger.warning(f"  ⚠️  Stage 1 found no block matches; falling back to global search...")
            logger.info(f"📍 Stage 2: Searching globally for text (permissive mode)...")
            
            # Try the full text first
            phrases_to_try = [norm_text]
            
            # Add sentence-level phrases
            sentences = norm_text.split(". ")
            for sent in sentences:
                s = sent.strip()
                if len(s) > 20 and s not in phrases_to_try:
                    phrases_to_try.append(s)
            
            # Add phrase-level splits (largest chunks only, no aggressive chunking)
            words = norm_text.split()
            if len(words) > 15:
                # Try 2-3 sentence fragments
                for i in range(0, len(words) - 10, max(7, len(words)//3)):
                    chunk = " ".join(words[i:i+12])
                    if len(chunk) > 30 and chunk not in phrases_to_try:
                        phrases_to_try.append(chunk)
            
            logger.info(f"  Stage 2: Trying {len(phrases_to_try)} phrases...")
            
            for phrase_idx, phrase in enumerate(phrases_to_try, 1):
                for page_num, page in enumerate(doc, 1):
                    rects = page.search_for(phrase, quads=False)
                    if rects:
                        logger.info(f"  ✓ Stage 2: Found phrase {phrase_idx} on page {page_num}: {len(rects)} matches")
                        for rect in rects:
                            highlight = page.add_highlight_annot(rect)
                            highlight.set_colors(stroke=(1, 1, 0))
                            highlight.set_opacity(0.35)
                            highlight.update()
                            total_hits += 1
                            highlighted_pages.add(page_num)  # Track this page
                        break  # Found a match for this phrase, move to next
            
            logger.info(f"  Stage 2: Applied {total_hits} highlights (global mode)")
        
        logger.info(f"✅ Total highlights: {total_hits}")
        if total_hits == 0:
            logger.warning(f"  ⚠️  No highlights found. Search text: {norm_text[:100]}...")
        
        # Get the first page with highlights for auto-navigation
        first_highlighted_page = min(highlighted_pages) if highlighted_pages else 1
        logger.info(f"  📍 First highlighted page: {first_highlighted_page}")
        
        # Save to in-memory buffer
        output = io.BytesIO()
        doc.save(output)
        doc.close()
        output.seek(0)
        logger.info(f"  ✅ PDF generated with highlights (total_hits={total_hits})")

        # Optional logging
        try:
            write_log("cmc_highlight", {
                "source": source,
                "chars_in_text": len(norm_text),
                "total_highlight_hits": total_hits,
                "highlighted_pages": list(highlighted_pages)
            })
        except Exception:
            pass

        # Return PDF with custom headers to indicate which page has highlights
        response = send_file(
            output,
            mimetype="application/pdf",
            as_attachment=False,
            download_name="cmc_highlighted.pdf",
        )
        # Add headers for frontend to jump to the highlighted page
        response.headers['X-Highlight-Page'] = str(first_highlighted_page)
        response.headers['X-Total-Highlights'] = str(total_hits)
        response.headers['X-Highlighted-Pages'] = ','.join(map(str, sorted(highlighted_pages)))
        return response

    except Exception as e:
        return jsonify({
            "error": "Failed to highlight PDF",
            "details": str(e),
        }), 500


'''if __name__ == "__main__":
    # Run on port 8001 (frontend expects this port)
    logger.info("=" * 70)
    logger.info("🚀 STARTING FLASK SERVER")
    logger.info("=" * 70)
    logger.info("📡 Server will run on:")
    logger.info("   • http://127.0.0.1:8001")
    logger.info("   • http://0.0.0.0:8001")
    logger.info("=" * 70)
    logger.info("Frontend React app should be running on http://localhost:3001")
    logger.info("=" * 70)
    logger.info("✅ All systems ready. Waiting for requests...")
    logger.info("=" * 70)'''

@app.route("/pdf/replace-paragraph", methods=["POST"])
def pdf_replace_paragraph():
        """
        Replace a paragraph in a PDF using anchors.
        Supports session-based working copy or traditional JSON/FormData approach.
        Returns the PDF file directly for download.
        """
        try:
            # Check for session ID
            session_id = request.headers.get('X-Session-ID')
            
            # If session ID exists and we have a working copy, use it
            if session_id and session_id in working_copies:
                logger.info(f"🔄 Using working copy for session: {session_id}")
                
                # Get parameters from JSON
                data = request.get_json(force=True) or {}
                page = data.get("page")
                start_anchor = data.get("start_anchor")
                end_anchor = data.get("end_anchor")
                replacement_text = data.get("replacement_text")
                
                # Use the working copy as input
                full_input_path = working_copies[session_id]
                
                logger.info(f"📝 Editing working copy - page: {page}")
                
            elif request.files and 'pdf_file' in request.files:
                # FormData with uploaded PDF (legacy blob-based approach)
                pdf_file = request.files['pdf_file']
                page = int(request.form.get('page'))
                start_anchor = request.form.get('start_anchor')
                end_anchor = request.form.get('end_anchor')
                replacement_text = request.form.get('replacement_text')
                
                logger.info(f"POST /pdf/replace-paragraph (FormData) - page: {page}")
                
                # Save uploaded PDF to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_input:
                    pdf_file.save(tmp_input.name)
                    full_input_path = tmp_input.name
            else:
                # JSON request (original path-based approach)
                data = request.get_json(force=True) or {}
                input_pdf_path = data.get("input_pdf_path")
                page = data.get("page")
                start_anchor = data.get("start_anchor")
                end_anchor = data.get("end_anchor")
                replacement_text = data.get("replacement_text")
                
                logger.info(f"POST /pdf/replace-paragraph (JSON) - input_pdf_path: {input_pdf_path}, page: {page}")
                
                # If client didn't send a path, fall back to the current PDF from config
                if not input_pdf_path:
                    logger.warning("input_pdf_path missing in JSON request; falling back to current PDF")
                    full_input_path = get_current_pdf_path()
                else:
                    # Accept either absolute or project-relative paths
                    if os.path.isabs(input_pdf_path):
                        full_input_path = input_pdf_path
                    else:
                        full_input_path = os.path.join(PROJECT_ROOT, input_pdf_path)
                
                if not full_input_path or not os.path.exists(full_input_path):
                    logger.error(f"PDF file not found: {full_input_path}")
                    return jsonify({"error": f"PDF file not found: {input_pdf_path or full_input_path}"}), 404
            
            # Validate required fields
            if not all([page, start_anchor, end_anchor, replacement_text is not None]):
                logger.error("Missing required fields")
                return jsonify({"error": "Missing required fields"}), 400
            
            # Generate the edited PDF
            output_path = replace_paragraph_anchored(full_input_path, page, start_anchor, end_anchor, replacement_text)
            logger.info(f"PDF replacement successful, output: {output_path}")
            
            # If using session-based working copy, update it in place
            if session_id and session_id in working_copies:
                # Replace the working copy with the new version
                shutil.move(output_path, working_copies[session_id])
                logger.info(f"✅ Updated working copy for session: {session_id}")

                # If we created a temp input file, delete it too
                try:
                    if request.files and 'pdf_file' in request.files:
                        os.unlink(full_input_path)
                        logger.info(f"Deleted temporary input file: {full_input_path}")
                except Exception as e:
                    logger.warning(f"Could not delete temp input file: {e}")

                # Return the updated working copy as a PDF blob so frontend can both update viewer and trigger download
                try:
                    with open(working_copies[session_id], 'rb') as f:
                        pdf_data = f.read()
                except Exception as e:
                    logger.error(f"Failed to read updated working copy: {e}")
                    return jsonify({"error": str(e)}), 500

                write_log("pdf_replace_paragraph_session", {
                    "page": page,
                    "start_anchor": start_anchor[:100],
                    "end_anchor": end_anchor[:100],
                    "replacement_text": replacement_text[:200],
                    "session_id": session_id
                })

                return send_file(
                    io.BytesIO(pdf_data),
                    mimetype="application/pdf",
                    as_attachment=True,
                    download_name=f"cmc_session_{session_id}_edited.pdf"
                )
            else:
                # Traditional approach: return the PDF
                # Read the PDF file into memory
                with open(output_path, 'rb') as f:
                    pdf_data = f.read()
                
                # Delete temporary files
                try:
                    os.unlink(output_path)
                    logger.info(f"Deleted temporary output file: {output_path}")
                    # If we created a temp input file, delete it too
                    if request.files and 'pdf_file' in request.files:
                        os.unlink(full_input_path)
                        logger.info(f"Deleted temporary input file: {full_input_path}")
                except Exception as e:
                    logger.warning(f"Could not delete temp file: {e}")
                
                # Return the PDF file as a download
                write_log("pdf_replace_paragraph", {
                    "page": page,
                    "start_anchor": start_anchor[:100],
                    "end_anchor": end_anchor[:100],
                    "replacement_text": replacement_text[:200],
                    "session_id": session_id
                })
                return send_file(
                    io.BytesIO(pdf_data),
                    mimetype="application/pdf",
                    as_attachment=True,
                    download_name="cmc_edited.pdf"
                )
            
        except ValueError as e:
            logger.error(f"Anchor not found: {str(e)}")
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error in pdf_replace_paragraph: {str(e)}")
            return jsonify({"error": str(e)}), 500


app.run(host="0.0.0.0", port=8001, debug=False)

if __name__ == "__main__":
    # Run on port 8001 (frontend expects this port)
    logger.info("=" * 70)
    logger.info("🚀 STARTING FLASK SERVER")
    logger.info("=" * 70)
    logger.info("📡 Server will run on:")
    logger.info("   • http://127.0.0.1:8001")
    logger.info("   • http://0.0.0.0:8001")
    logger.info("=" * 70)
    logger.info("Frontend React app should be running on http://localhost:3001")
    logger.info("=" * 70)
    logger.info("✅ All systems ready. Waiting for requests...")
    logger.info("=" * 70)