from pdf_paragraph_replace import replace_paragraph_anchored
import os

pdf = os.path.join(os.path.dirname(__file__), "cmc_rag", "pdfs", "hympavzi-epar-public-assessment-report_en (2).pdf")
start_anchor = "Effect of ADA and NAb on PD Data Profiles of key participants"
end_anchor = "by age for study b7841005 – marstacimab dataset"
try:
    out = replace_paragraph_anchored(pdf, 80, start_anchor, end_anchor, "REPLACED TEST")
    print("Replacement output:", out)
except Exception as e:
    print("Replacement failed:", e)
