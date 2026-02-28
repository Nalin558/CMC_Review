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
