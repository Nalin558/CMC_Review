// Helper to detect matched page for section text
function detectMatchedPage(sectionText, documentData) {
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
}

export default detectMatchedPage;
