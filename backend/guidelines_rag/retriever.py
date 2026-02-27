import os
import re
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# ------------------------------------------------------------
# Helpers for symbolic reasoning (Roman numerals, CTD sections)
# ------------------------------------------------------------

ROMAN_MAP = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10
}

def normalize_query(q: str):
    q = q.strip().upper()

    # Roman numeral?
    if q in ROMAN_MAP:
        return q

    # Numeric / CTD code?
    m = re.search(r"(\d+(\.\d+)*[A-Z0-9\.]*)", q)
    if m:
        return m.group(1)

    return q


def extract_heading(chunk: str) -> str:
    """Return the heading (first line)."""
    return chunk.split("\n", 1)[0].strip()


# ------------------------------------------------------------
# Hybrid Retriever
# ------------------------------------------------------------

class ICHRetriever:

    def __init__(self, store=None):
        # Use absolute path relative to this file's location
        if store is None:
            base_dir = os.path.dirname(__file__)
            store = os.path.join(base_dir, "faiss_store")
        
        # Resolve to absolute path
        store = os.path.abspath(store)
        
        if not os.path.exists(store):
            raise FileNotFoundError(f"FAISS store directory not found: {store}")
        
        index_path = os.path.join(store, "index.faiss")
        embeddings_path = os.path.join(store, "embeddings.npy")
        chunks_path = os.path.join(store, "chunks.pkl")
        metadata_path = os.path.join(store, "metadata.pkl")
        
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index not found: {index_path}")
        
        self.index = faiss.read_index(index_path)
        self.embeddings = np.load(embeddings_path)

        with open(chunks_path, "rb") as f:
            self.chunks = pickle.load(f)

        with open(metadata_path, "rb") as f:
            self.meta = pickle.load(f)

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def symbolic_score(self, query_norm, chunk_heading, meta):
        """Boost score based on structural matches."""

        score = 0.0

        h = chunk_heading.upper()

        # 1. EXACT HEADING MATCH
        if h.startswith(query_norm):
            score += 1.0

        # 2. ROMAN numeral -> numeric bridging
        if query_norm in ROMAN_MAP:
            num = str(ROMAN_MAP[query_norm])
            if h.startswith(num + ".") or h.startswith(num + " "):
                score += 0.9

        # 3. Partial structured match: 3.2.P.3
        if query_norm in h:
            score += 0.5

        # 4. Keyword match
        query_words = query_norm.split()
        for w in query_words:
            if len(w) > 3 and w in h:
                score += 0.2

        # 5. Category boost (Q, S, E, M)
        if "category" in meta and meta["category"].upper() in ["Q", "S", "E", "M"]:
            score += 0.05

        return score

    def search(self, query, k=5, category=None):
        # ------------------------------
        # Step 1 — Semantic FAISS Search
        # ------------------------------
        q_emb = self.model.encode([query], convert_to_numpy=True)
        scores, idxs = self.index.search(q_emb, 50)

        query_norm = normalize_query(query)

        ranked = []

        # ------------------------------
        # Step 2 — Combine with symbolic boosts
        # ------------------------------
        for semantic_score, idx in zip(scores[0], idxs[0]):

            meta = self.meta[idx]
            heading = extract_heading(self.chunks[idx])

            # category filter
            if category and meta["category"] != category:
                continue

            # compute symbolic confidence
            sym_score = self.symbolic_score(query_norm, heading, meta)

            # final hybrid score
            final_score = (0.7 * float(semantic_score)) + (0.3 * sym_score)

            ranked.append((final_score, self.chunks[idx], meta))

        # sort descending
        ranked = sorted(ranked, key=lambda x: -x[0])

        return ranked[:k]
