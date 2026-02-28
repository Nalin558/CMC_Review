// src/components/PdfPageViewer.jsx
import React, { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist/legacy/build/pdf";
import {
  PDFSinglePageViewer,
  EventBus,
} from "pdfjs-dist/web/pdf_viewer";
import "pdfjs-dist/web/pdf_viewer.css";
 
pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.js";
 
 
export default function PdfPageViewer({
  pdfUrl = "/cmc.pdf",
  pageNumber,
  totalPages,
  onPageChange,
  commentText,
  commentNumber,
  isHighlighting,
  onGoToPage,
  onPageCount,
  onPdfUpload,
}) {
  const containerRef = useRef(null);
  const viewerRef = useRef(null);
  const fileInputRef = useRef(null);
 
  const [pdfDoc, setPdfDoc] = useState(null);
  const [viewer, setViewer] = useState(null);
  const [eventBus, setEventBus] = useState(null);
  const commentRef = useRef(commentText || "");
  const commentNumRef = useRef(commentNumber || "");
  const [uploading, setUploading] = useState(false);
  
  // Track the last loaded PDF URL to detect changes
  const lastLoadedUrlRef = useRef(null);
 
  // --- Search state and handler (keep in order) ---
  const [searchText, setSearchText] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchMatches, setSearchMatches] = useState([]); // array of page numbers
  const [searchIndex, setSearchIndex] = useState(0); // current match index
 
  const handleSearchAndGo = async () => {
    if (!pdfDoc || !searchText.trim()) return;
    setSearching(true);
    const matches = [];
    for (let i = 1; i <= pdfDoc.numPages; i++) {
      const page = await pdfDoc.getPage(i);
      const textContent = await page.getTextContent();
      const pageText = textContent.items.map(item => item.str).join(" ");
      if (pageText.toLowerCase().includes(searchText.toLowerCase())) {
        matches.push(i);
      }
    }
    setSearchMatches(matches);
    setSearchIndex(0);
    setSearching(false);
    if (matches.length > 0) {
      onPageChange(matches[0]);
    } else {
      alert("Text not found in document.");
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

const handleFileChange = async (e) => {
  const files = e.target.files;
  if (files && files[0]) {
    const file = files[0];
    if (file.type === "application/pdf") {
      try {
        setUploading(true);
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch("http://127.0.0.1:8001/api/pdf/upload", {
          method: "POST",
          body: formData,
        });

        try {
          const result = await response.json();
          console.log("Upload response:", result);
          
          // Call onPdfUpload regardless of status - file is uploaded
          if (onPdfUpload) {
            onPdfUpload(result);
          }
          setUploading(false);
        } catch (parseError) {
          console.error("JSON parse error (but file uploaded):", parseError);
          // File was likely uploaded even if response parsing failed
          setUploading(false);
        }
      } catch (error) {
        console.error("Upload error:", error);
        setUploading(false);
      }
    } else {
      alert("Please upload a PDF file");
    }
  }
  if (fileInputRef.current) {
    fileInputRef.current.value = "";
  }
};
 
  // When searchIndex changes, go to that page
  useEffect(() => {
    if (searchMatches.length > 0 && searchIndex >= 0 && searchIndex < searchMatches.length) {
      onPageChange(searchMatches[searchIndex]);
    }
    // eslint-disable-next-line
  }, [searchIndex]);
 
  // Reset matches if search text changes
  useEffect(() => {
    setSearchMatches([]);
    setSearchIndex(0);
  }, [searchText]);
 
  useEffect(() => {
    commentRef.current = commentText || "";
  }, [commentText]);
 
  useEffect(() => {
    commentNumRef.current = commentNumber || "";
  }, [commentNumber]);
 
  /* ------------------- 1) Load PDF ------------------- */
  useEffect(() => {
    // If no URL provided, clear everything
    if (!pdfUrl || pdfUrl === null || pdfUrl === undefined) {
      console.log("📄 No PDF URL provided, clearing document");
      setPdfDoc(null);
      lastLoadedUrlRef.current = null;
      return;
    }
    
    // Check if this is actually a new URL (ignore if it's the same URL we just loaded)
    if (lastLoadedUrlRef.current === pdfUrl) {
      console.log("📄 Same PDF URL, skipping reload:", pdfUrl);
      return;
    }
    
    console.log("📄 Loading new PDF:", pdfUrl);
    console.log("📄 Previous URL was:", lastLoadedUrlRef.current);
    
    // Clear previous document first
    setPdfDoc(null);
    
    // Load the new PDF
    const loadingTask = pdfjsLib.getDocument(pdfUrl);
    
    loadingTask.promise.then(doc => {
      console.log("✅ PDF loaded successfully, pages:", doc.numPages);
      setPdfDoc(doc);
      lastLoadedUrlRef.current = pdfUrl;
      
      // Always call onPageCount when a new PDF loads
      if (onPageCount && doc?.numPages) {
        console.log("📊 Notifying parent of page count:", doc.numPages);
        onPageCount(doc.numPages);
      }
    }).catch((error) => {
      console.error('❌ Error loading PDF:', error);
      setPdfDoc(null);
      lastLoadedUrlRef.current = null;
    });
    
    // Cleanup function
    return () => {
      // Destroy the loading task if component unmounts during loading
      loadingTask.destroy();
    };
  }, [pdfUrl, onPageCount]);
 
  /* ------------------- 2) Init Viewer Once ------------------- */
  useEffect(() => {
    if (!containerRef.current || !viewerRef.current) return;
 
    const eb = new EventBus();
    const v = new PDFSinglePageViewer({
      container: containerRef.current,
      viewer: viewerRef.current,
      eventBus: eb,
      textLayerMode: 2,
      removePageBorders: true,
    });
 
    eb.on("pagesinit", () => {
      v.currentScaleValue = "page-width";
    });
 
    // initial attach
    eb.on("pagerendered", () => {
      attachCommentIcons();
    });
 
    setViewer(v);
    setEventBus(eb);
  }, []);
 
  /* ------------------- 3) Set Document ------------------- */
  useEffect(() => {
    if (viewer && pdfDoc) {
      console.log("📄 Setting document in viewer");
      viewer.setDocument(pdfDoc);
    }
  }, [viewer, pdfDoc]);
 
  // Show page not found if pageNumber exceeds pdfDoc.numPages
  const [pageError, setPageError] = useState(null);
  useEffect(() => {
    if (pdfDoc && pageNumber > pdfDoc.numPages) {
      setPageError('Page not found');
    } else {
      setPageError(null);
    }
  }, [pdfDoc, pageNumber]);
 
  /* ------------------- 4) App → Viewer ------------------- */
  useEffect(() => {
    if (!viewer) return;
    viewer.currentPageNumber = pageNumber;
   
    // Force container to scroll the page into view
    if (containerRef.current) {
      // Give viewer time to render the page
      requestAnimationFrame(() => {
        const pageView = viewer.pdfViewer?.getPageView(pageNumber - 1);
        if (pageView?.div) {
          pageView.div.scrollIntoView({ behavior: "auto" });
        }
      });
    }
  }, [pageNumber, viewer]);
 
  /* ------------------- 5) Viewer → App ------------------- */
  useEffect(() => {
    if (!eventBus) return;
 
    const handler = (e) => {
      if (e?.pageNumber) onPageChange(e.pageNumber);
    };
 
    eventBus.on("pagechanging", handler);
    return () => eventBus.off("pagechanging", handler);
  }, [eventBus, onPageChange]);
 
// Track the last page number to prevent duplicate calls
  const lastAttachedPageRef = useRef(null);

  /* ============================================================
        ⭐ 6) FIX: Re-attach tooltip after manually changing page
     ============================================================ */
  useEffect(() => {
    if (!viewerRef.current || lastAttachedPageRef.current === pageNumber) return;

    lastAttachedPageRef.current = pageNumber;

    // Use requestAnimationFrame to break synchronous execution and prevent ResizeObserver loops
    const animationId = requestAnimationFrame(() => {
      // Additional delay ensures PDF.js completes layout
      const timer = setTimeout(() => {
        try {
          attachCommentIcons();
        } catch (error) {
          console.warn('Error attaching comment icons:', error);
        }
      }, 160);

      return () => clearTimeout(timer);
    });

    return () => {
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
    };
  }, [pageNumber]); // <— THIS MAKES TOOLTIP STAY WHEN RETURNING TO PAGE
 
 
  /* ============================================================
        ⭐ HIGHLIGHT → ONE ICON + POPUP
     ============================================================ */
  function attachCommentIcons() {
    const root = viewerRef.current;
    if (!root) return;

    try {

      // clear old
      root.querySelectorAll(".comment-icon").forEach((el) => el.remove());
      root.querySelectorAll(".comment-popup").forEach((el) => el.remove());

      const annotationLayer = root.querySelector(".annotationLayer");
      if (!annotationLayer) return;

      // Only consider annotation 'section' elements that have a visible background
      // (many pdf.js sections are structural and not actual highlights). This
      // prevents showing the comment tooltip on pages that don't contain real
      // highlight annotations.
      const allSections = [...annotationLayer.querySelectorAll("section")];
      const quads = allSections.filter((el) => {
        try {
          const cs = window.getComputedStyle(el);
          const bg = cs.backgroundColor || "";
          const opacity = parseFloat(cs.opacity || "1") || 0;
          // treat transparent or empty background as non-highlight
          if (!bg || bg === "transparent" || bg === "rgba(0, 0, 0, 0)") return false;
          // some annotation sections may be non-visible via opacity
          if (opacity === 0) return false;
          // passed checks — treat as a highlight quad
          return true;
        } catch (e) {
          return false;
        }
      });
      if (quads.length === 0) return;
    // compute bounding box (largest highlight)
    let minX = Infinity, minY = Infinity,
        maxX = -Infinity, maxY = -Infinity;
 
    quads.forEach((el) => {
      const r = el.getBoundingClientRect();
      minX = Math.min(minX, r.left);
      minY = Math.min(minY, r.top);
      maxX = Math.max(maxX, r.right);
      maxY = Math.max(maxY, r.bottom);
    });
 
    const parentRect = root.getBoundingClientRect();
    const left = minX - parentRect.left;
    const top = minY - parentRect.top;
 
    /* -------- ICON WITH PULSE ANIMATION -------- */
    const icon = document.createElement("div");
    icon.className = "comment-icon";
    icon.innerText = "💬";
   
    // Add animation style
    const style = document.createElement("style");
    style.textContent = `
      @keyframes pulse-glow {
        0%, 100% { box-shadow: 0 2px 8px rgba(220, 38, 38, 0.4), 0 0 0 0 rgba(220, 38, 38, 0.7); }
        50% { box-shadow: 0 2px 8px rgba(220, 38, 38, 0.6), 0 0 0 8px rgba(220, 38, 38, 0); }
      }
      .comment-icon-highlight {
        animation: pulse-glow 2s infinite;
      }
    `;
    if (!document.querySelector("style[data-comment-animation]")) {
      style.setAttribute("data-comment-animation", "true");
      document.head.appendChild(style);
    }
   
    Object.assign(icon.style, {
      position: "absolute",
      left: `${left}px`,
      top: `${top}px`,
      background: "#dc2626",
      color: "white",
      width: "28px",
      height: "28px",
      borderRadius: "50%",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontSize: "16px",
      cursor: "pointer",
      zIndex: 9999,
      boxShadow: "0 2px 8px rgba(220, 38, 38, 0.4)",
      transition: "transform 0.2s ease",
    });
   
    icon.classList.add("comment-icon-highlight");
    icon.addEventListener("mouseover", () => {
      icon.style.transform = "scale(1.15)";
    });
    icon.addEventListener("mouseout", () => {
      icon.style.transform = "scale(1)";
    });
 
    /* -------- POPUP WITH COMMENT NUMBER -------- */
    const popup = document.createElement("div");
    popup.className = "comment-popup";
   
    const commentNum = commentNumRef.current;
    const popupText = commentNum
      ? `Comment #${commentNum}\n\n${commentRef.current || "Reviewer comment"}`
      : commentRef.current || "Reviewer comment";
   
    popup.innerText = popupText;
    Object.assign(popup.style, {
      position: "absolute",
      left: `${left + 36}px`,
      top: `${top - 15}px`,
      padding: "12px 14px",
      maxWidth: "300px",
      background: "#1f2937",
      color: "white",
      border: "2px solid #dc2626",
      borderRadius: "8px",
      boxShadow: "0 8px 16px rgba(0,0,0,0.4)",
      fontSize: "12px",
      display: "none",
      zIndex: 10000,
      fontWeight: "500",
      lineHeight: "1.5",
      whiteSpace: "pre-wrap",
      wordWrap: "break-word",
    });
 
    icon.onclick = (ev) => {
      ev.stopPropagation();
      popup.style.display = popup.style.display === "none" ? "block" : "none";
    };
 
    const clickHandler = (e) => {
      if (!icon.contains(e.target) && !popup.contains(e.target)) {
        popup.style.display = "none";
      }
    };
    document.addEventListener("click", clickHandler);
 
    popup.addEventListener("DOMNodeRemoved", () => {
      document.removeEventListener("click", clickHandler);
    });
 
    root.appendChild(icon);
    root.appendChild(popup);
    } catch (error) {
      console.warn('Error attaching comment icons:', error);
    }
  }
 
  // Highlight search matches on the current page
  useEffect(() => {
    if (!searchText || !pdfDoc || searchMatches.length === 0) return;
    // Wait for text layer to render
    const timer = setTimeout(() => {
      const textLayer = containerRef.current?.querySelector('.textLayer');
      if (!textLayer) return;
      // Remove previous highlights
      // Remove previous highlights by replacing highlight spans with their text content
      textLayer.querySelectorAll('.search-highlight').forEach(el => {
        const parent = el.parentNode;
        if (parent) {
          parent.replaceChild(document.createTextNode(el.textContent), el);
        }
      });
      if (!searchText.trim()) return;
      // Highlight all matches on the current page, only wrapping matching text nodes
      const regex = new RegExp(searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
      textLayer.querySelectorAll('span').forEach(span => {
        for (let node of Array.from(span.childNodes)) {
          if (node.nodeType === Node.TEXT_NODE && regex.test(node.textContent)) {
            const frag = document.createDocumentFragment();
            let lastIndex = 0;
            node.textContent.replace(regex, (match, offset) => {
              // Text before match
              if (offset > lastIndex) {
                frag.appendChild(document.createTextNode(node.textContent.slice(lastIndex, offset)));
              }
              // Highlighted match
              const mark = document.createElement('span');
              mark.className = 'search-highlight';
              mark.textContent = match;
              frag.appendChild(mark);
              lastIndex = offset + match.length;
              return match;
            });
            // Remaining text after last match
            if (lastIndex < node.textContent.length) {
              frag.appendChild(document.createTextNode(node.textContent.slice(lastIndex)));
            }
            span.replaceChild(frag, node);
          }
        }
      });
    }, 120);
    return () => clearTimeout(timer);
  }, [pageNumber, searchText, searchMatches, pdfDoc]);
 
  /* -------- UI -------- */
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Toolbar */}
      <div className="h-14 px-4 flex items-center justify-between border-b border-slate-700/50 bg-slate-900/60 backdrop-blur-xl text-xs gap-3">
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span className="font-semibold text-slate-300">
            PDF ({pageNumber}/{pdfDoc?.numPages || totalPages || 0})
          </span>
          {isHighlighting && (
            <span className="inline-flex items-center gap-2 text-green-400 font-semibold text-xs">
              <span style={{
                display: "inline-block",
                width: "8px",
                height: "8px",
                background: "#4ade80",
                borderRadius: "50%",
                animation: "pulse 1s infinite",
              }} />
              Highlighting...
            </span>
          )}
          {/* Search and Go UI */}
          <input
            type="text"
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            placeholder="Search text"
            style={{ padding: "4px 8px", fontSize: "12px", borderRadius: "4px", border: "1px solid #ccc" }}
            disabled={searching}
          />
          <button
            onClick={handleSearchAndGo}
            style={{
              padding: "6px 10px",
              fontSize: "11px",
              cursor: "pointer",
              border: "1px solid #22c55e",
              borderRadius: "4px",
              background: "#22c55e",
              color: "white",
              fontWeight: "500",
            }}
            disabled={searching}
            title="Search and go to page"
          >
            {searching ? "Searching..." : "Search & Go"}
          </button>
          <button
            onClick={handleUploadClick}
            style={{
              padding: "6px 10px",
              fontSize: "11px",
              cursor: "pointer",
              border: "1px solid #0ea5e9",
              borderRadius: "4px",
              background: "#0ea5e9",
              color: "white",
              fontWeight: "500",
              marginLeft: "8px",
            }}
            disabled={uploading}
            title="Upload a new PDF document"
          >
            {uploading ? "Uploading..." : "📤 Upload"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            style={{ display: "none" }}
          />
          {searchMatches.length > 0 && (
            <span style={{ marginLeft: 6, display: "inline-flex", alignItems: "center", gap: 2 }}>
              <button
                onClick={() => setSearchIndex(i => (i > 0 ? i - 1 : searchMatches.length - 1))}
                style={{ padding: "2px 6px", fontSize: "13px", borderRadius: "3px", border: "1px solid #000", background: "#000", color: "#fff", cursor: "pointer" }}
                title="Previous match"
              >
                &#60;
              </button>
              <span style={{ fontSize: "12px", minWidth: 32, textAlign: "center", color: "#fff" }}>{searchIndex + 1} / {searchMatches.length}</span>
              <button
                onClick={() => setSearchIndex(i => (i < searchMatches.length - 1 ? i + 1 : 0))}
                style={{ padding: "2px 6px", fontSize: "13px", borderRadius: "3px", border: "1px solid #000", background: "#000", color: "#fff", cursor: "pointer" }}
                title="Next match"
              >
                &#62;
              </button>
            </span>
          )}
        </div>
 
        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          <button
            onClick={() => onPageChange(Math.max(1, pageNumber - 1))}
            className="px-4 py-2 text-xs font-medium rounded-lg bg-slate-700/60 hover:bg-slate-600/80 text-slate-200 border border-slate-600/50 transition-all duration-200 hover:scale-105"
          >
            ◀ Prev
          </button>
         
          <button
            onClick={() => onPageChange(Math.min(totalPages, pageNumber + 1))}
            className="px-4 py-2 text-xs font-medium rounded-lg bg-slate-700/60 hover:bg-slate-600/80 text-slate-200 border border-slate-600/50 transition-all duration-200 hover:scale-105"
          >
            Next ▶  
          </button>
 
          {onGoToPage && (
            <button
              onClick={() => {
                const page = prompt("Go to page number:", pageNumber.toString());
                if (page && !isNaN(page)) {
                  const pageNum = parseInt(page);
                  if (pageNum >= 1 && pageNum <= totalPages) {
                    onGoToPage(pageNum);
                  } else {
                    alert(`Please enter a number between 1 and ${totalPages}`);
                  }
                }
              }}
               className="px-4 py-2 text-xs font-bold rounded-lg bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700 text-white border border-green-500/50 transition-all duration-200 hover:scale-105 shadow-lg"
              title="Jump to specific page"
            >
              Go to Page
            </button>
          )}
        </div>
      </div>
 
      {/* Pulse animation keyframes */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
 
      {/* PDF Viewer */}
      <div className="relative flex-1 bg-slate-900 overflow-hidden">
        {pageError ? (
          <div className="flex items-center justify-center h-full text-red-600 text-lg font-semibold">
            {pageError}
          </div>
        ) : (
          <div ref={containerRef} style={{ position: "absolute", inset: 0, overflow: "auto" }}>
            <div
              ref={viewerRef}
              className="pdfViewer"
              style={{ position: "relative", width: "100%", height: "100%" }}
            />
          </div>
        )}
      </div>
 
      {/* Highlighted search term style */}
      <style>{`
        .search-highlight {
          background: #1e293b !important; /* much darker gray */
          color: #fff !important;
          border-radius: 2px;
          box-shadow: 0 0 0 2px #111, 0 2px 8px #111a;
          padding: 0 2px;
          transition: background 0.2s;
        }
      `}</style>
    </div>
  );
}