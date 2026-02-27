import os
import pprint

from cmc_rag.retriever import CMCRetriever
from cmc_rag import coord_cache

print("Testing coord cache...")
ret = CMCRetriever()
print(f"Loaded retriever with {len(ret.meta)} entries")

# pick first meta
m = ret.meta[0]
print("Meta sample:")
pp = pprint.PrettyPrinter()
pp.pprint(m)

coord = ret.get_coords_for_meta(m)
print("Coords:")
pp.pprint(coord)

if coord is None:
    print("WARNING: Could not compute coords for first meta — that may be acceptable depending on PDF layout.")
else:
    print("Success: Coordinates computed and returned.")

# Check cache read/write roundtrip
section_id = m.get('id')
cached = coord_cache.get_coord(ret.store_dir, section_id)
print("Cached:")
pp.pprint(cached)

print("Done")
