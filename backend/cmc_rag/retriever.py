import os
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from .text_cleaner import clean_chunk_with_llm
import fitz
import sys
# Add parent directory to path to import text_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from text_utils import normalize_text
from . import coord_cache
import traceback


class CMCRetriever:
    """
    Lightweight FAISS retriever for CMC documents.
    Used in Problem 3:
      - map reviewer comment → CMC section
      - retrieve context for rewriting
      - support red/green diff generation
    """

    def __init__(self, store=None):
        base_dir = os.path.dirname(__file__)

        if store is None:
            store = os.path.join(base_dir, "faiss_store")

        index_path = os.path.join(store, "index.faiss")
        emb_path = os.path.join(store, "embeddings.npy")
        chunks_path = os.path.join(store, "chunks.pkl")
        meta_path = os.path.join(store, "metadata.pkl")

        if not all(os.path.exists(p) for p in [index_path, emb_path, chunks_path, meta_path]):
            raise RuntimeError(f"FAISS store not found in {store}. Run cmc_rag.indexer first.")

        # Load FAISS + embeddings + metadata
        self.index = faiss.read_index(index_path)
        self.embeddings = np.load(emb_path)

        with open(chunks_path, "rb") as f:
            self.chunks = pickle.load(f)

        with open(meta_path, "rb") as f:
            self.meta = pickle.load(f)

        # Embedding model (same as used for indexing)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        # Coordinate cache directory (same as FAISS store)
        self.store_dir = store

    def get_coords_for_meta(self, meta):
        """Return cached coords for a section meta or compute them by scanning the PDF."""
        section_id = meta.get("id")
        if not section_id:
            return None

        # 1) Try cache
        try:
            cached = coord_cache.get_coord(self.store_dir, section_id)
            if cached:
                return cached
        except Exception:
            pass

        # 2) Compute coordinates by scanning the PDF file
        try:
            pdf_root = os.path.join(os.path.dirname(__file__), "pdfs")
            pdf_path = os.path.join(pdf_root, meta.get("file"))
            if not os.path.exists(pdf_path):
                return None

            doc = fitz.open(pdf_path)
            snippet = normalize_text(meta.get("heading", ""))
            # fallback to first 80 chars of text if heading isn't helpful
            if not snippet:
                snippet = normalize_text(str(meta.get("text", "")))[:80]

            for i, page in enumerate(doc, start=1):
                blocks = page.get_text("blocks")
                for j, b in enumerate(blocks):
                    b_text = normalize_text(b[4])
                    if not b_text:
                        continue
                    # exact or prefix match
                    if snippet and (snippet in b_text or snippet[:30] in b_text):
                        # Expand to nearby blocks for robust bbox
                        start_idx = max(0, j - 1)
                        end_idx = min(len(blocks) - 1, j + 2)
                        sel = blocks[start_idx:end_idx+1]
                        x0 = min(x[0] for x in sel)
                        y0 = min(x[1] for x in sel)
                        x1 = max(x[2] for x in sel)
                        y1 = max(x[3] for x in sel)
                        coord = {"file": meta.get("file"), "page": i, "bbox": [x0, y0, x1, y1]}
                        try:
                            coord_cache.set_coord(self.store_dir, section_id, coord)
                        except Exception:
                            traceback.print_exc()
                        doc.close()
                        return coord
            doc.close()
        except Exception:
            traceback.print_exc()

        return None

    def search(self, query, k=5, clean_chunks=True):
        """
        Semantic search over CMC sections.
        
        Args:
            query: Search query string
            k: Number of results to return
            clean_chunks: If True, use LLM to clean header/footer artifacts from results
            
        Returns: list of dicts {score, text, metadata}
        """
        q_emb = self.model.encode([query], convert_to_numpy=True)
        scores, idxs = self.index.search(q_emb, k)

        results = []
        for score, idx in zip(scores[0], idxs[0]):
            chunk_text = self.chunks[idx]
            
            # Clean the chunk if requested
            if clean_chunks:
                try:
                    from llm_client import llm
                    chunk_text = clean_chunk_with_llm(chunk_text, llm)
                except Exception as e:
                    print(f"Warning: LLM cleaning failed for chunk {idx}: {e}")
                    # Continue with uncleaned text
            
            # Extract only the matching portion from the chunk
            extracted_text = self._extract_matching_text(query, chunk_text)
            
            results.append({
                "score": float(score),
                "text": extracted_text,
                "meta": self.meta[idx]
            })

        return results

    def _extract_matching_text(self, query, chunk_text):
        """
        Extract only the portion of chunk_text that matches the query.
        Removes extra sentences/paragraphs before and after the match.
        
        Args:
            query: The original query/comment text
            chunk_text: The full chunk returned from FAISS
            
        Returns: The matching portion (or original chunk if no good match found)
        """
        if not query or not chunk_text:
            return chunk_text
        
        # Normalize for comparison
        from text_utils import normalize_text
        import logging
        logger = logging.getLogger(__name__)
        
        norm_query = normalize_text(query)
        norm_chunk = normalize_text(chunk_text)
        
        # Strategy 1: Exact match (query text appears directly in chunk)
        if norm_query in norm_chunk:
            # Find the position and extract surrounding context (full sentences)
            start_pos = norm_chunk.find(norm_query)
            end_pos = start_pos + len(norm_query)
            
            # Expand to sentence boundaries for readability
            chunk_for_expand = chunk_text
            # Find sentence start (look back for ". " or start of text)
            sentence_start = 0
            for i in range(start_pos - 1, -1, -1):
                if norm_chunk[i:i+2] == '. ':
                    sentence_start = i + 2
                    break
            
            # Find sentence end (look ahead for ". ")
            sentence_end = len(norm_chunk)
            for i in range(end_pos, len(norm_chunk) - 1):
                if norm_chunk[i:i+2] == '. ':
                    sentence_end = i + 1
                    break
            
            # Map back to original text (accounting for normalization differences)
            # Simple approach: use character ratio
            char_ratio = len(chunk_text) / len(norm_chunk)
            actual_start = max(0, int(sentence_start * char_ratio) - 50)
            actual_end = min(len(chunk_text), int(sentence_end * char_ratio) + 50)
            
            extracted = chunk_text[actual_start:actual_end].strip()
            if len(extracted) > 30:  # Only return if meaningful
                logger.info(f"✓ Extracted matching text (exact match): {len(extracted)} chars")
                return extracted
        
        # Strategy 2: Key word matching - find sentences containing most query words
        key_words = [w.lower() for w in norm_query.split() if len(w) > 3]
        if len(key_words) >= 2:
            sentences = [s.strip() for s in chunk_text.split('.') if s.strip()]
            
            best_match = None
            best_score = 0
            best_range = (0, 1)
            
            # Score each sentence based on how many key words it contains
            for i, sent in enumerate(sentences):
                sent_lower = sent.lower()
                score = sum(1 for w in key_words if w in sent_lower)
                
                if score > best_score:
                    best_score = score
                    best_match = i
            
            # If we found good matches, include the matching sentence plus context
            if best_match is not None and best_score >= 2:
                # Include matched sentence and up to 2 surrounding sentences
                start_idx = max(0, best_match - 0)  # Include 0 sentences before
                end_idx = min(len(sentences), best_match + 2)  # Include 1-2 sentences after
                
                matched_sentences = sentences[start_idx:end_idx+1]
                extracted = '. '.join(matched_sentences).strip()
                
                if extracted and len(extracted) > 30:
                    if not extracted.endswith('.'):
                        extracted += '.'
                    logger.info(f"✓ Extracted matching text (keyword match, score={best_score}): {len(extracted)} chars")
                    return extracted
        
        # Strategy 3: Return original chunk if no good extraction found
        logger.info(f"⚠ No good match found, returning full chunk: {len(chunk_text)} chars")
        return chunk_text

