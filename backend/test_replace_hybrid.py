from pdf_paragraph_replace import replace_paragraph_anchored
import os

pdf = os.path.join(os.path.dirname(__file__), "cmc_rag", "pdfs", "hympavzi-epar-public-assessment-report_en (2).pdf")

# Craft anchors unlikely to match exact page blocks, but semantically similar
start_anchor = "assessment report - September 2024"
end_anchor = "procedure"

try:
    out = replace_paragraph_anchored(pdf, 1, start_anchor, end_anchor, "REPLACED")
    print("Replacement output:", out)
except Exception as e:
    print("Replacement failed:", e)
