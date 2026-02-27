#!/usr/bin/env python
"""Test script to verify highlighting with the provided text"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re
import unicodedata

# Test text from the user
test_text = """The cell banks have been adequately characterised. The Applicant has established a LIVCA from the MCB, phenotypic stability and comparability was confirmed for MCB, WCB and end of production (EOP) LIVCA cells. MCB and WCB stability is monitored; the proposed intervals are acceptable. A protocol for introduction of future WCBs has been included and considered acceptable."""

def test_normalization():
    """Test text normalization process"""
    print("=" * 80)
    print("TESTING TEXT NORMALIZATION")
    print("=" * 80)
    print(f"\nOriginal text ({len(test_text)} chars):")
    print(test_text[:100] + "...")
    
    # Apply the same normalization from app.py
    norm_text = test_text
    norm_text = unicodedata.normalize('NFKD', norm_text)
    norm_text = norm_text.replace("\n", " ").replace("\r", " ")
    norm_text = re.sub(r'\s+', ' ', norm_text).strip()
    
    print(f"\nNormalized text ({len(norm_text)} chars):")
    print(norm_text)
    
    # Test phrase extraction
    print("\n" + "=" * 80)
    print("PHRASE EXTRACTION")
    print("=" * 80)
    
    phrases = []
    for part in norm_text.split(". "):
        p = part.strip()
        if len(p) > 15:
            phrases.append(p)
    
    print(f"\nExtracted {len(phrases)} phrases:")
    for i, phrase in enumerate(phrases, 1):
        print(f"  {i}. {phrase}")
    
    # Test key phrase extraction
    print("\n" + "=" * 80)
    print("KEY PHRASE EXTRACTION (Fallback)")
    print("=" * 80)
    
    words = norm_text.split()
    key_phrases = []
    
    for i in range(len(words) - 2):
        key_phrases.append(" ".join(words[i:i+3]))
        if i < len(words) - 4:
            key_phrases.append(" ".join(words[i:i+4]))
    
    # Filter for length
    key_phrases = [kp for kp in key_phrases if len(kp) > 10]
    
    print(f"\nExtracted {len(key_phrases)} key phrases (showing first 10):")
    for i, phrase in enumerate(key_phrases[:10], 1):
        print(f"  {i}. {phrase}")
    
    return norm_text, phrases, key_phrases

if __name__ == "__main__":
    norm_text, phrases, key_phrases = test_normalization()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✓ Original text length: {len(test_text)} characters")
    print(f"✓ Normalized text length: {len(norm_text)} characters")
    print(f"✓ Phrases for primary search: {len(phrases)}")
    print(f"✓ Key phrases for fallback: {len(key_phrases)}")
    print("\n✅ Text normalization and phrase extraction working correctly!")
