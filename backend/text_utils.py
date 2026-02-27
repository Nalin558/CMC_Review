import re
import unicodedata

def normalize_text(t: str) -> str:
    """
    Collapses all whitespace to single spaces and lowercases.
    Also applies unicode normalization (NFKD) to decompose ligatures 
    (e.g. 'fi' ligature -> 'f'+'i') and strip accents, ensuring maximum match potential.
    """
    if not t:
        return ""
    
    # Normalize unicode characters (e.g. \xa0 -> space, ligatures -> chars)
    t = unicodedata.normalize('NFKD', t)
    
    # Strip non-ascii chars if needed (optional, but good for robust matching)
    # t = t.encode('ascii', 'ignore').decode('utf-8') 
    
    return re.sub(r'\s+', ' ', t).lower().strip()

# Compile regexes once for performance
EMA_RE = re.compile(r'ema\s*/\s*\d+\s*/\s*\d+', re.IGNORECASE)
PAGE_RE = re.compile(r'page\s*\d+(\s*/\s*\d+)?', re.IGNORECASE)
ASSESS_RE = re.compile(r'assessment\s*report', re.IGNORECASE)
DATE_RE = re.compile(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b', re.IGNORECASE)

def sanitize_anchor(t: str) -> str:
    """
    Removes common header/footer artifacts from potential anchor text.
    Returns normalized, clean text.
    If cleaning removes everything, returns original normalized text.
    """
    if not t:
        return ""
    
    original = t
    
    # 1. Line-based cleaning (Robust against multi-line headers)
    lines = t.split('\n')
    clean_lines = []
    for line in lines:
        l = line.strip().lower()
        # Skip garbage lines
        if not l: continue
        if l.startswith("assessment report"): continue
        if "ema/" in l and re.search(r'\d', l): continue  # e.g EMA/123/456
        if l.startswith("page") and re.search(r'\d', l): continue
        if l.startswith("procedure no"): continue
        if "european medicines agency" in l: continue
        
        clean_lines.append(line)
    
    # Reassemble
    t = " ".join(clean_lines)

    # 2. Fallback Regex cleaning (for inline artifacts)
    t = EMA_RE.sub('', t)
    t = PAGE_RE.sub('', t)
    t = ASSESS_RE.sub('', t)
    t = DATE_RE.sub('', t)
    
    norm = normalize_text(t)
    
    # If sanitization stripped everything (e.g. anchor WAS just "Page 78"), 
    # fall back to original (normalized) to avoid matching empty string
    if len(norm) < 10:  # Increased threshold slightly
        return normalize_text(original)
        
    return norm
