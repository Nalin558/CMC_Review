import fitz

doc = fitz.open('highlighted_test.pdf')
print(f'PDF has {len(doc)} pages')

for page_num in range(min(3, len(doc))):
    page = doc[page_num]
    blocks = page.get_text('dict')['blocks']
    text_blocks = [b for b in blocks if b.get('type') == 1]
    
    print(f'\nPage {page_num + 1}:')
    print(f'  Total blocks: {len(blocks)}')
    print(f'  Text blocks: {len(text_blocks)}')
    
    # Get all text to see what's in this page
    text = page.get_text()
    print(f'  Text length: {len(text)} chars')
    print(f'  First 100 chars: {repr(text[:100])}')

doc.close()
