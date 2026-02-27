import json
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "session_logs.jsonl")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def write_log(event_type, payload):
    entry = {
        "time": datetime.utcnow().isoformat(),
        "event": event_type,
        "data": payload
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
