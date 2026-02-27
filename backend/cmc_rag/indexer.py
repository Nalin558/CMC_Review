import os
import pickle
import faiss
import numpy as np

from sentence_transformers import SentenceTransformer
from .pdf_parser import extract_text_from_pdf
from .section_parser import split_into_sections


class CMCIndexer:

    def __init__(self):
        # same embedding model as ICH RAG
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def index_root(
        self,
        cmc_root=None,
        out_folder=None
    ):
        # Determine paths relative to this file
        base_dir = os.path.dirname(__file__)

        if cmc_root is None:
            cmc_root = os.path.join(base_dir, "pdfs")

        if out_folder is None:
            out_folder = os.path.join(base_dir, "faiss_store")

        print(f"\n📁 Using CMC root: {cmc_root}")
        print(f"📁 Output FAISS store: {out_folder}")

        chunks = []
        metadata = []
        section_counter = 0

        # -------------------------------------------------------------------
        # Loop through all PDFs inside cmc_rag/pdfs
        # -------------------------------------------------------------------
        pdf_files = [f for f in os.listdir(cmc_root) if f.lower().endswith(".pdf")]
        print(f"\n📚 Found {len(pdf_files)} CMC PDFs")

        for fname in pdf_files:
            pdf_path = os.path.join(cmc_root, fname)
            print(f" → Processing PDF: {pdf_path}")

            # Extract text from PDF
            text = extract_text_from_pdf(pdf_path)
            if not text.strip():
                print("   ⚠️ Extracted EMPTY TEXT! Skipping.")
                continue

            # Split into structured sections
            sections = split_into_sections(text)
            if not sections:
                print("   ⚠️ No sections detected. Skipping.")
                continue

            # Store chunks + metadata
            for sec in sections:
                if not sec.strip():
                    continue

                section_counter += 1
                section_id = f"CMC-{section_counter}"

                heading = sec.split("\n", 1)[0].strip()[:200]

                chunks.append(sec)
                metadata.append({
                    "id": section_id,
                    "file": fname,
                    "heading": heading
                })

        # -------------------------------------------------------------------
        # Build embeddings
        # -------------------------------------------------------------------
        print("\n🧠 Embedding sections...")
        embeddings = self.model.encode(
            chunks,
            convert_to_numpy=True,
            show_progress_bar=True
        )

        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        # Ensure FAISS output directory exists
        os.makedirs(out_folder, exist_ok=True)

        # Save the full store
        faiss.write_index(index, os.path.join(out_folder, "index.faiss"))
        np.save(os.path.join(out_folder, "embeddings.npy"), embeddings)

        with open(os.path.join(out_folder, "chunks.pkl"), "wb") as f:
            pickle.dump(chunks, f)

        with open(os.path.join(out_folder, "metadata.pkl"), "wb") as f:
            pickle.dump(metadata, f)

        print("\n✅ CMC Indexing Complete!")
        print(f"📦 Total sections indexed: {len(chunks)}")
        print(f"📌 Stored inside: {out_folder}")


# Run from terminal: python -m cmc_rag.indexer
if __name__ == "__main__":
    CMCIndexer().index_root()
