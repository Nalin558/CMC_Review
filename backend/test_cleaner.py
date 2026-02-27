"""
Test script to verify the LLM-based text cleaner works correctly.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from cmc_rag.text_cleaner import _has_header_footer_patterns, _regex_clean

# Test cases
test_texts = [
    # Case 1: Text with EMA header
    """Assessment report EMA/464842/2024 Page 78/195
This is the actual content that should be preserved.
It contains important information about the drug.
Assessment report EMA/464842/2024 Page 79/195""",
    
    # Case 2: Text without headers
    """This is clean content.
No headers or footers here.
Just regular pharmaceutical text.""",
    
    # Case 3: Text with page numbers
    """Some content here.
Page 45/100
More content that should stay."""
]

print("=" * 70)
print("Testing Header/Footer Detection and Cleaning")
print("=" * 70)

for i, text in enumerate(test_texts, 1):
    print(f"\n--- Test Case {i} ---")
    print(f"Original text:\n{text}\n")
    
    has_patterns = _has_header_footer_patterns(text)
    print(f"Has header/footer patterns: {has_patterns}")
    
    if has_patterns:
        cleaned = _regex_clean(text)
        print(f"\nCleaned text (regex):\n{cleaned}\n")

print("=" * 70)
print("Test completed!")
print("=" * 70)
