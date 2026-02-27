# backend/validator.py
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

from llm_client import llm

load_dotenv()  # loads GOOGLE_API_KEY from .env

API_KEY = os.getenv("OPENAI_API_KEY")
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "cmc_data")
Path(DATA_DIR).mkdir(exist_ok=True)

PROMPT_TEMPLATE = """
You are a STRICT RULE-BASED VALIDATOR.

--- INPUT ---
GUIDELINES:
{guidelines}

PARAGRAPH:
{paragraph}

--- TASK ---
1. Extract every guideline as a separate rule.
2. Check each rule against the paragraph.
3. Identify EXACT words/phrases in the paragraph that violate guidelines.
4. Wrap each violated text with <HIGHLIGHT> ... </HIGHLIGHT> tags.
5. Provide a reasoning for why it is a violation.

--- RULES FOR VIOLATION ---
- EXPLICIT VIOLATIONS ONLY: A guideline is violated ONLY if the paragraph explicitly contradicts it.
- NO INFERENCE: Do not assume a violation if the paragraph is merely silent or vague.
- BENEFIT OF DOUBT: If unsure, assume NO violation.
- NO FALSE POSITIVES.

--- OUTPUT FORMAT ---
Return ONLY the following:

GUIDELINES VIOLATED:
- [Rule 1]: [Violation details]
- [Rule 2]: [Violation details]
(If none, write "None")

AI REASONING:
• [First key point about the validation]
• [Second key point about the validation]
• [Additional points as needed]

IMPORTANT: You MUST format the AI REASONING section as bullet points.
Each point MUST start with the bullet symbol •
DO NOT use numbers, dashes, or any other format.
Example format:
• This is the first reasoning point
• This is the second reasoning point
• This is the third reasoning point

HIGHLIGHTED PARAGRAPH:
[Paragraph with tags... or original text if no violations]
"""

def run_validator(guidelines_text, paragraph_text):
    """
    Calls LLM to validate a paragraph against guidelines.
    Returns raw output, violated rules, reasoning, and highlighted HTML.

    Handles network or LLM errors by returning a structured fallback where
    AI REASONING is a bullet starting with "- Network Error: ..." so it
    stays consistent with our bullet-format requirement.
    """
    prompt = PROMPT_TEMPLATE.format(guidelines=guidelines_text, paragraph=paragraph_text)

    try:
        # Use the shared LLM client which has retry/backoff built in
        raw_text = llm.generate_text(prompt)
    except Exception as e:
        err_msg = str(e) or "Unknown network error"
        raw_text = (
            "GUIDELINES VIOLATED:\n- None\n\n"
            "AI REASONING:\n- Network Error: " + err_msg + "\n\n"
            f"HIGHLIGHTED PARAGRAPH:\n{paragraph_text}"
        )

    violated, reasoning, highlighted = parse_output(raw_text)
    highlighted_html = convert_highlight_to_html(highlighted)

    return raw_text, violated, reasoning, highlighted_html


def parse_output(raw_text):
    violated = ""
    reasoning = ""
    highlighted = raw_text

    # Extract GUIDELINES VIOLATED
    if "GUIDELINES VIOLATED:" in raw_text:
        parts = raw_text.split("GUIDELINES VIOLATED:", 1)
        rest = parts[1]
        
        # Extract AI REASONING
        if "AI REASONING:" in rest:
            v_part, r_part = rest.split("AI REASONING:", 1)
            violated = v_part.strip()
            
            # Extract HIGHLIGHTED PARAGRAPH
            if "HIGHLIGHTED PARAGRAPH:" in r_part:
                r_text, h_text = r_part.split("HIGHLIGHTED PARAGRAPH:", 1)
                reasoning = r_text.strip()
                highlighted = h_text.strip()
            else:
                reasoning = r_part.strip()

            # Normalize reasoning to bullet points
            reasoning = format_reasoning_as_bullets(reasoning)
        else:
            # Fallback if reasoning is missing but highlight exists
            if "HIGHLIGHTED PARAGRAPH:" in rest:
                v_part, h_part = rest.split("HIGHLIGHTED PARAGRAPH:", 1)
                violated = v_part.strip()
                highlighted = h_part.strip()
            else:
                violated = rest.strip()
    
    return violated, reasoning, highlighted


def format_reasoning_as_bullets(text):
    """Ensure the AI reasoning is returned as bullet points.

    - If reasoning is empty or 'None', return "None".
    - If already bullet-formatted (lines starting with -, *, •), normalize to '- '.
    - Otherwise split into sentences or lines and prefix each with '- '.
    """
    if not text or not text.strip():
        return "None"

    raw = text.strip()

    # If it's exactly 'None' or similar
    if raw.lower() in ("none", "no", "n/a"):
        return "None"

    lines = []
    # If there are explicit newline-delimited bullets or lines, use them
    for part in re.split(r"\n+", raw):
        part = part.strip()
        if not part:
            continue
        # If already begins with a bullet char, normalize it
        if re.match(r'^\s*[-\*•]\s+', part):
            norm = re.sub(r'^\s*[-\*•]\s+', '- ', part)
            lines.append(norm)
            continue

        # If lines seem long, split into sentences conservatively
        sentences = re.split(r'(?<=[.!?])\s+', part)
        if len(sentences) == 1:
            lines.append('- ' + part)
        else:
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                lines.append('- ' + s)

    # Final join
    return "\n".join(lines)


def convert_highlight_to_html(text):
    if not text:
        return ""
    text = re.sub(
        r"<HIGHLIGHT>(.*?)</HIGHLIGHT>",
        r"<span style='color:red; font-weight:bold'>\1</span>",
        text,
        flags=re.DOTALL
    )
    return text


def save_validator_results(guidelines, paragraph, violated_text, reasoning, highlighted_html):
    report_file = os.path.join(DATA_DIR, "Report_generated.json")
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "guidelines_input": guidelines,
        "paragraph_input": paragraph,
        "violated_rules": violated_text,
        "ai_reasoning": reasoning,
        "highlighted_html": highlighted_html
    }

    current_data = []
    if os.path.exists(report_file):
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                current_data = json.load(f)
                if not isinstance(current_data, list):
                    current_data = []
        except Exception:
            current_data = []

    current_data.append(entry)

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)

    return report_file, report_file
