import json
import os
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.path.join(BASE_DIR, "result.json")

def load_results():
    if not os.path.exists(RESULTS_FILE):
        return {}
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_file(data):
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def create_result_entry(session_id, data):
    """
    Creates a new entry under the given session_id.
    data should contain: comment, guidelines, suggested_rewrite, etc.
    Returns the new entry_id.
    """
    all_data = load_results()
    
    if session_id not in all_data:
        all_data[session_id] = []
    
    entry_id = str(uuid.uuid4())
    entry = {
        "entry_id": entry_id,
        "timestamp": datetime.now().isoformat(),
        **data
    }
    
    all_data[session_id].append(entry)
    _save_file(all_data)
    return entry_id

def update_result_entry(session_id, entry_id, update_data):
    """
    Updates an existing entry with new fields (e.g. validation results).
    """
    all_data = load_results()
    
    if session_id not in all_data:
        return False
    
    # Find the entry
    for entry in all_data[session_id]:
        if entry.get("entry_id") == entry_id:
            entry.update(update_data)
            entry["last_updated"] = datetime.now().isoformat()
            _save_file(all_data)
            return True
            
    return False

def clear_results():
    """
    Clears all entries in result.json.
    """
    _save_file({})
