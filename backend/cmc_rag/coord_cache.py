import json
import os

CACHE_FILENAME = "coords.json"


def load_cache(store_dir: str):
    path = os.path.join(store_dir, CACHE_FILENAME)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(store_dir: str, cache: dict):
    path = os.path.join(store_dir, CACHE_FILENAME)
    os.makedirs(store_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def clear_cache(store_dir: str):
    """Overwrite the cache with an empty object. Intended to be called at project start to avoid
    accumulating stale or multiple cache files across runs."""
    path = os.path.join(store_dir, CACHE_FILENAME)
    os.makedirs(store_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)


def get_coord(store_dir: str, section_id: str):
    cache = load_cache(store_dir)
    return cache.get(section_id)


def set_coord(store_dir: str, section_id: str, coord: dict):
    cache = load_cache(store_dir)
    cache[section_id] = coord
    save_cache(store_dir, cache)
