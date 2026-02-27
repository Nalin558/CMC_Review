import os
import json
from cmc_rag import coord_cache

faiss_store_dir = os.path.join(os.path.dirname(__file__), "cmc_rag", "faiss_store")
path = os.path.join(faiss_store_dir, "coords.json")

# Write a dummy cache entry to simulate previous run
os.makedirs(faiss_store_dir, exist_ok=True)
with open(path, "w", encoding="utf-8") as f:
    json.dump({"DUMMY": {"page": 1}}, f)
print("Wrote dummy cache. Size:", os.path.getsize(path))

# Simulate app startup by calling clear_cache directly (avoid importing Flask dependencies in test)
coord_cache.clear_cache(faiss_store_dir)

# Read file back
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("Cache after clear_cache call:", data)
assert isinstance(data, dict) and len(data) == 0
print("✅ clear_cache cleared the cache as expected.")
