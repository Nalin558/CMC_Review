#!/usr/bin/env python3
"""
Analyze font sizes in a PDF to debug font size detection
"""
import fitz
import sys
from collections import Counter

def analyze_pdf_fonts(pdf_path, page_num=0):
    """Analyze all fonts on a specific page"""
    try:
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            print(f"Error: PDF only has {len(doc)} pages")
            return
            
        page = doc[page_num]
        text_blocks = page.get_text("dict")["blocks"]
        
        all_fonts = []
        all_sizes = []
        
        print(f"\n{'='*60}")
        print(f"PDF Font Analysis: {pdf_path}")
        print(f"Analyzing page {page_num + 1} of {len(doc)}")
        print(f"{'='*60}\n")
        
        for block_idx, block in enumerate(text_blocks):
            if block.get("type") == 1:  # Text block
                text_content = block.get("text", "").strip()
                if text_content:
                    print(f"\nBlock {block_idx}: '{text_content[:50]}...'")
                    print(f"  Position: {block['bbox']}")
                    
                    for line_idx, line in enumerate(block.get("lines", [])):
                        for span_idx, span in enumerate(line.get("spans", [])):
                            size = span.get("size", 0)
                            font = span.get("font", "Unknown")
                            text = span.get("text", "")
                            
                            all_sizes.append(size)
                            all_fonts.append(font)
                            
                            print(f"    Line {line_idx}, Span {span_idx}:")
                            print(f"      Font: {font} | Size: {size}pt | Text: '{text}'")
        
        # Summary statistics
        print(f"\n{'='*60}")
        print("SUMMARY STATISTICS:")
        print(f"{'='*60}")
        
        size_counter = Counter(all_sizes)
        font_counter = Counter(all_fonts)
        
        print(f"\nFont Sizes Found: {len(size_counter)} distinct sizes")
        for size in sorted(size_counter.keys(), reverse=True):
            count = size_counter[size]
            percentage = (count / len(all_sizes)) * 100
            print(f"  {size:5.1f}pt : {count:3d} samples ({percentage:5.1f}%)")
        
        print(f"\nFonts Found: {len(font_counter)} distinct fonts")
        for font, count in font_counter.most_common(10):
            percentage = (count / len(all_fonts)) * 100
            print(f"  {font:20s} : {count:3d} samples ({percentage:5.1f}%)")
        
        # Most likely body text size
        most_common_size = size_counter.most_common(1)[0][0]
        largest_size = max(all_sizes)
        avg_size = sum(all_sizes) / len(all_sizes) if all_sizes else 0
        
        print(f"\nFont Size Analysis:")
        print(f"  Most common size: {most_common_size}pt")
        print(f"  Largest size: {largest_size}pt")
        print(f"  Average size: {avg_size:.1f}pt")
        print(f"  Min size: {min(all_sizes)}pt")
        print(f"  Max size: {max(all_sizes)}pt")
        
        doc.close()
        
    except Exception as e:
        print(f"Error analyzing PDF: {e}", file=sys.stderr)

if __name__ == "__main__":
    pdf_path = "highlighted_test.pdf"
    page_num = 0
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    if len(sys.argv) > 2:
        page_num = int(sys.argv[2])
    
    analyze_pdf_fonts(pdf_path, page_num)
