import os
import pickle
import faiss
import numpy as np

from sentence_transformers import SentenceTransformer
from .pdf_parser import extract_text_from_pdf
from .section_parser import split_into_sections


class ICHIndexer:

    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def index_root(
        self,
        ich_root=None,
        out_folder=None
    ):
        # ------------------------------------------------------------------
        # Resolve default paths RELATIVE to this file
        # ------------------------------------------------------------------
        base_dir = os.path.dirname(__file__)

        if ich_root is None:
            ich_root = os.path.join(base_dir, "pdfs")

        if out_folder is None:
            out_folder = os.path.join(base_dir, "faiss_store")

        print(f"📁 Using ICH root: {ich_root}")
        print(f"📁 Output FAISS store: {out_folder}")

        chunks = []
        metadata = []
        section_counter = 0

        # --------------------------------------------------------------
        # Process Q / S / E / M guidelines
        # --------------------------------------------------------------
        for category in ["Q", "S", "E", "M"]:
            category_path = os.path.join(ich_root, category)

            if not os.path.exists(category_path):
                print(f"⚠️  WARNING: Folder not found → {category_path}")
                continue

            pdf_files = [f for f in os.listdir(category_path) if f.lower().endswith(".pdf")]
            print(f"\n📚 Category {category}: {len(pdf_files)} PDFs found")

            for fname in pdf_files:
                pdf_path = os.path.join(category_path, fname)
                print(f" → Processing PDF: {pdf_path}")

                # Extract text
                text = extract_text_from_pdf(pdf_path)
                if not text.strip():
                    print("   ⚠️ Extracted EMPTY TEXT! Skipping.")
                    continue

                # Split into guideline sections
                sections = split_into_sections(text)
                if not sections:
                    print("   ⚠️ No sections detected. Skipping.")
                    continue

                for sec in sections:
                    if not sec.strip():
                        continue

                    section_counter += 1
                    section_id = f"{category}-{section_counter}"
                    heading = sec.split("\n", 1)[0].strip()[:200]

                    chunks.append(sec)
                    metadata.append({
                        "id": section_id,
                        "category": category,
                        "file": fname,
                        "heading": heading
                    })

        # --------------------------------------------------------------
        # Build embeddings
        # --------------------------------------------------------------
        print("\n🧠 Embedding chunks...")
        embeddings = self.model.encode(
            chunks,
            convert_to_numpy=True,
            show_progress_bar=True
        )

        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        # Ensure output folder exists
        os.makedirs(out_folder, exist_ok=True)

        # Save everything
        faiss.write_index(index, os.path.join(out_folder, "index.faiss"))
        np.save(os.path.join(out_folder, "embeddings.npy"), embeddings)

        with open(os.path.join(out_folder, "chunks.pkl"), "wb") as f:
            pickle.dump(chunks, f)

        with open(os.path.join(out_folder, "metadata.pkl"), "wb") as f:
            pickle.dump(metadata, f)

        print("\n✅ Indexing Complete!")
        print(f"📦 Total sections indexed: {len(chunks)}")
        print(f"📌 Stored inside: {out_folder}")
if __name__ == "__main__":
    indexer = ICHIndexer()
    indexer.index_root()
