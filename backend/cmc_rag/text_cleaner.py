# backend/cmc_rag/text_cleaner.py
"""
LLM-based text cleaner to remove header/footer artifacts from CMC sections.
"""

import re
from typing import Optional

def clean_chunk_with_llm(text: str, llm_client) -> str:
    """
    Use LLM to intelligently remove header/footer artifacts from a text chunk.
    
    Args:
        text: The text chunk to clean
        llm_client: The LLM client instance (from llm_client.py)
    
    Returns:
        Cleaned text with headers/footers removed
    """
    # Quick check: if text doesn't contain common header/footer patterns, skip LLM call
    if not _has_header_footer_patterns(text):
        return text
    
    prompt = f"""You are a text cleaner for pharmaceutical CMC documents.

Your task is to remove ONLY header/footer artifacts from the following text chunk while preserving ALL actual content.

Common header/footer patterns to remove:
- "Assessment report EMA/XXXXXX/XXXX Page XX/XXX"
- "Page XX/XXX" or "Page XX"
- "EMA/XXXXXX/XXXX"
- "Procedure No. EMEA/H/C/XXXXXX"
- Standalone page numbers

IMPORTANT RULES:
1. Remove ONLY headers and footers - preserve ALL actual document content
2. Do NOT summarize or paraphrase the content
3. Do NOT remove section headings or titles
4. Return the cleaned text directly without any explanation or markdown formatting
5. If unsure whether something is a header/footer, keep it

Text to clean:
{text}

Return only the cleaned text:"""

    try:
        cleaned = llm_client.generate_text(prompt, max_tokens=2048)
        # Remove any markdown code blocks if LLM added them
        cleaned = cleaned.replace("```", "").strip()
        
        # Sanity check: if cleaned text is too short compared to original, return original
        if len(cleaned) < len(text) * 0.5:
            return text
            
        return cleaned
    except Exception as e:
        # If LLM fails, fall back to regex-based cleaning
        print(f"LLM cleaning failed: {e}, falling back to regex")
        return _regex_clean(text)


def _has_header_footer_patterns(text: str) -> bool:
    """Quick check if text contains common header/footer patterns."""
    patterns = [
        r"Assessment\s+report\s+EMA\/\d+\/\d+",
        r"Page\s+\d+\/\d+",
        r"EMA\/\d+\/\d+",
        r"Procedure\s+No\.\s+EMEA",
    ]
    
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _regex_clean(text: str) -> str:
    """Fallback regex-based cleaning."""
    lines = text.split("\n")
    cleaned_lines = []
    
    # Patterns to remove
    header_footer_pattern = re.compile(
        r"^\s*(Assessment\s+report\s+EMA\/\d+\/\d+\s+Page\s+\d+\/\d+|"
        r"Page\s+\d+\/\d+|"
        r"EMA\/\d+\/\d+|"
        r"Procedure\s+No\.\s+EMEA.*|"
        r"^\d{1,3}$)\s*$",
        re.IGNORECASE
    )
    
    for line in lines:
        if not header_footer_pattern.match(line.strip()):
            cleaned_lines.append(line)
    
    return "\n".join(cleaned_lines).strip()
