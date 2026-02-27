#!/usr/bin/env python
"""Test PDF upload functionality"""
import requests
import sys
import os

# Test PDF upload
API_BASE = "http://127.0.0.1:8000"

def test_upload():
    """Test uploading a sample PDF"""
    
    # First, check status
    print("1️⃣ Checking PDF status...")
    try:
        res = requests.get(f"{API_BASE}/api/pdf/status")
        print(f"   Status response: {res.json()}")
    except Exception as e:
        print(f"   ❌ Error checking status: {e}")
        return
    
    # Try to upload a test PDF from the PDFs directory
    pdf_path = r"C:\Users\hari.chillakuru\Documents\CMC_Review_part_2\CMC_Review_part_2\CMC_Review_P3_v_backup\backend\cmc_rag\pdfs\hympavzi-epar-public-assessment-report_en (2).pdf"
    
    if not os.path.exists(pdf_path):
        print(f"   ❌ Test PDF not found: {pdf_path}")
        return
    
    print(f"\n2️⃣ Uploading PDF: {pdf_path}")
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': f}
            res = requests.post(f"{API_BASE}/api/pdf/upload", files=files)
            print(f"   Upload response status: {res.status_code}")
            print(f"   Upload response: {res.json()}")
    except Exception as e:
        print(f"   ❌ Error uploading: {e}")
        return
    
    # Check status again
    print(f"\n3️⃣ Checking PDF status after upload...")
    try:
        res = requests.get(f"{API_BASE}/api/pdf/status")
        print(f"   Status response: {res.json()}")
    except Exception as e:
        print(f"   ❌ Error checking status: {e}")

if __name__ == "__main__":
    test_upload()
