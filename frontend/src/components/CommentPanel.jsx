// src/components/CommentPanel.jsx
import React, { useState } from "react";
import axios from "axios";
import { logEvent, getSessionId } from "../logService";
import DiffSideBySide from "./DiffSideBySide";
import GuidelineValidator from "./GuidelineValidator";
import ProcessLogs from "./ProcessLogs";

const API_BASE = "http://127.0.0.1:8001";

export default function CommentPanel({
  comment,
  onChangeComment,
  comments,
  onAddComment,
  onClearComments,
  onProcessBatch,
  onRun,
  loading,
  answerData,
  batchResults,
  currentResultIndex,
  onNextResult,
  onPrevResult,
  documentData,
  onGoToPage,
  onHighlightSection,
  isHighlighting,
  onPdfUpdate
}) {
  /* ---------------- UI MODE & VALIDATION STATE ---------------- */
  const [uiMode, setUiMode] = useState("default"); // default | impact
  const [commentCache, setCommentCache] = useState({});
  const [validationStatus, setValidationStatus] = useState(null); // null | "none" | "violations"

  const currentCommentCache = commentCache[currentResultIndex] || {
    selectedCmcIndex: 0,
    sections: {},
    loadingLlm: false,
  };
  const selectedCmcIndex = currentCommentCache.selectedCmcIndex;
  const loadingLlm = currentCommentCache.loadingLlm || false;

  const currentSectionCache = currentCommentCache.sections?.[selectedCmcIndex] || {};
  const sectionLlmData = currentSectionCache.sectionLlmData;
  const showLlmResults = currentSectionCache.showResults || false;

  const llm = sectionLlmData || answerData?.llm_result;
  const category = answerData?.category_used;
  const cmcHits = answerData?.cmc_hits || [];
  const comment_text = answerData?.comment || comment;

  // PDF edit modal state
  const [showModal, setShowModal] = useState(false);
  const [startAnchor, setStartAnchor] = useState('');
  const [endAnchor, setEndAnchor] = useState('');
  const [replacementText, setReplacementText] = useState('');
  const [pageNumber, setPageNumber] = useState(1);

  const affectedSection = cmcHits.length > 0
    ? cmcHits[selectedCmcIndex]?.text
    : llm?.cmc_context_used;

  const selectedHit = cmcHits.length > 0 ? cmcHits[selectedCmcIndex] : null;

  const updateCommentCache = (idx, updates) => {
    setCommentCache((prev) => ({
      ...prev,
      [idx]: { ...prev[idx], ...updates },
    }));
  };

  const handleSelectSection = (idx) => {
    updateCommentCache(currentResultIndex, { selectedCmcIndex: idx });
  };

  const handleAiRewrite = async () => {
    if (!cmcHits[selectedCmcIndex]) return;
    updateCommentCache(currentResultIndex, { loadingLlm: true });

    const updatedSections = currentCommentCache.sections || {};
    updateCommentCache(currentResultIndex, { sections: updatedSections });
    updateCommentCache(currentResultIndex, {
      sections: {
        ...updatedSections,
        [selectedCmcIndex]: { ...updatedSections[selectedCmcIndex], showResults: true },
      },
    });

    try {
      const sessionId = getSessionId();
      const endpoint = `${API_BASE}/cmc/answer-section`;
      const payload = {
        comment: comment_text,
        section_text: cmcHits[selectedCmcIndex].text,
        category: category,
        guideline_k: 5,
        session_id: sessionId
      };

      console.debug("POST", endpoint, payload);
      const res = await axios.post(endpoint, payload);

      // Handle unexpected HTML or string payloads (e.g., dev server proxy returned index.html)
      let data = res.data;
      if (typeof data === 'string') {
        try {
          data = JSON.parse(data);
        } catch (e) {
          console.error('Unexpected non-JSON response from LLM endpoint', data.substring(0, 200));
          alert('Error: received unexpected response from server. Please check backend logs.');
          updateCommentCache(currentResultIndex, { loadingLlm: false });
          return;
        }
      }

      if (data.error) {
        alert('LLM generation failed: ' + (data.error || 'Unknown error'));
        updateCommentCache(currentResultIndex, { loadingLlm: false });
        return;
      }

      updateCommentCache(currentResultIndex, {
        sections: {
          ...updatedSections,
          [selectedCmcIndex]: {
            sectionLlmData: data,
            showResults: true,
          },
        },
      });

      logEvent("section_llm_generated", {
        section_index: selectedCmcIndex,
        score: cmcHits[selectedCmcIndex].score
      });
    } catch (err) {
      console.error("Error fetching LLM response:", err);
      const status = err.response?.status;
      if (status === 404) {
        console.error('Endpoint not found (404). Response data:', err.response?.data);
        alert(`AI rewrite failed: Endpoint not found (404). Is backend running at ${API_BASE}?`);
      } else {
        const errMsg = err.response?.data?.error || err.message || 'Unknown error';
        alert('Failed to generate AI rewrite: ' + errMsg);
      }
    } finally {
      updateCommentCache(currentResultIndex, { loadingLlm: false });
    }
  };

  const isBatchMode = batchResults.length > 0;
  const hasPrev = isBatchMode && currentResultIndex > 0;
  const hasNext = isBatchMode && currentResultIndex < batchResults.length - 1;

  /* ---------------- VIEW SWITCH ---------------- */
  if (uiMode === "impact") {
    const sessionId = getSessionId() || "default_session";
    return (
      <div className="flex-1 flex flex-col bg-white rounded-2xl shadow-sm border border-orange-200 overflow-hidden p-3">
        <GuidelineValidator
          initialGuidelines={sectionLlmData?.guideline_context}
          initialParagraph={sectionLlmData?.suggested_cmc_rewrite}
          sessionId={sessionId}
          entryId={sectionLlmData?.entry_id}
          onBack={() => setUiMode("default")}
          onValidationStatusChange={setValidationStatus}
        />
        {/* AUTOMATED APPROVE CHANGES (ONLY IF VALIDATION PASSED) */}
        <button onClick={async () => {
          try {
            if (!window.confirm("Are you sure you want to approve and apply these changes to the PDF?")) return;

            // 1. Calculate Page
            let targetPage = 1;
            if (documentData?.pages) {
              const target = (affectedSection || "").replace(/\s+/g, " ").toLowerCase().trim();
              // Try exact match first
              let page = documentData.pages.find(p =>
                (p.text || "").replace(/\s+/g, " ").toLowerCase().includes(target.substring(0, 50))
              )?.page_number;

              // fuzzy fallback
              if (!page) {
                const chunk = target.substring(0, 50);
                page = documentData.pages.find(p => {
                  const pText = (p.text || "").replace(/\s+/g, " ").toLowerCase();
                  return pText.includes(chunk);
                })?.page_number;
              }
              if (page) targetPage = page;
            }

            // 2. Derive Anchors from Original Text
            const original = (affectedSection || "").trim();
            if (!original || original.length < 10) {
              alert("Original text is too short to automatically replace.");
              return;
            }

            // 3. Call API
            const sessionId = getSessionId() || "default_session";

            // Use the FULL original text as anchors for precise matching
            // This ensures we only replace the exact paragraph, not the entire page
            // The backend will normalize whitespace for matching
            const start_anchor = original.substring(0, Math.min(100, original.length));
            const end_anchor = original.substring(Math.max(0, original.length - 100));

            const response = await axios.post(`${API_BASE}/pdf/replace-paragraph`, {
              page: targetPage,
              start_anchor: start_anchor,
              end_anchor: end_anchor,
              replacement_text: sectionLlmData.suggested_cmc_rewrite || ""
            }, { responseType: 'blob', headers: { 'X-Session-ID': sessionId } });

            // 4. Create blob URL and trigger silent download (no PDF viewer changes)
            const blobUrl = URL.createObjectURL(response.data);

            // Trigger browser download of the edited PDF silently
            try {
              const a = document.createElement('a');
              a.href = blobUrl;
              a.download = `cmc_session_${sessionId}_edited.pdf`;
              a.target = '_blank';
              a.rel = 'noopener noreferrer';
              document.body.appendChild(a);
              a.click();
              a.remove();
              // Clean up URL after delay to ensure download starts reliably
              setTimeout(() => { try { URL.revokeObjectURL(blobUrl); } catch (e) {} }, 1000);
            } catch (err) { console.warn('Download failed', err); }

            alert(`✅ Success! Changes applied to session copy and downloaded.`);
            // Reset validation status after successful approval
            setValidationStatus(null);

          } catch (e) {
            console.error(e);
            if (e.response?.data instanceof Blob) {
              const reader = new FileReader();
              reader.onload = () => {
                try {
                  alert("❌ Failed: " + (JSON.parse(reader.result).error || "Unknown error"));
                } catch (err) { alert("❌ Failed: Unknown error"); }
              }
              reader.readAsText(e.response.data);
            } else {
              alert("❌ Failed to apply changes: " + (e.response?.data?.error || e.message));
            }
          }
        }} disabled={validationStatus !== "none" || loadingLlm} title={validationStatus !== "none" ? "Run Impact Change Analysis first and ensure validation passes" : ""} className={`w-full text-xs py-2 mt-3 rounded-xl font-semibold transition ${validationStatus === "none" ? "bg-green-600 text-white hover:bg-green-700 cursor-pointer" : "bg-slate-700/60 text-slate-400 cursor-not-allowed"}`}>
          ✅ Approve Changes
        </button>
      </div>
    );
  }

  /* ---------------- DEFAULT VIEW ---------------- */
  return (
    <div className="flex-1 flex flex-col bg-slate-800/60 backdrop-blur-xl rounded-2xl shadow-2xl border border-slate-700/50 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700/50 bg-slate-900/60">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-300">
            {isBatchMode ? `Impact Change Comments (${currentResultIndex + 1}/${batchResults.length})` : "Updation Required"}
          </span>
          {comments.length > 0 && (
            <span className="text-xs bg-green-600/30 text-green-300 px-3 py-1 rounded-full font-semibold border border-green-500/50">
              {comments.length} comment{comments.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col p-3 gap-3 overflow-auto">
        {/* INPUT */}
        <div className="border-b border-slate-700/50 pb-4">
          <textarea
             className="w-full min-h-[70px] text-sm rounded-xl border border-slate-600/50 bg-slate-900/60 text-slate-200 px-4 py-3
                       focus:outline-none focus:ring-2 focus:ring-green-500/50 resize-y placeholder-slate-500"
            placeholder="Enter User comment for Impact Change..."
            value={comment}
            onChange={(e) => onChangeComment(e.target.value)}
            disabled={loading}
          />
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => { logEvent("comment_added", { comment }); onAddComment(); }}
              disabled={loading || !comment.trim()}
              className="flex-1 inline-flex items-center justify-center px-3 py-2 text-xs font-semibold rounded-xl
                          bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white shadow-lg
                         disabled:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50 transition-all duration-200 hover:scale-105"
            >
              + Add to List
            </button>
            {comments.length > 0 && (
              <button
                onClick={() => { logEvent("process_batch", { total: comments.length }); onProcessBatch(); }}
                disabled={loading}
                className="flex-1 inline-flex items-center justify-center px-4 py-2.5 text-xs font-bold rounded-xl
                           bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700 text-white shadow-lg
                           disabled:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50 transition-all duration-200 hover:scale-105"
              >
                {loading ? "Processing..." : "Process All"}
              </button>
            )}
          </div>
        </div>

        {/* COMMENTS LIST */}
        {comments.length > 0 && !isBatchMode && (
          <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-3 backdrop-blur-sm">
            <div className="text-xs font-bold text-slate-300 mb-2">Comments to Process:</div>
            <div className="space-y-2 max-h-32 overflow-y-auto">
              {comments.map((cmt, idx) => (
                <div key={idx} className="text-xs bg-slate-800/60 border border-slate-700/50 rounded-lg p-2 flex item-start justify-between gap-2">
                  <span className="flex-1 text-slate-300">{cmt.substring(0, 50)}...</span>
                  <span className="text-slate-500 text-xs flex-shrink-0">#{idx + 1}</span>
                </div>
              ))}
            </div>
            <button onClick={onClearComments} disabled={loading} className="w-full mt-2 text-xs text-red-400 hover:text-red-300 font-bold transition-colors"

            >

              Clear All

            </button>
          </div>
        )}

        {/* BATCH NAV */}
        {isBatchMode && (
          <div className="bg-green-900/30 border border-green-600/50 rounded-xl p-3 backdrop-blur-sm">
            <div className="text-xs font-bold text-green-300 mb-3">Processing Results: {currentResultIndex + 1}/{batchResults.length}</div>
            <div className="flex gap-2 mb-3">
              <button onClick={onPrevResult} disabled={!hasPrev || loading} className="flex-1 px-2 py-1 text-xs font-semibold rounded-lg bg-slate-700/80 hover:bg-slate-600/80 text-slate-200 border border-slate-600/50 disabled:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40 transition-all duration-200 hover:scale-105">← Previous</button>
              <div className="flex-1 inline-flex items-center justify-center px-3 py-2 text-xs font-bold 
                             bg-green-600/30 text-green-300 rounded-lg border border-green-500/50">{currentResultIndex + 1} / {batchResults.length}
              </div>
              <button onClick={onNextResult} disabled={!hasNext || loading} className="flex-1 px-3 py-2 text-xs font-bold rounded-lg bg-slate-700/80 hover:bg-slate-600/80 text-slate-200 border border-slate-600/50
                           disabled:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40 transition-all duration-200 hover:scale-105"
              >Next →</button>
            </div>
            {answerData?.error && <div className="text-xs text-red-400 bg-red-900/30 border border-red-500/50 p-2 rounded-lg backdrop-blur-sm">Error: {answerData.error}</div>}
            <button onClick={onClearComments} disabled={loading} className="w-full mt-2 text-xs text-slate-400 hover:text-slate-300 font-bold transition-colors">Start Over</button>
          </div>
        )}

        {/* RESULTS AREA */}
        {answerData && !answerData.error && (
          <>
            {typeof currentResultIndex === "number" && comments[currentResultIndex] && (
              <div className="text-xs text-slate-300 mb-2 bg-slate-900/40 p-2 rounded-lg border border-slate-700/50"><span className="font-semibold">Result for #{currentResultIndex + 1}:</span> {comments[currentResultIndex]}</div>
            )}

            {cmcHits.length > 0 && (
              <>
                <div className="text-xs font-bold text-slate-300 mt-2 mb-2">Affected CMC Sections ({cmcHits.length})</div>
                <div className="flex gap-2 mb-3 overflow-x-auto pb-1">
                  {cmcHits.map((hit, idx) => (
                    <button key={idx} onClick={() => handleSelectSection(idx)} disabled={loadingLlm}
                      className={`text-xs px-3 py-2 rounded-lg whitespace-nowrap font-bold flex-shrink-0 transition-all duration-200${selectedCmcIndex === idx ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg" : "bg-slate-700/60 text-slate-300 hover:bg-slate-600/80 border border-slate-600/50"} disabled:opacity-50`}>
                      #{idx + 1} ({(hit.score * 100).toFixed(0)}%)
                    </button>
                  ))}
                </div>

                {selectedHit && (
                  <>
                    <div className="text-xs bg-slate-900/60 border border-slate-700/50 rounded-lg p-3 text-slate-300 whitespace-pre-wrap max-h-20 overflow-auto backdrop-blur-sm">{selectedHit.text}</div>
                    <button onClick={async () => {
                      // 1. Trigger highlight and WAIT for it to complete
                      await onHighlightSection(affectedSection);

                      // 2. After highlight is ready, Find and Jump to page
                      if (documentData?.pages) {
                        const target = (affectedSection || "").replace(/\s+/g, " ").toLowerCase().trim();
                        // Try exact match first
                        let page = documentData.pages.find(p =>
                          (p.text || "").replace(/\s+/g, " ").toLowerCase().includes(target.substring(0, 50))
                        )?.page_number;

                        // fuzzy fallback if exact fail
                        if (!page) {
                          // split into chunks
                          const chunk = target.substring(0, 50);
                          page = documentData.pages.find(p => {
                            const pText = (p.text || "").replace(/\s+/g, " ").toLowerCase();
                            return pText.includes(chunk);
                          })?.page_number;
                        }

                        if (page) onGoToPage(page);
                      }
                    }} disabled={isHighlighting || loadingLlm} className="w-full text-xs py-1 mt-2 bg-indigo-600 text-white rounded-lg font-semibold hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed">
                      {isHighlighting ? "Highlighting..." : "Highlight This Section"}
                    </button>
                    <button onClick={handleAiRewrite} disabled={loadingLlm} className="w-full text-xs py-1 mt-2 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 disabled:bg-slate-300 disabled:cursor-not-allowed flex items-center justify-center gap-2">
                      {loadingLlm ? "Generating AI Rewrite..." : "📝 AI Rewrite"}
                    </button>

                  </>
                )}
              </>
            )}

            {showLlmResults && sectionLlmData && (
              <>
                <div className="text-xs font-semibold text-slate-300 mt-3">✨ Summary of Suggested Fix</div>
                <div className="text-xs bg-blue-900/30 border border-blue-600/50 rounded-lg p-3 text-slate-300 whitespace-pre-wrap max-h-20 overflow-auto flex items-center gap-2 backdrop-blur-sm">
                  {loadingLlm ? "Loading..." : sectionLlmData.short_answer || "No summary."}
                </div>
                <div className="text-xs font-semibold text-slate-300 mt-2">✨ Detailed Suggested Rewrite</div>
                <div className="text-xs bg-green-900/30 border border-green-600/50 rounded-lg p-3 text-slate-300 whitespace-pre-wrap max-h-20 overflow-auto flex items-center gap-2 backdrop-blur-sm">
                  {loadingLlm ? "Loading..." : sectionLlmData.suggested_cmc_rewrite || "No rewrite."}
                </div>
                {sectionLlmData.diff_segments?.length > 0 && (
                  <div className="text-xs mt-2">
                    {/* Convert legacy diff_segments into structured blocks for side-by-side rendering */}
                    {(() => {
                      const escapeHtml = (s) => (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                      const blocks = sectionLlmData.diff_segments.map((seg) => {
                        if (seg.op === "replace") {
                          return { type: "replace", old: [{ status: "delete", html: escapeHtml(seg.orig) }], new: [{ status: "insert", html: escapeHtml(seg.suggested) }] };
                        }
                        if (seg.op === "delete") {
                          return { type: "delete", old: [{ status: "delete", html: escapeHtml(seg.orig) }], new: [] };
                        }
                        if (seg.op === "insert") {
                          return { type: "insert", old: [], new: [{ status: "insert", html: escapeHtml(seg.suggested) }] };
                        }
                        // equal
                        return { type: "equal", old: [{ status: "equal", html: escapeHtml(seg.orig) }], new: [{ status: "equal", html: escapeHtml(seg.orig) }] };
                      });

                      return (
                        <div className="bg-slate-50 border border-slate-200 rounded-lg p-2 max-h-40 overflow-auto">
                          <DiffSideBySide structured={{ blocks }} />
                        </div>
                      );
                    })()}
                  </div>
                )}

                {/* VALIDATION STATUS INDICATOR */}
                {validationStatus && (
                  <div className={`text-xs p-2 rounded-lg mt-2 ${validationStatus === "none" ? "bg-green-900/30 border border-green-600/50 text-green-300" : "bg-red-900/30 border border-red-600/50 text-red-300"}`}>
                    {validationStatus === "none" ? "✅ Validation passed - No violations found" : "⚠️ Validation failed - Violations detected"}
                  </div>
                )}

                {/* RUN IMPACT CHANGE ANALYSIS */}
                <button onClick={() => setUiMode("impact")} disabled={loadingLlm} className="w-full text-xs py-2 mt-3 bg-orange-600 text-white rounded-xl font-semibold hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed">
                  🔍 Run Impact Change Analysis
                </button>
              </>
            )}
          </>
        )}
      </div>

      {
        showModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="mt-3 bg-slate-900/60 border border-slate-700/50 rounded-xl p-3 backdrop-blur-sm">
              <h2 className="text-xs font-bold text-slate-300 mb-2 flex items-center justify-between">Edit PDF Paragraph</h2>
              <div className="mb-4">
                <label className="block text-sm font-medium mb-1">Page Number</label>
                <input type="number" value={pageNumber} onChange={e => setPageNumber(parseInt(e.target.value))} className="w-full p-2 border rounded" />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium mb-1">Start Anchor</label>
                <input type="text" value={startAnchor} onChange={e => setStartAnchor(e.target.value)} className="w-full p-2 border rounded" />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium mb-1">End Anchor</label>
                <input type="text" value={endAnchor} onChange={e => setEndAnchor(e.target.value)} className="w-full p-2 border rounded" />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium mb-1">Replacement Text</label>
                <textarea value={replacementText} onChange={e => setReplacementText(e.target.value)} className="w-full p-2 border rounded" rows="5" />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowModal(false)} className="text-xs text-red-400 hover:text-red-300 font-bold transition-colors">Cancel</button>
                <button onClick={async () => {
                  try {
                    const response = await axios.post(`${API_BASE}/pdf/replace-paragraph`, {
                      input_pdf_path: 'frontend/public/cmc.pdf',
                      page: pageNumber,
                      start_anchor: startAnchor,
                      end_anchor: endAnchor,
                      replacement_text: replacementText
                    }, { responseType: 'blob' });

                    const blobUrl = URL.createObjectURL(response.data);
                    const a = document.createElement('a');
                    a.href = blobUrl;
                    a.download = 'cmc_edited.pdf';
                    a.target = '_blank';
                    a.rel = 'noopener noreferrer';
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    setTimeout(() => { try { URL.revokeObjectURL(blobUrl); } catch (e) {} }, 1000);

                    setShowModal(false);
                  } catch (e) { alert('Error: ' + (e.response?.data?.error || e.message)); }
                }} className="text-xs text-red-400 hover:text-red-300 font-bold transition-colors">Download Edited PDF</button>
              </div>
            </div>
          </div>
        )
      }
      <ProcessLogs maxItems={15} />
    </div >
  );
}
