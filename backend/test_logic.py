import sys
import os

# Add current dir to sys.path
sys.path.append(os.getcwd())

try:
    print("Importing result_manager...")
    import result_manager
    print("result_manager imported.")
    
    print("Testing create_result_entry...")
    eid = result_manager.create_result_entry("test_session", {"foo": "bar"})
    print(f"Entry ID: {eid}")
    
    print("Importing app...")
    from app import app, load_cmc_document, CMC_PDF_PATH
    print("app imported.")
    
    # Test loading cmc_full.json
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cmc_full.json")
    print(f"Loading {json_path}...")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-16") as f:
            c = f.read()
            import json
            json.loads(c)
        print("cmc_full.json loaded and parsed successfully.")
    else:
        print("cmc_full.json NOT FOUND.")

except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
