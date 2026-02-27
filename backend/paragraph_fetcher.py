"""
Intelligent paragraph fetching from PDF using LLM-guided cosine similarity.
This module helps find the correct paragraph in a PDF when exact text matching fails.
"""

import fitz
import os
import logging
from sentence_transformers import SentenceTransformer
import numpy as np
import re
import unicodedata
from typing import List, Tuple, Dict, Optional
from llm_client import llm

logger = logging.getLogger(__name__)

# Initialize sentence transformer for semantic similarity
model = SentenceTransformer('all-MiniLM-L6-v2')


def extract_pdf_paragraphs(pdf_path: str) -> List[Tuple[str, int, int]]:
    """
    Extract all paragraphs from a PDF.
    Returns list of tuples: (paragraph_text, page_number, block_index)
    """
    paragraphs = []
    
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc, 1):
            blocks = page.get_text("blocks")
            for block_idx, block in enumerate(blocks):
                # block[4] contains the text
                text = block[4].strip()
                if text and len(text) > 30:  # Filter out very short texts
                    # Normalize text
                    text = normalize_text(text)
                    paragraphs.append((text, page_num, block_idx))
        doc.close()
    except Exception as e:
        logger.error(f"Error extracting paragraphs from PDF: {e}")
    
    return paragraphs


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison.
    - Unicode normalization (handles ligatures)
    - Whitespace normalization
    - Collapse multiple spaces
    """
    # 1. Unicode normalization
    text = unicodedata.normalize('NFKD', text)
    # 2. Replace newlines and carriage returns with spaces
    text = text.replace("\n", " ").replace("\r", " ")
    # 3. Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_key_concepts(paragraph: str) -> str:
    """
    Use LLM to extract key concepts/intent from the paragraph.
    This helps with semantic matching even if exact text differs.
    """
    try:
        prompt = f"""Extract the key concepts and intent from this paragraph in 1-2 sentences.
Focus on the main meanings, technical terms, and main idea. Be concise.

Paragraph:
{paragraph[:500]}

Key concepts:"""
        
        key_concepts = llm.generate_text(
            prompt=prompt,
            system_instruction="You are a technical document analyst. Extract key concepts concisely.",
            max_tokens=200,
            temperature=0.0
        )
        return key_concepts.strip()
    except Exception as e:
        logger.warning(f"Error extracting key concepts: {e}")
        return paragraph[:200]


def find_paragraph_with_similarity(
    user_paragraph: str,
    pdf_path: str,
    top_k: int = 5,
    similarity_threshold: float = 0.3
) -> List[Dict]:
    """
    Find paragraphs in PDF that match the user's paragraph using cosine similarity.
    
    Strategy:
    1. Extract all paragraphs from PDF
    2. Extract key concepts using LLM
    3. Compute cosine similarity between key concepts embeddings
    4. Return top-k matches with similarity scores
    
    Returns:
        List of dicts with keys: 'text', 'page', 'block_idx', 'similarity', 'is_match'
    """
    logger.info("🔍 Starting intelligent paragraph fetching with LLM-guided similarity...")
    
    # Step 1: Extract key concepts from user's paragraph using LLM
    logger.info("  1️⃣  Extracting key concepts from user paragraph using LLM...")
    user_concepts = extract_key_concepts(user_paragraph)
    logger.info(f"     User concepts: {user_concepts[:100]}...")
    
    # Step 2: Get all paragraphs from PDF
    logger.info("  2️⃣  Extracting all paragraphs from PDF...")
    pdf_paragraphs = extract_pdf_paragraphs(pdf_path)
    logger.info(f"     Found {len(pdf_paragraphs)} paragraphs in PDF")
    
    if not pdf_paragraphs:
        logger.warning("⚠️  No paragraphs found in PDF")
        return []
    
    # Step 3: Compute embeddings and cosine similarity
    logger.info("  3️⃣  Computing embeddings and cosine similarity...")
    
    # Embed user's key concepts
    user_embedding = model.encode([user_concepts])[0]
    
    # Embed all PDF paragraphs (use their key concepts for better matching)
    pdf_texts = [p[0] for p in pdf_paragraphs]
    pdf_embeddings = model.encode(pdf_texts)
    
    # Compute cosine similarity
    # Normalize vectors for cosine similarity
    user_norm = user_embedding / np.linalg.norm(user_embedding)
    pdf_norms = pdf_embeddings / np.linalg.norm(pdf_embeddings, axis=1, keepdims=True)
    
    similarities = np.dot(pdf_norms, user_norm)
    
    # Step 4: Get top-k results with high similarity
    logger.info(f"  4️⃣  Getting top {top_k} results with similarity > {similarity_threshold}...")
    
    results = []
    top_indices = np.argsort(similarities)[::-1][:top_k * 2]  # Get more candidates
    
    for idx in top_indices:
        sim_score = float(similarities[idx])
        
        if sim_score >= similarity_threshold:
            para_text, page_num, block_idx = pdf_paragraphs[idx]
            results.append({
                'text': para_text,
                'page': page_num,
                'block_idx': block_idx,
                'similarity': sim_score,
                'is_match': False  # Will be updated by LLM
            })
    
    logger.info(f"     Found {len(results)} candidates with similarity >= {similarity_threshold}")
    
    # Step 5: Let LLM verify which one is the actual match
    if results:
        logger.info("  5️⃣  Using LLM to verify the best match...")
        
        # Create a comparison prompt
        candidates_text = "\n".join(
            [f"Candidate {i}: [Page {r['page']}, Similarity: {r['similarity']:.2%}]\n{r['text'][:300]}..."
             for i, r in enumerate(results[:5])]
        )
        
        verify_prompt = f"""Given the user's original paragraph and these candidate paragraphs from the PDF,
