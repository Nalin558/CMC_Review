"""
PDF Manager - Handles PDF uploads, path updates, and cleanup
"""
import os
import json
import shutil
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Configuration
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
PDF_CONFIG_FILE = os.path.join(UPLOADS_DIR, "pdf_config.json")

# Files that need PDF_PATH updates
FILES_WITH_PDF_PATHS = [
    "debug_highlight.py",
    "test_replace_hybrid.py",
    "test_replace_page80.py",
]

def ensure_uploads_dir():
    """Create uploads directory if it doesn't exist"""
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    logger.info(f"✅ Uploads directory ensured: {UPLOADS_DIR}")

def get_pdf_config():
    """Load current PDF configuration"""
    ensure_uploads_dir()
    if os.path.exists(PDF_CONFIG_FILE):
        try:
            with open(PDF_CONFIG_FILE, 'r') as f:
                content = f.read().strip()
                if not content:  # File is empty
                    logger.warning(f"⚠️  PDF config file is empty, returning defaults")
                    return {"current_pdf": None, "current_pdf_path": None}
                return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse PDF config JSON: {e}")
            logger.info(f"   Resetting to empty config")
            return {"current_pdf": None, "current_pdf_path": None}
        except Exception as e:
            logger.error(f"❌ Failed to load PDF config: {e}")
            return {"current_pdf": None, "current_pdf_path": None}
    return {"current_pdf": None, "current_pdf_path": None}

