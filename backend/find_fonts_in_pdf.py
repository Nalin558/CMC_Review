import fitz
from collections import Counter

doc = fitz.open('highlighted_test.pdf')
print(f'PDF has {len(doc)} pages\n')

# Find a page with text blocks and analyze its fonts
for page_num in range(len(doc)):
    page = doc[page_num]
    blocks = page.get_text('dict')['blocks']
    
    font_sizes = []
    font_names = []
    
    for block in blocks:
        if block.get('type') == 1:
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    size = span.get('size', 0)
                    font = span.get('font', 'Unknown')
                    if size > 0:
                        font_sizes.append(size)
                        font_names.append(font)
    
    if font_sizes:
        print(f'Page {page_num + 1}: Found {len(font_sizes)} font samples in {len(set(font_sizes))} distinct sizes')
        size_counter = Counter(font_sizes)
        font_counter = Counter(font_names)
        
        print(f'  Sizes: {dict(sorted(size_counter.items(), reverse=True)[:5])}')
        print(f'  Fonts: {dict(font_counter.most_common(3))}')
        print()
        
        if page_num > 5 and len(font_sizes) > 20:
            # Found a good page with multiple fonts, stop
            break

doc.close()
