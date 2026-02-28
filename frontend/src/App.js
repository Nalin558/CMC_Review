// src/App.js
import React, { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import "./App.css";
import CommentPanel from "./components/CommentPanel";
import PdfPageViewer from "./components/PdfPageViewer";
import UniversalNavbar from "./components/UniversalNavbar";
import Dashboard from "./components/Dashboard";
import PdfUploadComponent from "./components/PdfUploadComponent";
import { logEvent, getSessionId } from "./logService";

const API_BASE = "http://127.0.0.1:8001";

function App() {
  const [documentData, setDocumentData] = useState(null);
  const [comment, setComment] = useState("");
  const [comments, setComments] = useState([]); // List of comments
  const [answerData, setAnswerData] = useState(null);
  const [batchResults, setBatchResults] = useState([]); // Results for all comments
  const [loading, setLoading] = useState(false);
  const [backendError, setBackendError] = useState(null);
  const [isDarkMode, setIsDarkMode] = useState(false);

  // PDF Upload State
  const [pdfLoaded, setPdfLoaded] = useState(false);
  const [currentPdfName, setCurrentPdfName] = useState("");
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [indexingInProgress, setIndexingInProgress] = useState(false);
  const [currentPdfPage, setCurrentPdfPage] = useState(1);
  const [leftPaneWidth, setLeftPaneWidth] = useState(55);

  // highlighted PDF blob - null until PDF is loaded
  const [pdfBlobUrl, setPdfBlobUrl] = useState(null);
  // track current object URL so we can revoke it when replaced
  const currentPdfObjectRef = useRef(null);

  const setPdfBlobObjectUrl = (url) => {
    // Revoke previous object URL if it was a blob
    try {
      if (currentPdfObjectRef.current && currentPdfObjectRef.current.startsWith('blob:')) {
        URL.revokeObjectURL(currentPdfObjectRef.current);
      }
    } catch (e) {}
    if (url && url.startsWith && url.startsWith('blob:')) {
      currentPdfObjectRef.current = url;
    } else {
      currentPdfObjectRef.current = null;
    }
    setPdfBlobUrl(url);
  };

  // Called when a session PDF is updated (e.g. after approving changes)
  // - sets the new blob URL (and revokes previous)
  // - clears the in-memory highlight cache so stale highlights won't be reused
  // - refreshes server-side document metadata (pages/text) so page detection stays correct
  const handlePdfUpdate = async (blobUrl, pageNumber = null) => {
    // Apply page number first so PDF.js will open the new blob on the desired page
    if (pageNumber) {
      setCurrentPdfPage(pageNumber);
    }

    setPdfBlobObjectUrl(blobUrl);

    // Clear highlight cache (document changed)
    try {
      highlightCacheRef.current.clear();
    } catch (e) {
      console.warn('Failed to clear highlight cache:', e);
    }

    // Refresh document metadata (pages/text) so detectMatchedPage works on updated PDF
    try {
      const res = await axios.get(`${API_BASE}/cmc/document`);
      setDocumentData(res.data);
    } catch (e) {
      console.warn('Failed to refresh document metadata:', e);
    }
  };
  const [isHighlighting, setIsHighlighting] = useState(false);

  // Track which result is currently being viewed
  const [currentResultIndex, setCurrentResultIndex] = useState(null);

  // DASHBOARD STATE
  const [dashboardData, setDashboardData] = useState(null);

  // In-memory cache for this browser session (cleared on tab close)
  const highlightCacheRef = useRef(new Map()); // key -> { blobUrl, text }

  // session start logging & cleanup - ONLY ON ACTUAL PAGE RELOAD, NOT RE-RENDERS
  useEffect(() => {
    // Use sessionStorage to detect if this is an actual page reload
    // sessionStorage persists across component mounts but clears on page reload
    const hasInitialized = sessionStorage.getItem('app_initialized');
    
    if (!hasInitialized) {
      // First time loading this page - clear PDFs and show upload UI
      sessionStorage.setItem('app_initialized', 'true');
      
      logEvent("session_start", { session_id: getSessionId() });

      // Clear results on refresh/mount
      axios.post(`${API_BASE}/cmc/results/clear`)
        .catch(err => console.error("Failed to clear results on mount:", err));

      // Clear any existing PDFs on mount so upload UI is shown first
      // This only happens on actual page reload, not on component re-mounts
      axios.post(`${API_BASE}/cmc/clear-document`)
        .catch(err => console.error("Failed to clear document on mount:", err));
    }
    
    // Check PDF status on mount (whether first time or not)
    checkPdfStatus();
  }, []);

  const checkPdfStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/pdf/status`);
      console.log("📊 PDF status on mount:", res.data);
      if (res.data.has_pdf && res.data.current_pdf) {
        setPdfLoaded(true);
        setCurrentPdfName(res.data.current_pdf);
        // Try to load document data
        try {
          const docRes = await axios.get(`${API_BASE}/cmc/document`);
          setDocumentData(docRes.data);
          // Set the PDF URL to the frontend public path (served by React dev server)
          const pdfUrl = "/cmc.pdf";
          console.log("📤 Setting PDF URL on mount:", pdfUrl);
          setPdfBlobUrl(pdfUrl);
        } catch (err) {
          console.warn("❌ Could not load document data:", err);
        }
      } else {
        console.log("❌ No PDF loaded, showing upload UI");
        setPdfLoaded(false);
        setCurrentPdfName("");
        setPdfBlobUrl(null);
      }
    } catch (err) {
      console.warn("❌ Could not check PDF status:", err);
      // Default to showing upload UI on error
      setPdfLoaded(false);
      setPdfBlobUrl(null);
    }
  };

  const handlePdfUploadSuccess = async (data) => {
    console.log("✅ PDF uploaded successfully:", data);
    setPdfLoaded(true);
    setCurrentPdfName(data.filename);
    
    // Try to load document data after PDF upload
    try {
      // Small delay to ensure backend has finished writing cmc_full.json
      await new Promise(resolve => setTimeout(resolve, 500));
      
      console.log("📄 Loading document data from backend...");
      const docRes = await axios.get(`${API_BASE}/cmc/document?t=${Date.now()}`); // Add cache buster
      console.log("✅ Document data loaded - pages:", docRes.data.num_pages);
      setDocumentData(docRes.data);
      
      // Set the PDF URL to the frontend public path (cached on server)
      const pdfUrl = "/cmc.pdf";
      console.log("📤 Setting PDF URL:", pdfUrl);
      setPdfBlobUrl(pdfUrl);
      
      // Clear any previous results
      setComments([]);
      setBatchResults([]);
      setComment("");
      setCurrentResultIndex(null);
      setAnswerData(null);
      logEvent("pdf_uploaded", { filename: data.filename });
    } catch (err) {
      console.error("❌ Failed to load document data after upload:", err);
      setBackendError("Failed to load document data - backend error");
    }
  };

  const handlePdfUploadError = (error) => {
    console.error("PDF upload error:", error);
    setBackendError(error);
  };

  // load base document metadata and ensure PDF is loaded
  useEffect(() => {
    if (!pdfLoaded) return;

    const fetchDocData = async () => {
      try {
        const res = await axios.get(`${API_BASE}/cmc/document`);
        setDocumentData(res.data);
      } catch (err) {
        console.error("Failed to load document data:", err);
        setBackendError("Failed to load document data");
      }
    };
    
    fetchDocData();
  }, [pdfLoaded]);

  // MAIN: Run AI review + backend highlight
  const handleRunReview = async () => {
    if (!comment.trim()) return;

    setLoading(true);
    setBackendError(null);

    try {
      // Step 1: LLM review
      const res = await axios.post(`${API_BASE}/cmc/answer`, {
        comment: comment.trim(),
        cmc_k: 5,
        guideline_k: 5,
      });
      setAnswerData(res.data);

      const sectionText = res.data?.llm_result?.cmc_context_used || "";

      // Step 2: backend highlight
      if (sectionText.length > 20) {
        const highlightRes = await axios.post(
          `${API_BASE}/cmc/highlight`,
          { text: sectionText, session_id: getSessionId() },
          { responseType: "blob" }
        );

        const blobUrl = URL.createObjectURL(highlightRes.data);
        setPdfBlobObjectUrl(blobUrl);

        // AUTO-NAVIGATE: Read X-Highlight-Page header and jump to first highlighted page
        const firstHighlightedPage = highlightRes.headers['x-highlight-page'];
        if (firstHighlightedPage) {
          const pageNum = parseInt(firstHighlightedPage, 10);
          if (!isNaN(pageNum) && pageNum > 0) {
            setCurrentPdfPage(pageNum);
            logEvent("auto_navigate_to_highlight", {
              page: pageNum,
              total_highlights: highlightRes.headers['x-total-highlights'],
              highlighted_pages: highlightRes.headers['x-highlighted-pages'],
            });
          }
        }
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
        cmc_k: 5,
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
                { text: sectionText, session_id: getSessionId() },
                { responseType: "blob" }
              );
              const blobUrl = URL.createObjectURL(highlightRes.data);
              setPdfBlobObjectUrl(blobUrl);

              // AUTO-NAVIGATE: Read X-Highlight-Page header and jump to first highlighted page
              const firstHighlightedPage = highlightRes.headers['x-highlight-page'];
              if (firstHighlightedPage) {
                const pageNum = parseInt(firstHighlightedPage, 10);
                if (!isNaN(pageNum) && pageNum > 0) {
                  setCurrentPdfPage(pageNum);
                  logEvent("auto_navigate_to_highlight", {
                    page: pageNum,
                    total_highlights: highlightRes.headers['x-total-highlights'],
                    highlighted_pages: highlightRes.headers['x-highlighted-pages'],
                  });
                }
              }
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

  // Navigate to next result in batch
  const handleNextResult = async () => {
    if (currentResultIndex < batchResults.length - 1) {
      const nextIndex = currentResultIndex + 1;
      setCurrentResultIndex(nextIndex);

      const result = batchResults[nextIndex];
      if (result?.llm_result) {
        const sectionText = result.llm_result.cmc_context_used || "";

        if (sectionText.length > 20) {
          // Auto-detect and jump to matched page FIRST
          const matchedPage = detectMatchedPage(sectionText);
          if (matchedPage) {
            setCurrentPdfPage(matchedPage);
          }

          // Then highlight (page will be visible while highlighting)
          await handleHighlightSection(sectionText);
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
          // Auto-detect and jump to matched page FIRST
          const matchedPage = detectMatchedPage(sectionText);
          if (matchedPage) {
            setCurrentPdfPage(matchedPage);
          }

          // Then highlight (page will be visible while highlighting)
          await handleHighlightSection(sectionText);
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
    if (pdfBlobUrl) {
      setPdfBlobUrl(pdfBlobUrl);
    }
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

  // simple non-crypto string hash (djb2) for cache key
  function hashKey(str) {
    let h = 5381;
    for (let i = 0; i < str.length; i++) {
      h = (h * 33) ^ str.charCodeAt(i);
    }
    return (h >>> 0).toString(36);
  }

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

  const handleHighlightSection = async (sectionText) => {
    if (!sectionText || sectionText.length < 20) return;
    const key = hashKey(sectionText);

    const cache = highlightCacheRef.current;
    if (cache.has(key)) {
      // Use cached object URL
      const cached = cache.get(key);
      setPdfBlobObjectUrl(cached.blobUrl);
      // Navigate to cached page if available
      if (cached.pageNum) {
        setCurrentPdfPage(cached.pageNum);
      }
      // ensure brief UI feedback
      setIsHighlighting(false);
      return;
    }

    try {
      setIsHighlighting(true);
      const highlightRes = await axios.post(
        `${API_BASE}/cmc/highlight`,
        { text: sectionText, session_id: getSessionId() },
        { responseType: "blob" }
      );
      const blob = highlightRes.data;
      const blobUrl = URL.createObjectURL(blob);
      setPdfBlobObjectUrl(blobUrl);
      
      // AUTO-NAVIGATE: Read X-Highlight-Page header and jump to first highlighted page
      let pageNum = null;
      const firstHighlightedPage = highlightRes.headers['x-highlight-page'];
      if (firstHighlightedPage) {
        pageNum = parseInt(firstHighlightedPage, 10);
        if (!isNaN(pageNum) && pageNum > 0) {
          setCurrentPdfPage(pageNum);
          logEvent("auto_navigate_to_highlight", {
            page: pageNum,
            total_highlights: highlightRes.headers['x-total-highlights'],
            highlighted_pages: highlightRes.headers['x-highlighted-pages'],
          });
        }
      }
      
      // store in session cache with page number
      cache.set(key, { blobUrl, text: sectionText, pageNum });
    } catch (err) {
      console.error("Error highlighting PDF:", err);
    } finally {
      setTimeout(() => setIsHighlighting(false), 600);
    }
  };

  // cleanup object URLs on unload to avoid leaking memory
  useEffect(() => {
    const onUnload = () => {
      const cache = highlightCacheRef.current;
      for (const v of cache.values()) {
        try {
          URL.revokeObjectURL(v.blobUrl);
        } catch (e) { }
      }
      cache.clear();
    };
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
  }, []);

  /* ---------------- CONDITIONAL FULL-PAGE DASHBOARD ---------------- */
  if (dashboardData) {
    return (
      <Dashboard
        data={dashboardData}
        onBack={() => setDashboardData(null)}
      />
    );
  }

  // If no PDF is loaded, show upload UI
  if (!pdfLoaded) {
    console.log("📤 RENDERING UPLOAD UI - pdfLoaded is false");
    return (
      <div className={`min-h-screen flex flex-col transition-colors duration-300`} style={{ backgroundColor: '#192334' }}>

        {/* Universal Navbar */}

        <UniversalNavbar

          currentPage="CMC Review"

          activeModule="review"

          showHomeButton={true}

        />

        {/* MAIN - Upload UI */}
        <main className="flex-1 flex items-center justify-center px-4">
          <div className="w-full max-w-2xl">
            <PdfUploadComponent
              onUploadSuccess={handlePdfUploadSuccess}
              onUploadError={handlePdfUploadError}
            />
            {backendError && (
              <div className="mt-4 text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded-xl p-3 backdrop-blur-sm">
                {backendError}
              </div>
            )}
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className={`min-h-screen flex flex-col transition-colors duration-300`} style={{ backgroundColor: '#192334' }}>
      {console.log("🎬 RENDERING MAIN UI - pdfLoaded:", pdfLoaded, "pdfBlobUrl:", pdfBlobUrl, "currentPdfName:", currentPdfName)}
       {/* Universal Navbar */}

      <UniversalNavbar

        currentPage={`CMC Review - ${currentPdfName}`}

        activeModule="review"

        showHomeButton={true}

        showUploadButton={true}

        onUploadClick={() => setShowUploadModal(true)}

      />

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">

          <div className="bg-slate-800/90 backdrop-blur-xl rounded-2xl p-6 max-w-2xl w-full mx-4 shadow-2xl border border-slate-700/50">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-black text-white">Upload New PDF</h2>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-slate-400 hover:text-white text-2xl leading-none transition"
              >
                ✕
              </button>
            </div>
            <PdfUploadComponent
              onUploadSuccess={(data) => {
                handlePdfUploadSuccess(data);
                setShowUploadModal(false);
              }}
              onUploadError={handlePdfUploadError}
            />
          </div>
        </div>
      )}

      {/* MAIN */}
      <main className="relative flex-1 flex flex-row overflow-hidden min-h-0">
        {/* LEFT PANE */}
        <div
          className="flex flex-col flex-1 min-h-0 border-r border-slate-700/50 bg-slate-800/60 backdrop-blur-xl shadow-2xl"
          style={{ width: `${leftPaneWidth}%` }}
        >
          <PdfPageViewer
            pdfUrl={pdfBlobUrl}
            pageNumber={currentPdfPage}
            totalPages={documentData?.num_pages || 0}
            onPageChange={setCurrentPdfPage}
            commentText={comment}
            commentNumber={currentResultIndex !== null ? currentResultIndex + 1 : ""}
            isHighlighting={isHighlighting}
            onGoToPage={setCurrentPdfPage}
          />
        </div>

        {/* SPLITTER */}
        <div
          className="w-[6px] cursor-col-resize bg-slate-700/50 hover:bg-gradient-to-b hover:from-green-500 hover:to-teal-500 transition-all duration-300"
          onMouseDown={handleDragStart}
        />

        {/* RIGHT PANE */}
        <div className="flex-1 h-full flex flex-col bg-slate-800/60 backdrop-blur-xl p-4 gap-4 overflow-hidden">
          {/* Comment Panel */}
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
              onViewDashboard={(data) => setDashboardData(data)}
              onPdfUpdate={(url, page) => handlePdfUpdate(url, page)}
            />
          </div>

          {/* Backend Error */}
          {backendError && (
            <div className="text-xs text-red-400 bg-red-900/30 p-3 border border-red-500/50 rounded-lg backdrop-blur-sm">
              {backendError}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
export default App;