def save_pdf_config(config):
    """Save PDF configuration"""
    ensure_uploads_dir()
    try:
        # Ensure config is valid dict with required keys
        if not isinstance(config, dict):
            logger.error(f"❌ Invalid config type: {type(config)}, expected dict")
            config = {"current_pdf": None, "current_pdf_path": None}
        
        # Ensure required keys exist
        if "current_pdf" not in config:
            config["current_pdf"] = None
        if "current_pdf_path" not in config:
            config["current_pdf_path"] = None
            
        # Write to file with proper formatting
        with open(PDF_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Verify the file was written correctly
        with open(PDF_CONFIG_FILE, 'r') as f:
            verify_content = f.read()
            if not verify_content.strip():
                logger.error(f"❌ Config file written but empty!")
            else:
                logger.info(f"✅ PDF config saved: {config}")
    except Exception as e:
        logger.error(f"❌ Failed to save PDF config: {e}")
        import traceback
        logger.error(traceback.format_exc())

def update_pdf_paths_in_files(pdf_path):
    """Update PDF_PATH in all relevant Python files"""
    backend_dir = os.path.dirname(__file__)
    
    # Escape backslashes in path for Python string
    escaped_path = pdf_path.replace("\\", "\\\\")
    logger.info(f"📝 Updating PDF paths in files to: {escaped_path}")
    
    for filename in FILES_WITH_PDF_PATHS:
        filepath = os.path.join(backend_dir, filename)
        logger.info(f"   Checking file: {filepath}")
        
        if not os.path.exists(filepath):
            logger.warning(f"⚠️  File not found: {filepath}")
            continue
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace PDF_PATH = r"..." with new path
            import re
            pattern = r'PDF_PATH\s*=\s*r?"[^"]*"'
            new_content = re.sub(
                pattern,
                f'PDF_PATH = r"{escaped_path}"',
                content
            )
            
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                logger.info(f"✅ Updated PDF_PATH in {filename}")
            else:
                logger.warning(f"⚠️  Could not find PDF_PATH pattern in {filename}")
                
        except Exception as e:
            logger.error(f"❌ Error updating {filename}: {e}")

def cleanup_old_pdf(old_pdf_path):
    """
    Delete all old PDFs:
    1. From uploads folder (ALL PDFs)
    2. The specific old_pdf_path if provided
    """
    # Delete ALL PDFs from uploads folder
    logger.info(f"🗑️  Cleaning ALL PDFs from uploads folder...")
    ensure_uploads_dir()
    try:
        for file in os.listdir(UPLOADS_DIR):
            if file.endswith('.pdf'):
                file_path = os.path.join(UPLOADS_DIR, file)
                try:
                    os.remove(file_path)
                    logger.info(f"   ✅ Deleted from uploads: {file}")
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not delete {file}: {e}")
    except Exception as e:
        logger.warning(f"⚠️  Error cleaning uploads folder: {e}")
    
    # Delete specific old PDF path if provided
    if old_pdf_path and os.path.exists(old_pdf_path):
        try:
            os.remove(old_pdf_path)
            logger.info(f"✅ Deleted old PDF: {old_pdf_path}")
        except Exception as e:
            logger.error(f"❌ Failed to delete old PDF: {e}")
    
    # Also clean up temp PDFs in frontend public dir
    frontend_public = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public")
    try:
        for file in os.listdir(frontend_public):
            if file.startswith("tmp") and file.endswith(".pdf"):
                temp_pdf = os.path.join(frontend_public, file)
                os.remove(temp_pdf)
                logger.info(f"✅ Deleted temp PDF: {temp_pdf}")
    except Exception as e:
        logger.warning(f"⚠️  Could not clean temp PDFs: {e}")

def save_uploaded_pdf(file_obj, filename):
    """
    Save uploaded PDF file to uploads directory
    - Deletes ALL old PDFs from uploads first (keep only current)
    - Copies to frontend/public/cmc.pdf for display
    - Copies to backend/cmc_rag/pdfs/ for FAISS indexing
    - Rebuilds FAISS index and regenerates cmc_full.json
    Returns the absolute path to the saved file
    """
    ensure_uploads_dir()
    logger.info(f"💾 save_uploaded_pdf called with filename: {filename}")
    
    # Get current config to find old PDF
    config = get_pdf_config()
    old_pdf_path = config.get("current_pdf_path")
    logger.info(f"   Old PDF path: {old_pdf_path}")
    
    # STEP 1: Clean ALL PDFs from uploads folder FIRST
    logger.info(f"   Step 1: Cleaning ALL old PDFs from uploads folder...")
    try:
        for file in os.listdir(UPLOADS_DIR):
            if file.endswith('.pdf') and file != 'pdf_config.json':
                file_path = os.path.join(UPLOADS_DIR, file)
                try:
                    os.remove(file_path)
                    logger.info(f"   ✅ Deleted old PDF: {file}")
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not delete {file}: {e}")
    except Exception as e:
        logger.warning(f"⚠️  Error cleaning uploads folder: {e}")
    
    # STEP 2: Save new PDF to uploads directory
    logger.info(f"   Step 2: Saving new PDF to uploads...")
    new_filename = filename
    new_pdf_path = os.path.join(UPLOADS_DIR, new_filename)
    logger.info(f"   New PDF path: {new_pdf_path}")
    
    # If file exists, add timestamp
    if os.path.exists(new_pdf_path):
        import time
        name, ext = os.path.splitext(filename)
        new_filename = f"{name}_{int(time.time())}{ext}"
        new_pdf_path = os.path.join(UPLOADS_DIR, new_filename)
        logger.info(f"   File exists, using timestamped name: {new_filename}")
    
    try:
        logger.info(f"   Saving file to: {new_pdf_path}")
        file_obj.save(new_pdf_path)
        logger.info(f"✅ Saved uploaded PDF: {new_pdf_path}")
        logger.info(f"   File exists after save: {os.path.exists(new_pdf_path)}")
        logger.info(f"   File size: {os.path.getsize(new_pdf_path) if os.path.exists(new_pdf_path) else 'N/A'}")
        
        # STEP 3: Copy to frontend/public/cmc.pdf for display
        logger.info(f"   Step 3: Copying to frontend/public/cmc.pdf for display...")
        try:
            frontend_public = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public", "cmc.pdf")
            logger.info(f"   Frontend path: {frontend_public}")
            shutil.copy2(new_pdf_path, frontend_public)
            logger.info(f"✅ Copied PDF to frontend: {frontend_public}")
        except Exception as e:
            logger.warning(f"⚠️  Could not copy to frontend: {e}")
        
        # STEP 4: Copy to backend/cmc_rag/pdfs/ for FAISS indexing (CRITICAL!)
        logger.info(f"   Step 4: Copying to backend/cmc_rag/pdfs/ (delete old, add new)...")
        try:
            indexing_pdfs_dir = os.path.join(os.path.dirname(__file__), "cmc_rag", "pdfs")
            os.makedirs(indexing_pdfs_dir, exist_ok=True)
            
            # Delete ALL old PDFs in the indexing directory
            logger.info(f"   Cleaning ALL old PDFs from indexing directory...")
            for old_file in os.listdir(indexing_pdfs_dir):
                if old_file.endswith('.pdf'):
                    old_file_path = os.path.join(indexing_pdfs_dir, old_file)
                    try:
                        os.remove(old_file_path)
                        logger.info(f"   ✅ Deleted from indexing dir: {old_file}")
                    except Exception as e:
                        logger.warning(f"   ⚠️  Could not delete {old_file}: {e}")
            
            # Copy new PDF to indexing directory with simple name
            indexing_pdf_path = os.path.join(indexing_pdfs_dir, "cmc.pdf")
            shutil.copy2(new_pdf_path, indexing_pdf_path)
            logger.info(f"✅ Copied PDF to indexing directory: {indexing_pdf_path}")
        except Exception as e:
            logger.warning(f"⚠️  Could not copy to indexing directory: {e}")
        
        # STEP 5: Update code files with new path
        logger.info(f"   Step 5: Updating PDF paths in code files...")
        update_pdf_paths_in_files(new_pdf_path)
        
        # STEP 6: Save new config (DO THIS BEFORE FAISS rebuild so frontend gets updated even if FAISS fails)
        logger.info(f"   Step 6: Saving new config...")
        config["current_pdf"] = new_filename
        config["current_pdf_path"] = new_pdf_path
        save_pdf_config(config)
        logger.info(f"   Config saved: {config}")
        
        # STEP 7: Reindex the new PDF for RAG (rebuilds FAISS from backend/cmc_rag/pdfs/)
        logger.info(f"   Step 7: Reindexing PDF for RAG system...")
        reindex_result = reindex_pdf(new_pdf_path)
        if reindex_result:
            logger.info(f"✅ FAISS reindex successful")
        else:
            logger.warning(f"⚠️  FAISS reindex encountered issues, will rebuild on first search")
        
        logger.info(f"✅ PDF upload process complete! Only {new_filename} remains in uploads.")
        return new_pdf_path
        
    except Exception as e:
        logger.error(f"❌ Error saving uploaded PDF: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

def get_current_pdf_path():
    """Get path to current PDF"""
    config = get_pdf_config()
    return config.get("current_pdf_path")

def has_pdf():
    """Check if a PDF is currently loaded"""
    path = get_current_pdf_path()
    return path is not None and os.path.exists(path)


def reindex_pdf(pdf_path):
    """
    Reindex a PDF for the CMC RAG system:
    1. Generate cmc_full.json from the PDF text
    2. Rebuild FAISS index from backend/cmc_rag/pdfs/
    """
    try:
        logger.info(f"🔄 Reindexing PDF: {pdf_path}")
        
        import json
        import fitz  # PyMuPDF
        
        base_dir = os.path.dirname(__file__)
        
        # Step 1: Generate cmc_full.json with page-by-page text
        logger.info(f"   Step 1: Generating cmc_full.json from new PDF...")
        pages_data = []
        
        try:
            # Extract page-by-page text using PyMuPDF
            doc = fitz.open(pdf_path)
            logger.info(f"   PDF opened successfully, pages: {doc.page_count}")
            for page_num in range(doc.page_count):
                page = doc[page_num]
                page_text = page.get_text("text") or ""
                pages_data.append({
                    "page_number": page_num + 1,
                    "text": page_text
                })
            doc.close()
            logger.info(f"✅ Extracted {len(pages_data)} pages from PDF")
        except Exception as e:
            logger.error(f"❌ Error extracting pages with PyMuPDF: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
        # Save cmc_full.json with the new PDF's content
        try:
            cmc_json_path = os.path.join(base_dir, "cmc_full.json")
            cmc_data = {
                "file": os.path.basename(pdf_path),
                "num_pages": len(pages_data),
                "pages": pages_data
            }
            
            with open(cmc_json_path, 'w', encoding='utf-8') as f:
                json.dump(cmc_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Saved cmc_full.json with {len(pages_data)} pages")
            logger.info(f"   File: {cmc_json_path}")
        except Exception as e:
            logger.error(f"❌ Error saving cmc_full.json: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
        # Step 2: Rebuild FAISS index
        logger.info(f"   Step 2: Rebuilding FAISS index...")
        try:
            from cmc_rag.indexer import CMCIndexer
            
            # Clear ALL FAISS cache files to ensure fresh index
            faiss_dir = os.path.join(base_dir, "cmc_rag", "faiss_store")
            logger.info(f"   🗑️  Clearing ALL old FAISS cache files...")
            
            # List of all FAISS cache files to delete
            faiss_files_to_delete = [
                "chunks.pkl",
                "coords.json",
                "embeddings.npy",
                "index.faiss",
                "metadata.pkl"
            ]
            
            # Delete individual FAISS files
            for fname in faiss_files_to_delete:
                fpath = os.path.join(faiss_dir, fname)
                if os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                        logger.info(f"   ✅ Deleted: {fname}")
                    except Exception as e:
                        logger.warning(f"   ⚠️  Could not delete {fname}: {e}")
            
            # Delete FAISS store directory if it exists
            if os.path.exists(faiss_dir):
                try:
                    import shutil
                    shutil.rmtree(faiss_dir)
                    logger.info(f"   ✅ Deleted FAISS store directory")
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not delete FAISS directory: {e}")
            
            # Clear coord cache file
            coord_cache_file = os.path.join(base_dir, "cmc_rag", "coord_cache.pkl")
            if os.path.exists(coord_cache_file):
                try:
                    os.remove(coord_cache_file)
                    logger.info(f"   ✅ Deleted coord_cache.pkl")
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not delete coord_cache.pkl: {e}")
            
            # Clear __pycache__ in cmc_rag to force module reloading
            pycache_dir = os.path.join(base_dir, "cmc_rag", "__pycache__")
            if os.path.exists(pycache_dir):
                try:
                    import shutil
                    shutil.rmtree(pycache_dir)
                    logger.info(f"   ✅ Cleared __pycache__ for module reload")
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not clear __pycache__: {e}")
            
            # Now rebuild FAISS index from backend/cmc_rag/pdfs/
            pdfs_dir = os.path.join(base_dir, "cmc_rag", "pdfs")
            logger.info(f"   📁 Checking PDFs directory: {pdfs_dir}")
            logger.info(f"   📁 Directory exists: {os.path.exists(pdfs_dir)}")
            
            if not os.path.exists(pdfs_dir):
                logger.error(f"   ❌ PDFs directory does not exist: {pdfs_dir}")
                logger.warning(f"   ⚠️  Creating empty directory...")
                os.makedirs(pdfs_dir, exist_ok=True)
                return False
            
            pdf_list = [f for f in os.listdir(pdfs_dir) if f.lower().endswith('.pdf')]
            logger.info(f"   📚 PDFs in folder: {pdf_list}")
            
            if not pdf_list:
                logger.error(f"   ❌ No PDFs found in {pdfs_dir}")
                logger.warning(f"   ⚠️  Make sure PDF is copied to this directory")
                return False
            
            logger.info(f"   🔄 Starting CMCIndexer.index_root()...")
            indexer = CMCIndexer()
            indexer.index_root(pdfs_dir)
            
            logger.info(f"✅ FAISS index rebuilt successfully with ONLY NEW PDF")
            
        except ImportError as e:
            logger.error(f"   ❌ Import error rebuilding FAISS: {e}")
            import traceback
            logger.error(traceback.format_exc())
            logger.warning(f"   ⚠️  FAISS will be rebuilt on first search")
            return False
        except Exception as e:
            logger.error(f"   ❌ Error rebuilding FAISS: {e}")
            import traceback
            logger.error(traceback.format_exc())
            logger.warning(f"   ⚠️  FAISS will be rebuilt on first search")
            return False
        
        logger.info(f"✅ PDF reindexing complete!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error reindexing PDF: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
