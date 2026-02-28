// src/components/CmcViewer.jsx
import React, { useEffect, useState, useRef } from "react";
import { logEvent } from "../log";

// Simple normalization for fuzzy page matching
function normalize(text) {
  return text
    .replace(/-\s*\n/g, "")
    .replace(/\s+/g, " ")
    .toLowerCase()
    .trim();
}

export default function CmcViewer({ document, llmResult, onPageChange }) {
  const cmcContext = llmResult?.cmc_context_used || null;

  const [matchedPage, setMatchedPage] = useState(null);
  const [matchedScore, setMatchedScore] = useState(0);

  // Prevent repeated auto-jumps
  const hasJumpedRef = useRef(false);

  /* -----------------------------------------------------
        AUTO-DETECT PAGE BY FUZZY MATCHING
  ----------------------------------------------------- */
  useEffect(() => {
    if (!document || !cmcContext || !document.pages?.length) return;

    hasJumpedRef.current = false; // reset on new comment

    const contextNorm = normalize(cmcContext);
    const tokens = contextNorm.split(" ").filter((w) => w.length > 5);

    let bestPage = null;
    let bestScore = 0;

    for (const p of document.pages) {
      const pageNorm = normalize(p.text || "");

      let score = 0;
      tokens.forEach((w) => {
        if (pageNorm.includes(w)) score++;
      });

      if (score > bestScore) {
        bestScore = score;
        bestPage = p.page_number;
      }
    }

    setMatchedPage(bestPage);
    setMatchedScore(bestScore);

    // Auto-jump when strong match
    if (bestPage && bestScore >= 5 && !hasJumpedRef.current) {
      hasJumpedRef.current = true;
      onPageChange(bestPage);

      logEvent("auto_jump_page", {
        bestPage,
        bestScore,
        source: "cmc_viewer_auto_jump",
      });
    }
  }, [document, cmcContext, onPageChange]);

  /* -----------------------------------------------------
        UI
  ----------------------------------------------------- */
  return (
    <div className="h-full w-full bg-white rounded-2xl shadow-sm border border-slate-200 flex flex-col overflow-hidden">

      {/* HEADER */}
      <div className="px-4 py-2 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold text-slate-700">
            Affected Section (From CMC)
          </div>
          <div className="text-[11px] text-slate-400">
            Auto-detected excerpt linked to the PDF on the left.
          </div>
        </div>

        {/* ⭐ Jump button (only when match exists) */}
        {matchedPage && matchedScore >= 3 && (
          <button
            onClick={() => onPageChange(matchedPage)}
            className="px-2 py-1 text-[11px] bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            Go to Page {matchedPage}
          </button>
        )}
      </div>

      {/* BODY */}
      <div className="flex-1 p-3 overflow-auto">
        {cmcContext ? (
          <>
            {/* ⭐ Show match details */}
            {matchedPage && (
              <div className="text-[11px] text-slate-500 mb-1">
                Found on <span className="font-semibold text-indigo-700">Page {matchedPage}</span>{" "}
                (score {matchedScore})
              </div>
            )}

            <pre className="bg-yellow-50 border border-yellow-200 rounded-xl px-3 py-2 
                             text-[11px] leading-relaxed text-slate-900 whitespace-pre-wrap font-mono">
              {cmcContext}
            </pre>
          </>
        ) : (
          <div className="text-xs text-slate-400 italic">
            Run <span className="font-semibold">“Generate AI Rewrite”</span> to detect and jump to
            the affected CMC section in the PDF.
          </div>
        )}
      </div>
    </div>
  );
}