identify which candidate (if any) is the actual/intended match. Consider:
1. Semantic similarity (same meaning)
2. Technical content match
3. Context alignment

User's paragraph (key concepts: {user_concepts[:200]}):
{user_paragraph[:500]}

Candidates from PDF:
{candidates_text}

Respond in JSON format:
{{
    "best_match_index": 0 or null,
    "confidence": 0.0-1.0,
    "reason": "explanation"
}}

Only set best_match_index if you're confident (>70%) this is the right paragraph."""
        
        try:
            llm_response = llm.generate_text(
                prompt=verify_prompt,
                system_instruction="You are a technical document matcher. Return only valid JSON.",
                max_tokens=300,
                temperature=0.0
            )
            
            # Parse LLM response (simple JSON extraction)
            import json
            try:
                # Try to extract JSON from response
                json_start = llm_response.find('{')
                json_end = llm_response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = llm_response[json_start:json_end]
                    llm_result = json.loads(json_str)
                    
                    best_idx = llm_result.get('best_match_index')
                    confidence = llm_result.get('confidence', 0)
                    
                    if best_idx is not None and best_idx < len(results):
                        results[best_idx]['is_match'] = True
                        results[best_idx]['llm_confidence'] = confidence
                        results[best_idx]['llm_reason'] = llm_result.get('reason', '')
                        logger.info(f"     LLM selected candidate {best_idx} with confidence {confidence:.2%}")
                        logger.info(f"     Reason: {llm_result.get('reason', '')[:100]}...")
            except json.JSONDecodeError:
                logger.warning(f"     Could not parse LLM response as JSON: {llm_response[:100]}")
        except Exception as e:
            logger.warning(f"     Error verifying with LLM: {e}")
    
    # Sort by similarity (highest first)
    results = sorted(results, key=lambda x: x['similarity'], reverse=True)
    
    logger.info(f"✅ Paragraph fetching complete. Found {len(results)} matches.")
    return results


def find_and_highlight_paragraph(
    pdf_path: str,
    user_paragraph: str,
    top_k: int = 5,
    similarity_threshold: float = 0.3
) -> Tuple[Optional[Dict], List[Dict]]:
    """
    Main function to find the best matching paragraph and return details.
    
    Returns:
        Tuple of (best_match_dict, all_candidates_list)
    """
    candidates = find_paragraph_with_similarity(
        user_paragraph=user_paragraph,
        pdf_path=pdf_path,
        top_k=top_k,
        similarity_threshold=similarity_threshold
    )
    
    # Get the best match (highest similarity + optionally LLM verified)
    best_match = None
    
    # First priority: LLM verified match
    for candidate in candidates:
        if candidate.get('is_match', False):
            best_match = candidate
            break
    
    # Second priority: highest similarity
    if not best_match and candidates:
        best_match = candidates[0]
    
    return best_match, candidates
