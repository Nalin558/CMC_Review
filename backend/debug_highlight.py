#!/usr/bin/env python
"""Debug highlighting issue - comparing two passages"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re
import unicodedata
import fitz

# The two passages from the user
passage_that_fails = """The finished product (FP) is presented as solution for injection containing 150 mg/mL of marstacimab as active substance (AS). Other ingredients are: Disodium edetate, L-Histidine, L-Histidine monohydrochloride, Polysorbate 80 (PS80), sucrose, water for injections. The product is available in a prefilled syringe and a prefilled pen containing 1 mL solution for injection"""

passage_that_works = """Treatment of haemophilia is primarily through replacement of the missing FVIII or FIX. The replacement factor products are commonly standard half-life (SHL) or extended half-life (EHL) recombinant factor products, but plasma-derived products of various purities are still in use. Treatment with the replacement coagulation factor can either be episodic, treating bleeding episodes on-demand as they occur, or prophylactic, preventing bleeding episodes by a regular schedule of FVIII or FIX infusions to maintain factor levels in a range >1%. Significant evidence exists that prophylactic treatment prevents bleeding episodes and the associated joint damage that is a major morbidity in haemophilic patients"""

PDF_PATH = r"C:\Users\nalin.mittal\Documents\CMC_Application\CMC_Review\backend\uploads\hympavzi_1.pdf"

def normalize_text(text):
    """Apply the exact same normalization from app.py"""
    norm_text = unicodedata.normalize('NFKD', text)
    norm_text = norm_text.replace("\n", " ").replace("\r", " ")
    norm_text = re.sub(r'\s+', ' ', norm_text).strip()
    return norm_text

def extract_phrases(norm_text):
    """Extract phrases using the same logic as app.py"""
    phrases = []
    
    # First, try to split by ". " to get sentence-like chunks
    for part in norm_text.split(". "):
        p = part.strip()
        if len(p) > 15:  # Minimum length for better matching
            phrases.append(p)
    
    # If we got too few phrases (single paragraph), use sliding window
    if len(phrases) < 2:
        words = norm_text.split(" ")
        window_size = 10
        step = 5
        if len(words) <= window_size:
            phrases = [norm_text] if len(norm_text) > 15 else []
        else:
            for i in range(0, len(words), step):
                chunk_words = words[i : i + window_size]
                if not chunk_words:
                    break
                chunk_str = " ".join(chunk_words)
                if len(chunk_str) > 15:
                    phrases.append(chunk_str)
    
    return phrases

def test_passage(passage, passage_name):
    """Test a passage against the PDF"""
    print("\n" + "=" * 90)
    print(f"TESTING: {passage_name}")
    print("=" * 90)
    
    # Normalize
    norm_text = normalize_text(passage)
    print(f"\n✓ Original length: {len(passage)} chars")
    print(f"✓ Normalized length: {len(norm_text)} chars")
    print(f"✓ Normalized text: {norm_text[:100]}...")
    
    # Extract phrases
    phrases = extract_phrases(norm_text)
    print(f"\n✓ Extracted {len(phrases)} phrases:")
    for i, phrase in enumerate(phrases[:5], 1):  # Show first 5
        print(f"   {i}. [{len(phrase)} chars] {phrase[:60]}...")
    
    # Open PDF and search
    print(f"\n📄 Opening PDF: {PDF_PATH}")
    doc = fitz.open(PDF_PATH)
    print(f"✓ PDF has {len(doc)} pages\n")
    
    total_hits = 0
    found_pages = set()
    
    # Test exact matching for each phrase
    print("🔍 SEARCHING FOR EXACT PHRASE MATCHES:\n")
    for phrase_idx, phrase in enumerate(phrases, 1):
        matches = 0
        for page_num, page in enumerate(doc):
            rects = page.search_for(phrase, quads=False)
            if rects:
                matches += len(rects)
                found_pages.add(page_num)
                total_hits += len(rects)
        
        status = "✓ FOUND" if matches > 0 else "✗ NOT FOUND"
        print(f"   Phrase {phrase_idx}: {matches} matches - {status}")
        print(f"     Text: {phrase[:70]}...")
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total matches found: {total_hits}")
    print(f"   Pages with matches: {sorted(found_pages)}")
    
    if total_hits == 0:
        print(f"\n   ⚠️  NO MATCHES FOUND! Testing with KEY PHRASES (fallback)...")
        
        # Try with key phrases
        words = norm_text.split()
        key_phrases = []
        for i in range(len(words) - 2):
            key_phrases.append(" ".join(words[i:i+3]))
            if i < len(words) - 4:
                key_phrases.append(" ".join(words[i:i+4]))
        
        key_phrases = list(set(key_phrases))  # Remove duplicates
        print(f"\n   Generated {len(key_phrases)} key phrases, testing first 10...")
        
        key_matches = 0
        for key_phrase in key_phrases[:10]:
            matches = 0
            for page in doc:
                rects = page.search_for(key_phrase, quads=False)
                if rects:
                    matches += len(rects)
                    key_matches += len(rects)
            
            if matches > 0:
                print(f"   ✓ '{key_phrase}' - {matches} matches")
        
        print(f"\n   Key phrase matches: {key_matches}")
        
        if key_matches == 0:
            print(f"\n   🔴 DIAGNOSIS: Text does not exist in PDF!")
            print(f"\n   Let me search for similar phrases in the PDF...")
            # Search for smaller key words
            important_words = [w for w in words if len(w) >= 4][:5]
            print(f"   Important words to search: {important_words}")
            
            for word in important_words:
                matches = 0
                for page_num, page in enumerate(doc):
                    rects = page.search_for(word, quads=False)
                    if rects:
                        matches += len(rects)
                
                if matches > 0:
                    print(f"   ✓ Found word '{word}' on {matches} instances")
                else:
                    print(f"   ✗ Word '{word}' not found")
    
    doc.close()

# Run tests
print("\n" + "=" * 90)
print("HIGHLIGHTING DEBUG: COMPARING TWO PASSAGES")
print("=" * 90)

test_passage(passage_that_fails, "PASSAGE THAT FAILS (Finished Product)")
test_passage(passage_that_works, "PASSAGE THAT WORKS (Treatment of haemophilia)")

print("\n" + "=" * 90)
print("DEBUG COMPLETE")
print("=" * 90)
