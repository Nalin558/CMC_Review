// src/App.js
import React, { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import "./App.css";
import CommentPanel from "./components/CommentPanel";
import PdfPageViewer from "./components/PdfPageViewer";
import { logEvent, getSessionId } from "./logService";

const API_BASE = "http://127.0.0.1:8001";

function App() {
  const [documentData, setDocumentData] = useState(null);
  const [documentUploaded, setDocumentUploaded] = useState(false); // Track if PDF is uploaded
  const [showMainUI, setShowMainUI] = useState(false); // Controls when to show main UI
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [comment, setComment] = useState("");
  const [comments, setComments] = useState([]); // List of comments
  const [answerData, setAnswerData] = useState(null);
  const [batchResults, setBatchResults] = useState([]); // Results for all comments
  const [loading, setLoading] = useState(false);
  const [backendError, setBackendError] = useState(null);
  const [currentPdfPage, setCurrentPdfPage] = useState(1);
  const [leftPaneWidth, setLeftPaneWidth] = useState(55);
  const [pdfBlobUrl, setPdfBlobUrl] = useState("/cmc.pdf");
  const [isHighlighting, setIsHighlighting] = useState(false);
  const [currentResultIndex, setCurrentResultIndex] = useState(null);

  // On initial load, clear any existing uploaded document so upload UI is always shown first
  useEffect(() => {
    const clearAndCheckDocument = async () => {
      try {
        await axios.post(`${API_BASE}/cmc/clear-document`);
        // After clearing, check PDF status
        const res = await axios.get(`${API_BASE}/api/pdf/status`);
        if (res.data && res.data.has_pdf) {
          setShowMainUI(true);
          setDocumentUploaded(true);
        } else {
          setShowMainUI(false);
          setDocumentUploaded(false);
        }
      } catch (err) {
        console.log("Error during clear and check:", err);
        setShowMainUI(false);
        setDocumentUploaded(false);
      }
    };
    clearAndCheckDocument();
  }, []);
// Remove duplicate code above
  useEffect(() => {
    if (!showMainUI) return;
    const fetchDoc = async () => {
      try {
        const res = await axios.get(`${API_BASE}/cmc/document`);
        setDocumentData(res.data);
      } catch (err) {
        console.error(err);
        setBackendError("Failed to load CMC document");
      }
    };
    fetchDoc();
  }, [showMainUI]);
  // Upload handler
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await axios.post(`${API_BASE}/cmc/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setDocumentUploaded(true);
      setShowMainUI(true);
    } catch (err) {
      setUploadError("Failed to upload file. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  // MAIN: Run AI review + backend highlight
  const handleRunReview = async () => {
    if (!comment.trim()) return;

    setLoading(true);
    setBackendError(null);

    try {
      // Step 1: LLM review
      const res = await axios.post(`${API_BASE}/cmc/answer`, {
        comment: comment.trim(),
        cmc_k: 3,
        guideline_k: 5,
      });
      setAnswerData(res.data);

      const sectionText = res.data?.llm_result?.cmc_context_used || "";

      // Step 2: backend highlight
      if (sectionText.length > 20) {
        const highlightRes = await axios.post(
          `${API_BASE}/cmc/highlight`,
          { text: sectionText },
          { responseType: "blob" }
        );

        const blobUrl = URL.createObjectURL(highlightRes.data);
        setPdfBlobUrl(blobUrl);
      } else {
        setPdfBlobUrl("/cmc.pdf");
      }
    } catch (err) {
      console.error(err);
      setBackendError("Error processing comment");
    } finally {
      setLoading(false);
    }
  };

  // Add comment to list and clear input
  const handleAddComment = () => {
    if (comment.trim()) {
      setComments([...comments, comment.trim()]);
      setComment(""); // Clear input field
    }
  };

  // Process all comments in batch
  const handleProcessBatch = async () => {
    if (comments.length === 0) return;

    setLoading(true);
    setBackendError(null);
    setBatchResults([]);
    setCurrentResultIndex(0);

    try {
      const res = await axios.post(`${API_BASE}/cmc/answer-batch`, {
        comments: comments,
        cmc_k: 3,
        guideline_k: 5,
      });

      const results = res.data.results || [];
      setBatchResults(results);
      
      // Set first result as active and highlight it
      if (results.length > 0) {
        const firstResult = results[0];
        if (firstResult?.llm_result) {
          const sectionText = firstResult.llm_result.cmc_context_used || "";
          
          if (sectionText.length > 20) {
            setIsHighlighting(true);
            try {
              const highlightRes = await axios.post(
                `${API_BASE}/cmc/highlight`,
                { text: sectionText },
                { responseType: "blob" }
              );
              const blobUrl = URL.createObjectURL(highlightRes.data);
              setPdfBlobUrl(blobUrl);
            } finally {
              setTimeout(() => setIsHighlighting(false), 800);
            }
          }
        }
      }
      logEvent("batch_comments_processed", { 
        total_comments: comments.length,
        total_errors: res.data.total_errors 
      });
    } catch (err) {
      console.error(err);
      setBackendError("Error processing batch comments");
    } finally {
      setLoading(false);
    }
  };

  // In-memory cache for this browser session (cleared on tab close)
  const highlightCacheRef = useRef(new Map()); // key -> { blobUrl, text }

  // simple non-crypto string hash (djb2) for cache key
  function hashKey(str) {
    let h = 5381;
    for (let i = 0; i < str.length; i++) {
      h = (h * 33) ^ str.charCodeAt(i);
    }
    return (h >>> 0).toString(36);
  }

  const handleHighlightSection = async (sectionText) => {
    if (!sectionText || sectionText.length < 20) return;
    const key = hashKey(sectionText);

    const cache = highlightCacheRef.current;
    if (cache.has(key)) {
      // Use cached object URL
      const cached = cache.get(key);
      setPdfBlobUrl(cached.blobUrl);
      // ensure brief UI feedback
      setIsHighlighting(false);
      return;
    }

    try {
      setIsHighlighting(true);
      const highlightRes = await axios.post(
        `${API_BASE}/cmc/highlight`,
        { text: sectionText },
        { responseType: "blob" }
      );
      const blob = highlightRes.data;
      const blobUrl = URL.createObjectURL(blob);
      setPdfBlobUrl(blobUrl);
      // store in session cache
      cache.set(key, { blobUrl, text: sectionText });
    } catch (err) {
      console.error("Error highlighting PDF:", err);
    } finally {
      setTimeout(() => setIsHighlighting(false), 600);
    }
  };

  // Helper to detect matched page for section text
  const detectMatchedPage = (sectionText) => {
    if (!documentData?.pages || !sectionText) return null;
    try {
      const contextNorm = (sectionText || "")
        .replace(/-\s*\n/g, "")
        .replace(/\s+/g, " ")
        .toLowerCase()
        .trim();
      const tokens = contextNorm.split(" ").filter((w) => w.length > 5);
      if (tokens.length === 0) return null;
      
      let bestPage = null;
      let bestScore = 0;
      for (const p of documentData.pages) {
        const pageNorm = (p.text || "")
          .replace(/-\s*\n/g, "")
          .replace(/\s+/g, " ")
          .toLowerCase()
          .trim();
        let score = 0;
        tokens.forEach((w) => {
          if (pageNorm.includes(w)) score++;
        });
        if (score > bestScore) {
          bestScore = score;
          bestPage = p.page_number;
        }
      }
      return bestPage;
    } catch (e) {
      return null;
    }
  };

  // Navigate to next result in batch
  const handleNextResult = async () => {
    if (currentResultIndex < batchResults.length - 1) {
      const nextIndex = currentResultIndex + 1;
      setCurrentResultIndex(nextIndex);
      
      const result = batchResults[nextIndex];
      if (result?.llm_result) {
        const sectionText = result.llm_result.cmc_context_used || "";
        
        if (sectionText.length > 20) {
          // Use cache-aware highlight handler
          await handleHighlightSection(sectionText);
          
          // Auto-detect and jump to matched page
          const matchedPage = detectMatchedPage(sectionText);
          if (matchedPage) {
            setCurrentPdfPage(matchedPage);
          }
        }
      }
    }
  };

  // Navigate to previous result in batch
  const handlePrevResult = async () => {
    if (currentResultIndex > 0) {
      const prevIndex = currentResultIndex - 1;
      setCurrentResultIndex(prevIndex);
      
      const result = batchResults[prevIndex];
      if (result?.llm_result) {
        const sectionText = result.llm_result.cmc_context_used || "";
        
        if (sectionText.length > 20) {
          // Use cache-aware highlight handler
          await handleHighlightSection(sectionText);
          
          // Auto-detect and jump to matched page
          const matchedPage = detectMatchedPage(sectionText);
          if (matchedPage) {
            setCurrentPdfPage(matchedPage);
          }
        }
      }
    }
  };

  // Clear all comments and results
  const handleClearComments = () => {
    setComments([]);
    setBatchResults([]);
    setComment("");
    setCurrentResultIndex(null);
    setAnswerData(null);
    setPdfBlobUrl("/cmc.pdf");
  };

  // Get current active result for display
  const currentResult = currentResultIndex !== null && batchResults[currentResultIndex] 
    ? batchResults[currentResultIndex]
    : answerData;

  // pane drag logic
  const handleDragStart = useCallback(
    (e) => {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = leftPaneWidth;

      const onMouseMove = (ev) => {
        const delta = ev.clientX - startX;
        const viewportWidth = window.innerWidth || 1;
        const newWidth = Math.max(
          30,
          Math.min(70, startWidth + (delta / viewportWidth) * 100)
        );
        setLeftPaneWidth(newWidth);
      };

      const onMouseUp = () => {
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [leftPaneWidth]
  );

  const totalPages = documentData?.num_pages || 0;

  // cleanup object URLs on unload to avoid leaking memory
  useEffect(() => {
    const onUnload = () => {
      const cache = highlightCacheRef.current;
      for (const v of cache.values()) {
        try {
          URL.revokeObjectURL(v.blobUrl);
        } catch (e) {}
      }
      cache.clear();
    };
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
  }, []);

  // Always show upload UI until PDF is uploaded (showMainUI true)
  if (!documentUploaded) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-100">
        <div className="bg-white p-8 rounded shadow-md flex flex-col items-center gap-4 border-2 border-dashed border-orange-400" style={{ minWidth: 350, minHeight: 350, background: '#fff8e1' }}>
          <div className="text-xl font-bold text-orange-800 mb-2">Upload New PDF</div>
          <div className="flex flex-col items-center gap-2 flex-1 justify-center">
            <div style={{ fontSize: 60, color: '#b26a00' }}>
              <svg width="48" height="48" fill="none" viewBox="0 0 48 48"><rect width="48" height="48" rx="8" fill="#FFF3E0"/><path d="M24 12v16m0 0l-6-6m6 6l6-6" stroke="#B26A00" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/><rect x="12" y="32" width="24" height="4" rx="2" fill="#B26A00"/></svg>
            </div>
            <div className="text-lg font-semibold text-orange-900">Upload a PDF Document</div>
            <div className="text-sm text-orange-700 mb-2">Drag and drop your PDF here, or click to select a file</div>
            <label className="block">
              <input
                type="file"
                accept="application/pdf"
                onChange={handleFileUpload}
                disabled={uploading}
                className="hidden"
              />
              <span className="inline-block px-6 py-2 bg-orange-600 text-white rounded cursor-pointer hover:bg-orange-700 font-semibold">Browse Files</span>
            </label>
            <div className="text-xs text-orange-700 mt-2">Maximum file size: 100MB | Format: PDF only</div>
            {uploading && <div className="text-blue-600 text-sm mt-2">Uploading...</div>}
            {uploadError && <div className="text-red-600 text-sm mt-2">{uploadError}</div>}
          </div>
        </div>
      </div>
    );
  }

  // Main UI after upload
  if (showMainUI) {
    return (
      <div className="min-h-screen bg-slate-100 flex flex-col">
        {/* HEADER */}
        <header className="h-14 flex items-center gap-2 px-6 border-b bg-white shadow-sm">
          <div className="h-8 w-8 rounded-xl bg-blue-600 text-white flex items-center justify-center text-sm font-bold">
            C3
          </div>
          <span className="text-sm font-semibold text-slate-900">CMC Review</span>
        </header>

        {/* MAIN */}
        <main className="flex-1 flex flex-row overflow-hidden min-h-0">
          {/* LEFT PANE — PDF Preview */}
          <div
            className="flex flex-col flex-1 min-h-0 border-r bg-slate-50"
            style={{ width: `${leftPaneWidth}%` }}
          >
            <PdfPageViewer
              pdfUrl={pdfBlobUrl}
              pageNumber={currentPdfPage}
              totalPages={totalPages}
              onPageChange={setCurrentPdfPage}
              commentText={comment}
              commentNumber={currentResultIndex !== null ? currentResultIndex + 1 : ""}
              isHighlighting={isHighlighting}
              onGoToPage={setCurrentPdfPage}
            />
          </div>

          {/* SPLITTER */}
          <div
            className="w-[6px] cursor-col-resize bg-slate-200 hover:bg-slate-400"
            onMouseDown={handleDragStart}
          />

          {/* RIGHT PANE — Comment Panel */}
          <div className="flex-1 h-full flex flex-col bg-slate-50 p-4 gap-4 overflow-hidden">
            <div className="flex-1 min-h-0">
              <CommentPanel
                comment={comment}
                onChangeComment={setComment}
                comments={comments}
                onAddComment={handleAddComment}
                onClearComments={handleClearComments}
                onProcessBatch={handleProcessBatch}
                onRun={handleRunReview}
                loading={loading}
                answerData={currentResult}
                documentData={documentData}
                onGoToPage={(p) => setCurrentPdfPage(p)}
                onHighlightSection={handleHighlightSection}
                isHighlighting={isHighlighting}
                batchResults={batchResults}
                currentResultIndex={currentResultIndex}
                onNextResult={handleNextResult}
                onPrevResult={handlePrevResult}
              />
            </div>

            {backendError && (
              <div className="text-xs text-red-600 bg-red-50 p-2 border rounded">
                {backendError}
              </div>
            )}
          </div>
        </main>
      </div>
    );
  }
}
export default App;
