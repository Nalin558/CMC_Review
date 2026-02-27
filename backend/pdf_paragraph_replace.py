import fitz
import io
import re
import os
import tempfile
import logging
from collections import Counter

logger = logging.getLogger(__name__)

def replace_paragraph_anchored(input_pdf_path: str, page_number: int, start_anchor: str, end_anchor: str, replacement_text: str):
    """
    Replaces a multi-line paragraph on a specific page using anchor-based bounding box.
    Returns the path to the modified PDF.

    Args:
        input_pdf_path (str): Path to the input PDF file.
        page_number (int): 1-based page number.
        start_anchor (str): Text to find the start block.
        end_anchor (str): Text to find the end block.
        replacement_text (str): New text to insert.

    Returns:
        str: Path to the new PDF file.

    Raises:
        ValueError: If anchors not found.
    """
    doc = fitz.open(input_pdf_path)
    try:
        page = doc[page_number - 1]
        blocks = page.get_text("blocks")
        
        # Log all detected blocks on the page
        print(f"Blocks on page {page_number}:")
        for i, block in enumerate(blocks):
            print(f"  {i}: {block[4][:100]}...")
        
        # Normalize anchors: lower, strip, collapse whitespace so newlines/spaces are treated uniformly
        start_norm = re.sub(r'\s+', ' ', start_anchor.lower().strip())
        end_norm = re.sub(r'\s+', ' ', end_anchor.lower().strip())
        
        start_idx = -1
        end_idx = -1
        
        # First try the simple block-by-block search (fast path)
        for i, block in enumerate(blocks):
            block_text_norm = re.sub(r'\s+', ' ', block[4].lower().strip())
            if start_norm in block_text_norm and start_idx == -1:
                start_idx = i
            if end_norm in block_text_norm and i > start_idx:
                end_idx = i
                break

        # If not found by blocks, try searching the concatenated page text
        if start_idx == -1 or end_idx == -1:
            # Normalize blocks and build a concatenated page text (collapse whitespace to single spaces)
            block_texts = [re.sub(r'\s+', ' ', b[4]).strip() for b in blocks]
            concat = ' '.join(block_texts).lower().strip()

            # Try to find anchors in the concatenated text
            start_pos = concat.find(start_norm)
            if start_pos == -1:
                raise ValueError(f"Start anchor '{start_anchor}' not found on page {page_number}")

            end_pos = concat.find(end_norm, start_pos + len(start_norm))
            if end_pos == -1:
                raise ValueError(f"End anchor '{end_anchor}' not found after start anchor on page {page_number}")

            # Map positions back to block indices
            pos_cursor = 0
            start_idx = None
            end_idx = None
            for i, bt in enumerate(block_texts):
                bt_len = len(bt)
                if start_idx is None and start_pos < pos_cursor + bt_len:
                    start_idx = i
                if end_pos < pos_cursor + bt_len and end_idx is None:
                    end_idx = i
                    break
                pos_cursor += bt_len + 1  # +1 for the separator

            # Fallback if mapping failed for some reason
            if start_idx is None:
                raise ValueError(f"Start anchor '{start_anchor}' not mapped to blocks on page {page_number}")
            if end_idx is None:
                raise ValueError(f"End anchor '{end_anchor}' not mapped to blocks on page {page_number}")

            print(f"Anchors found across blocks (start_pos={start_pos}, end_pos={end_pos}), mapped to blocks {start_idx}..{end_idx}")

        if start_idx == -1:
            raise ValueError(f"Start anchor '{start_anchor}' not found on page {page_number}")
        if end_idx == -1:
            raise ValueError(f"End anchor '{end_anchor}' not found after start anchor on page {page_number}")
        
        print(f"Start block index: {start_idx}, End block index: {end_idx}")
        
        # Collect blocks from start to end inclusive
        selected_blocks = blocks[start_idx:end_idx + 1]
        
        # Validation: check if we're selecting too many blocks (sanity check)
        # If we selected more than 80% of blocks on the page, something is wrong
        if len(selected_blocks) > len(blocks) * 0.8:
            logger.warning(f"⚠️  Selected blocks ({len(selected_blocks)}) is > 80% of page blocks ({len(blocks)})")
            logger.warning(f"Start anchor: {start_anchor[:50]}...")
            logger.warning(f"End anchor: {end_anchor[:50]}...")
            raise ValueError(f"Anchors are too broad - would replace most of the page. Selected {len(selected_blocks)}/{len(blocks)} blocks. Please use more specific text for start/end anchors.")
        
        # Compute combined bounding box
        x0 = min(b[0] for b in selected_blocks)
        y0 = min(b[1] for b in selected_blocks)
        x1 = max(b[2] for b in selected_blocks)
        y1 = max(b[3] for b in selected_blocks)
        rect = fitz.Rect(x0, y0, x1, y1)
        
        print(f"Combined rect: {rect}")
        
        # STEP 1: Get the actual text at this location
        text_at_location = page.get_text(clip=rect).strip()
        print(f"\n=== READING ORIGINAL TEXT ===")
        print(f"Original text at location: '{text_at_location[:80]}...'")
        
        # STEP 2: Get detailed text info with font sizes from dictionary format
        text_dict = page.get_text("dict")
        font_sizes = []
        font_names = []
        
        print(f"Searching for font sizes in the text area...")
        
        # Extract font info from ALL text blocks nested within the rectangle
        for block in text_dict["blocks"]:
            if block.get("type") == 1:  # Text block
                block_bbox = block["bbox"]
                # Check if block overlaps with our rectangle
                if (rect.x1 > block_bbox[0] and rect.x0 < block_bbox[2] and
                    rect.y1 > block_bbox[1] and rect.y0 < block_bbox[3]):
                    
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line["spans"]:
                                size = span.get("size", 0)
                                font = span.get("font", "")
                                text_span = span.get("text", "")
                                
                                # Collect if reasonable size
                                if 5 <= size <= 72:
                                    font_sizes.append(size)
                                    font_names.append(font)
                                    print(f"  Found: '{text_span[:30]}' @ {size}pt ({font})")
        
        print(f"\n=== FONT SIZE ANALYSIS ===")
        print(f"Total font samples found: {len(font_sizes)}")
        
        # STEP 3: Determine the main font size from the original text
        font_size = 12  # default
        detected_font_name = "helv"
        
        if font_sizes:
            # Method 1: Most common size (usually the body text)
            size_counter = Counter(font_sizes)
            most_common_size = size_counter.most_common(1)[0][0]
            
            # Method 2: Largest size
            largest_size = max(font_sizes)
            
            print(f"Most common size: {most_common_size}pt (appears {size_counter[most_common_size]}× in text)")
            print(f"Largest size: {largest_size}pt")
            print(f"Size distribution: {dict(sorted(size_counter.items(), key=lambda x: x[1], reverse=True))}")
            
            # Use most common since that's the actual body text being replaced
            # (not headers or footnotes)
            font_size = most_common_size
            print(f"\n✓ USING MOST COMMON SIZE: {font_size}pt (this is what you see in the PDF)")
            
            logger.info(f"Font sizes found: {size_counter}")
            logger.info(f"Selected font size: {font_size}pt (most common in selected area)")
        else:
            print(f"⚠ No font sizes found in text area! Using default 12pt")
            logger.warning("Could not detect font size, using default 12pt")
        
        if font_names:
            font_counter = Counter(font_names)
            detected_font_name = font_counter.most_common(1)[0][0]
            print(f"Detected font name: {detected_font_name} (appears {font_counter[detected_font_name]}× in text)")
        else:
            detected_font_name = "helv"
            print(f"No font names detected, using default Helvetica")
        
        logger.info(f"✓ Detected Font size: {font_size}pt, Font name: {detected_font_name}")
        print(f"=== FINAL DECISION: Using {font_size}pt {detected_font_name} ===\n")

        # Map detected font to standard 14 fonts as fallback
        font_lower = detected_font_name.lower()
        fallback_font = "helv"  # default fallback
        
        # Check for common font families for fallback
        if "verdana" in font_lower or "arial" in font_lower or "helvetica" in font_lower or "helv" in font_lower:
            fallback_font = "helv"
        elif "times" in font_lower:
            fallback_font = "tiro"  # Times-Roman
        elif "courier" in font_lower:
            fallback_font = "cour"
        
        print(f"Detected font: {detected_font_name}, Fallback font: {fallback_font}")
        
        # Try to get the font object from the document
        font_obj = None
        try:
            # Get list of fonts in the document
            fontlist = doc.get_page_fonts(page_number - 1)
            print(f"Available fonts on page: {fontlist}")
            
            # Try to find the detected font in the page's font list
            for font_info in fontlist:
                # font_info is typically (xref, ext, type, basename, name, encoding)
                if len(font_info) >= 5:
                    font_name_in_list = font_info[4]  # The font name
                    if detected_font_name in font_name_in_list or font_name_in_list in detected_font_name:
                        print(f"Found matching font in document: {font_name_in_list}")
                        # We found the font, but we'll still use the name for insert_textbox
                        break
        except Exception as e:
            print(f"Error getting font list: {e}")
        
        # Replace text by coordinates only
        page.add_redact_annot(rect)
        page.apply_redactions()
        
        # Insert text using EXACT detected font size (do not reduce)
        inserted = False
        
        # Build list of fonts to try
        # First try the exact detected font name, then try common variations, then fallback
        fonts_to_try = []
        
        # Add the exact detected font name
        fonts_to_try.append(detected_font_name)
        
        # Add common variations for Verdana
        if "verdana" in font_lower:
            fonts_to_try.extend(["Verdana", "verdana", "VERDANA"])
        
        # Add the fallback font
        if fallback_font not in fonts_to_try:
            fonts_to_try.append(fallback_font)
        
        print(f"Will try fonts in order: {fonts_to_try}")
        print(f"Starting font size: {font_size}pt")
        print(f"If text doesn't fit, will automatically reduce by 1pt until it fits (min 6pt)")
        print(f"Bounding box: {rect.width:.1f}pt wide × {rect.height:.1f}pt tall")
        print(f"Text to insert: {len(replacement_text)} characters")
        
        # Try each font
        for font_attempt in fonts_to_try:
            if inserted:
                break
            
            print(f"\n--- Trying font: '{font_attempt}' ---")
            
            # Try with decreasing font sizes
            current_size = font_size
            min_size = 6  # Don't go smaller than 6pt
            
            while current_size >= min_size and not inserted:
                try:
                    # Try justified alignment
                    logger.info(f"  Attempting {font_attempt}/{current_size}pt (justified)")
                    print(f"  Size {current_size}pt (justified)...", end=" ", flush=True)
                    
                    rc = page.insert_textbox(
                        rect, 
                        replacement_text, 
                        fontsize=current_size,
                        fontname=font_attempt,
                        align=fitz.TEXT_ALIGN_JUSTIFY
                    )
                    
                    # rc > 0 means text was successfully inserted
                    if rc > 0:
                        inserted = True
                        size_reduction = font_size - current_size
                        if size_reduction > 0:
                            print(f"\n✓ SUCCESS with font '{font_attempt}' at {current_size}pt (reduced from {font_size}pt by {size_reduction}pt)")
                            logger.info(f"✓ Text inserted with '{font_attempt}' at {current_size}pt (justified, reduced by {size_reduction}pt)")
                        else:
                            print(f"\n✓ SUCCESS with font '{font_attempt}' at {current_size}pt (original size)")
                            logger.info(f"✓ Text inserted with '{font_attempt}' at {current_size}pt (justified, original size)")
                        break
                    else:
                        # Text didn't fit with justified, try left alignment
                        print(f"(justified failed)", end=" ", flush=True)
                        logger.info(f"  Justified failed, trying left alignment with {font_attempt}/{current_size}pt")
                        
                        rc = page.insert_textbox(
                            rect, 
                            replacement_text, 
                            fontsize=current_size,
                            fontname=font_attempt,
                            align=fitz.TEXT_ALIGN_LEFT
                        )
                        if rc > 0:
                            inserted = True
                            size_reduction = font_size - current_size
                            if size_reduction > 0:
                                print(f"\n✓ SUCCESS with font '{font_attempt}' at {current_size}pt (left, reduced from {font_size}pt by {size_reduction}pt)")
                                logger.info(f"✓ Text inserted with '{font_attempt}' at {current_size}pt (left, reduced by {size_reduction}pt)")
                            else:
                                print(f"\n✓ SUCCESS with font '{font_attempt}' at {current_size}pt (left, original size)")
                                logger.info(f"✓ Text inserted with '{font_attempt}' at {current_size}pt (left, original size)")
                            break
                        else:
                            # Text still doesn't fit, try smaller size
                            print(f"(left failed, trying smaller)", end=" ", flush=True)
                            current_size -= 1
                            
                except Exception as e:
                    error_msg = str(e).lower()
                    logger.warning(f"  ✗ Error with {font_attempt}/{current_size}pt: {e}")
                    print(f"\n✗ Error with font '{font_attempt}' size {current_size}pt: {e}")
                    
                    # If error is font-related, skip to next font
                    if "font" in error_msg or "unknown" in error_msg:
                        logger.info(f"  Font '{font_attempt}' not available, trying next font")
                        print(f"Font '{font_attempt}' not available, trying next font")
                        break
                    else:
                        # Other errors, try smaller size
                        current_size -= 1
        
        # If all fonts failed, try fallback with very aggressive size reduction
        if not inserted:
            print(f"\nAll font attempts failed, trying fallback font '{fallback_font}' with aggressive size reduction...")
            current_size = font_size
            min_size = 5
            
            while current_size >= min_size and not inserted:
                try:
                    logger.info(f"Fallback attempt: {fallback_font}/{current_size}pt")
                    print(f"  Size {current_size}pt...", end=" ", flush=True)
                    
                    rc = page.insert_textbox(
                        rect, 
                        replacement_text, 
                        fontsize=current_size,
                        fontname=fallback_font,
                        align=fitz.TEXT_ALIGN_LEFT
                    )
                    if rc > 0:
                        inserted = True
                        size_reduction = font_size - current_size
                        if size_reduction > 0:
                            print(f"\n✓ Fallback SUCCESS at {current_size}pt (reduced from {font_size}pt by {size_reduction}pt)")
                            logger.info(f"✓ Text inserted with fallback font at {current_size}pt (reduced by {size_reduction}pt)")
                        else:
                            print(f"\n✓ Fallback SUCCESS at {current_size}pt (original size)")
                            logger.info(f"✓ Text inserted with fallback font at {current_size}pt (original size)")
                        break
                    else:
                        print(f"(failed)", end=" ", flush=True)
                        current_size -= 1
                except Exception as e:
                    logger.warning(f"Fallback error at {current_size}pt: {e}")
                    print(f"(error)", end=" ", flush=True)
                    current_size -= 1
        
        if not inserted:
            logger.warning(f"⚠️  Failed to insert text. Tried sizes from {font_size}pt down to 5pt.")
            logger.warning(f"Replacement text length: {len(replacement_text)} chars")
            logger.warning(f"Bounding box dimensions: {rect.width:.1f}pt wide × {rect.height:.1f}pt tall")
            raise ValueError(f"Failed to insert replacement text even after reducing font size to 5pt. The text is too long for the available space. Consider shortening the text significantly or using the UI to adjust the replacement text.")
        
        # Save a new PDF (do NOT overwrite original)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', dir=os.path.dirname(input_pdf_path)) as tmp:
            output_path = tmp.name
        doc.save(output_path)
        
        print(f"✓ Saved new PDF to {output_path}")
        logger.info(f"✓ PDF saved to {output_path}")
        return output_path
    finally:
        doc.close()

# Minimal Flask route snippet (commented out, not registered)
# @app.route('/replace_paragraph', methods=['POST'])
# def replace_paragraph_route():
#     data = request.get_json()
#     replace_paragraph(
#         data['input_pdf_path'],
#         data['output_pdf_path'],
#         data['page_number'],
#         data['old_text'],
#         data['new_text']
#     )
#     return {'status': 'success'}