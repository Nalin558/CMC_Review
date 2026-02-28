import React, { useState, useEffect } from "react";
import { validateParagraph } from "./api";

export default function GuidelineValidator({ onBack, initialGuidelines, initialParagraph, sessionId, entryId, onValidationStatusChange }) {
    const [guidelines, setGuidelines] = useState(initialGuidelines || "");
    const [paragraph, setParagraph] = useState(initialParagraph || "");
    const [highlightedHtml, setHighlightedHtml] = useState("");
    const [violatedRules, setViolatedRules] = useState("");
    const [reasoning, setReasoning] = useState("");
    const [loading, setLoading] = useState(false);
    const [missingGuidelines, setMissingGuidelines] = useState("");
    const [showMissingInput, setShowMissingInput] = useState(false);
    const [addedMissingGuidelines, setAddedMissingGuidelines] = useState("");
    
    // Store original validation results
    const [originalViolatedRules, setOriginalViolatedRules] = useState("");
    const [originalReasoning, setOriginalReasoning] = useState("");
    const [originalHighlightedHtml, setOriginalHighlightedHtml] = useState("");
    const [hasMissingAdded, setHasMissingAdded] = useState(false);

    useEffect(() => {
        if (initialGuidelines) setGuidelines(initialGuidelines);
        if (initialParagraph) setParagraph(initialParagraph);
    }, [initialGuidelines, initialParagraph]);

    const handleValidate = async () => {
        // Client-side guard: don't call backend if inputs are empty
        if (!guidelines || !guidelines.trim() || !paragraph || !paragraph.trim()) {
            alert("Please provide both Guidelines and the Updated Paragraph before validating.");
            return;
        }

        console.log("Validating with:", { 
            guidelinesLength: guidelines.length, 
            paragraphLength: paragraph.length,
            sessionId,
            entryId
        });

        setLoading(true);
        try {
            const res = await validateParagraph(guidelines, paragraph, sessionId, entryId);
            console.log("Validation response:", res);
            setHighlightedHtml(res.highlighted_html);
            setViolatedRules(res.violated);
            setReasoning(res.reasoning);
            
            // Store as original results (will be preserved when missing guidelines are added)
            if (!hasMissingAdded) {
                setOriginalViolatedRules(res.violated);
                setOriginalReasoning(res.reasoning);
                setOriginalHighlightedHtml(res.highlighted_html);
            }

            // Normalize for various 'none' outputs (e.g., '- None', 'none', '', etc.)
            let violated = (res.violated || '').trim().toLowerCase();
            // Remove leading dash and whitespace if present
            if (violated.startsWith('-')) violated = violated.slice(1).trim();
            const isValid = violated === 'none' || violated === '';
            if (onValidationStatusChange) {
                onValidationStatusChange(isValid ? "none" : "violations");
            }
        } catch (err) {
            console.error("Validation error:", err);
            alert("Validation failed: " + (err.response?.data?.error || err.message));
            if (onValidationStatusChange) {
                onValidationStatusChange(null);
            }
        } finally {
            setLoading(false);
        }
    };

    const handleAddMissingGuidelines = async () => {
        if (!missingGuidelines || !missingGuidelines.trim()) {
            alert("Please enter the missing violated guidelines.");
            return;
        }

        setLoading(true);
        try {
            // Store the missing guidelines being added
            const missingToAdd = missingGuidelines.trim();
            
            // Combine original guidelines with missing guidelines
            const combinedGuidelines = guidelines + "\n\n--- Additional Guidelines to Check ---\n" + missingToAdd;
            
            console.log("Re-validating with combined guidelines:", {
                originalLength: guidelines.length,
                missingLength: missingToAdd.length,
                combinedLength: combinedGuidelines.length
            });
            
            // Re-validate with combined guidelines
            const res = await validateParagraph(combinedGuidelines, paragraph, sessionId, entryId);
            
            console.log("Re-validation response:", res);
            
            // Update results (keep original separate)
            setHighlightedHtml(res.highlighted_html);
            setViolatedRules(res.violated);
            setReasoning(res.reasoning);
            
            // Mark that missing guidelines have been added
            setHasMissingAdded(true);
            
            // Update guidelines to include the missing ones
            setGuidelines(combinedGuidelines);
            
            // Track what was added for Dashboard display
            setAddedMissingGuidelines(prev => 
                prev ? prev + "\n\n" + missingToAdd : missingToAdd
            );
            
            // Clear and hide the missing guidelines input
            setMissingGuidelines("");
            setShowMissingInput(false);
        } catch (err) {
            console.error("Re-validation error:", err);
            alert("Re-validation failed: " + (err.response?.data?.error || err.message));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex-1 flex flex-col bg-slate-900 overflow-hidden">
            {/* Header */}
            <div className="px-6 py-5 border-b border-indigo-500/30 bg-gradient-to-r from-indigo-950 via-purple-950 to-indigo-950 shadow-2xl">
                <div className="flex items-center justify-between">
                    <span className="text-2xl font-black uppercase tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-violet-300 via-purple-300 to-fuchsia-300 drop-shadow-lg">
                        ✓ GUIDELINE VALIDATOR
                    </span>
                    <button
                        onClick={onBack}
                        className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold rounded-xl hover:from-indigo-500 hover:to-purple-500 shadow-xl hover:shadow-purple-500/60 transition-all duration-200 transform hover:scale-105 active:scale-95"
                    >
                        ← Back to Review
                    </button>
                </div>
            </div>

            <div className="flex-1 flex flex-col p-6 gap-6 overflow-auto bg-gradient-to-b from-slate-900 via-indigo-950/20 to-slate-900">
                <div>
                    <label className="text-sm font-bold text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-purple-400 mb-3 block uppercase tracking-wide">📋 Guidelines to Check Against:</label>
                    <textarea
                        className="w-full text-sm rounded-xl border-2 border-violet-500/50 bg-slate-800/70 backdrop-blur-sm text-slate-100 p-4 placeholder:text-slate-500 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/40 transition-all shadow-lg hover:shadow-violet-500/30"
                        rows="4"
                        placeholder="Guidelines will appear here..."
                        value={guidelines}
                        onChange={(e) => setGuidelines(e.target.value)}
                    />
                </div>
                <div>
                    <label className="text-sm font-bold text-transparent bg-clip-text bg-gradient-to-r from-fuchsia-400 to-pink-400 mb-3 block uppercase tracking-wide">✏️ Updated Paragraph (AI Rewrite):</label>
                    <textarea
                        className="w-full text-sm rounded-xl border-2 border-fuchsia-500/50 bg-slate-800/70 backdrop-blur-sm text-slate-100 p-4 placeholder:text-slate-500 focus:border-fuchsia-400 focus:outline-none focus:ring-2 focus:ring-fuchsia-400/40 transition-all shadow-lg hover:shadow-fuchsia-500/30"
                        rows="4"
                        value={paragraph}
                        onChange={(e) => setParagraph(e.target.value)}
                    />
                </div>

                <button
                    onClick={handleValidate}
                    disabled={loading || !guidelines.trim() || !paragraph.trim()}
                    className="px-6 py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-xl font-bold hover:from-violet-500 hover:to-fuchsia-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-xl hover:shadow-fuchsia-500/60 transform hover:scale-105 active:scale-95 text-base uppercase tracking-wide"
                    title={!guidelines.trim() || !paragraph.trim() ? "Provide both Guidelines and Paragraph" : undefined}
                >
                    {loading ? "⏳ Validating..." : "▶ Validate"}
                </button>

            {/* ORIGINAL VALIDATION RESULTS (shown when missing guidelines added) */}
            {hasMissingAdded && originalViolatedRules && (
                <div className="mt-4 p-6 bg-gradient-to-br from-slate-800/60 to-slate-800/30 backdrop-blur-xl border-2 border-indigo-500/60 rounded-2xl shadow-2xl">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="text-3xl">🔹</span>
                        <h3 className="font-bold text-indigo-300 text-lg uppercase tracking-wider">Original LLM Results</h3>
                    </div>
                    
                    <div className="space-y-4">
                        <div>
                            <h4 className="font-bold text-indigo-200 text-sm mb-2 uppercase">Violated Guidelines:</h4>
                            <pre className="bg-slate-900/80 border-2 border-indigo-500/40 p-4 rounded-xl whitespace-pre-wrap text-sm text-indigo-100 font-mono">{originalViolatedRules}</pre>
                        </div>
                        
                        {originalReasoning && (
                            <div>
                                <h4 className="font-bold text-indigo-200 text-sm mb-2 uppercase">Reasoning:</h4>
                                <div className="bg-slate-900/80 border-2 border-indigo-500/40 p-4 rounded-xl text-sm text-indigo-100 whitespace-pre-wrap">
                                    {originalReasoning}
                                </div>
                            </div>
                        )}
                        
                        {originalHighlightedHtml && (
                            <div>
                                <h4 className="font-bold text-indigo-200 text-sm mb-2 uppercase">Highlighted Paragraph:</h4>
                                <div
                                    className="bg-slate-900/80 border-2 border-indigo-500/40 p-4 rounded-xl text-sm text-indigo-100"
                                    dangerouslySetInnerHTML={{ __html: originalHighlightedHtml }}
                                />
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* CURRENT VALIDATION RESULTS */}
            {violatedRules && (
                <div className={`mt-4 ${hasMissingAdded ? 'p-6 bg-gradient-to-br from-slate-800/60 to-slate-800/30 backdrop-blur-xl border-2 border-emerald-500/60 rounded-2xl shadow-2xl' : 'p-6 bg-gradient-to-br from-slate-800/60 to-slate-800/30 backdrop-blur-xl border-2 border-rose-500/60 rounded-2xl shadow-2xl'}`}>
                    {hasMissingAdded && (
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-3xl">✨</span>
                            <h3 className="font-bold text-emerald-300 text-lg uppercase tracking-wider">After Adding Missing Guidelines</h3>
                        </div>
                    )}
                    
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <h3 className={`font-bold text-lg uppercase tracking-wider ${hasMissingAdded ? 'text-emerald-300' : 'text-rose-300'}`}>
                                {hasMissingAdded ? '✓ Updated Results:' : '⚠ Violations Detected:'}
                            </h3>
                            {!hasMissingAdded && (
                                <button
                                    onClick={() => setShowMissingInput(!showMissingInput)}
                                    className="text-sm px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg hover:from-indigo-500 hover:to-purple-500 transition-all shadow-lg hover:shadow-purple-500/60 font-semibold transform hover:scale-105 active:scale-95"
                                >
                                    {showMissingInput ? "✕ Cancel" : "+ Add Custom Guidelines"}
                                </button>
                            )}
                        </div>
                        <pre className={`p-4 rounded-xl whitespace-pre-wrap text-sm font-mono ${hasMissingAdded ? 'bg-slate-900/80 border-2 border-emerald-500/40 text-emerald-100' : 'bg-slate-900/80 border-2 border-rose-500/40 text-rose-100'}`}>{violatedRules}</pre>
                    </div>
                    
                    {showMissingInput && (
                        <div className="mt-4 p-5 bg-slate-900/60 border-2 border-purple-500/50 rounded-xl">
                            <label className="text-sm font-bold text-purple-300 mb-3 block uppercase">
                                ➕ Add Missing Violated Guidelines:
                            </label>
                            <textarea
                                className="w-full border-2 border-purple-500/40 p-3 rounded-lg mb-3 text-sm bg-slate-800 text-slate-100 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none"
                                rows="4"
                                placeholder="Enter additional guidelines that were violated but not detected..."
                                value={missingGuidelines}
                                onChange={(e) => setMissingGuidelines(e.target.value)}
                            />
                            <div className="flex gap-3">
                                <button
                                    onClick={handleAddMissingGuidelines}
                                    disabled={loading || !missingGuidelines.trim()}
                                    className="flex-1 px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-bold hover:from-violet-500 hover:to-fuchsia-500 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-fuchsia-500/60 transform hover:scale-105 active:scale-95 uppercase tracking-wide"
                                >
                                    {loading ? "⏳ Re-validating..." : "▶ Re-validate with Missing Guidelines"}
                                </button>
                                <button
                                    onClick={() => {
                                        setShowMissingInput(false);
                                        setMissingGuidelines("");
                                    }}
                                    className="px-4 py-2 bg-slate-700/60 text-slate-300 rounded-lg text-sm hover:bg-slate-600/60 border-2 border-slate-600/50 font-semibold transition-all"
                                >
                                    Cancel
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* UPDATED AI REASONING (after missing guidelines) */}
            {hasMissingAdded && reasoning && (
                <div className="mt-4 p-6 bg-gradient-to-br from-slate-800/60 to-slate-800/30 backdrop-blur-xl border-2 border-violet-500/60 rounded-2xl shadow-2xl">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="text-2xl">📝</span>
                        <h3 className="font-bold text-violet-300 text-lg uppercase tracking-wider">Updated Reasoning:</h3>
                    </div>
                    <div className="bg-slate-900/80 border-2 border-violet-500/40 p-4 rounded-xl text-sm text-violet-100 whitespace-pre-wrap">
                        {reasoning}
                    </div>
                </div>
            )}

            {/* ORIGINAL AI REASONING (when no missing guidelines) */}
            {!hasMissingAdded && reasoning && (
                <div className="mt-4 p-6 bg-gradient-to-br from-slate-800/60 to-slate-800/30 backdrop-blur-xl border-2 border-fuchsia-500/60 rounded-2xl shadow-2xl">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="text-2xl">📝</span>
                        <h3 className="font-bold text-fuchsia-300 text-lg uppercase tracking-wider">AI Reasoning:</h3>
                    </div>
                    <div className="bg-slate-900/80 border-2 border-fuchsia-500/40 p-4 rounded-xl text-sm text-fuchsia-100 whitespace-pre-wrap">
                        {reasoning}
                    </div>
                </div>
            )}

            {/* UPDATED HIGHLIGHTED PARAGRAPH (after missing guidelines) */}
            {hasMissingAdded && highlightedHtml && (
                <div className="mt-4 p-6 bg-gradient-to-br from-slate-800/60 to-slate-800/30 backdrop-blur-xl border-2 border-cyan-500/60 rounded-2xl shadow-2xl">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="text-2xl">📄</span>
                        <h3 className="font-bold text-cyan-300 text-lg uppercase tracking-wider">Updated Paragraph:</h3>
                    </div>
                    <div
                        className="bg-slate-900/80 border-2 border-cyan-500/40 p-4 rounded-xl text-sm text-cyan-100"
                        dangerouslySetInnerHTML={{ __html: highlightedHtml }}
                    />
                </div>
            )}

            {/* ORIGINAL HIGHLIGHTED PARAGRAPH (when no missing guidelines) */}
            {!hasMissingAdded && highlightedHtml && (
                <div className="mt-4 p-6 bg-gradient-to-br from-slate-800/60 to-slate-800/30 backdrop-blur-xl border-2 border-pink-500/60 rounded-2xl shadow-2xl">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="text-2xl">📄</span>
                        <h3 className="font-bold text-pink-300 text-lg uppercase tracking-wider">Highlighted Paragraph:</h3>
                    </div>
                    <div
                        className="bg-slate-900/80 border-2 border-pink-500/40 p-4 rounded-xl text-sm text-pink-100"
                        dangerouslySetInnerHTML={{ __html: highlightedHtml }}
                    />
                </div>
            )}
            </div>
        </div>
    );
}
