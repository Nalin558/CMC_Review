import React, { useRef } from "react";
import { jsPDF } from "jspdf";

/* ---------------- REPORT GENERATOR (SIMPLIFIED) ---------------- */

function ReportGenerator({ onGenerate }) {
    const statusCard = (label, sub) => (
        <div className="p-4 rounded-xl text-center shadow-sm transition
                        bg-gradient-to-br from-emerald-400 to-sky-400 text-slate-900">
            <div className="text-2xl font-bold">✅</div>
            <div className="mt-1 text-sm font-semibold">{label}</div>
            {sub && <div className="text-xs mt-1">{sub}</div>}
        </div>
    );

    return (
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-blue-200 card-glow fade-in-up">
            <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wide mb-4">
                ✅ Ready to generate updated CMC PDF
            </h3>

            {/* STATUS CARDS (ALWAYS READY) */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                {statusCard("Guidelines Ready")}
                {statusCard("Paragraphs Loaded")}
                {statusCard("Impact PDF Ready")}
            </div>

            {/* READY BANNER (ALWAYS GREEN) */}
            <div className="mb-4 p-3 rounded-xl border text-center font-semibold
                            bg-emerald-50 border-emerald-300 text-emerald-700">
                ✅ Ready to generate updated CMC PDF
            </div>

            {/* ACTION */}
            <button
                disabled
                title="UI only"
                className="w-full py-3 rounded-xl font-semibold transition
                           bg-gradient-to-r from-blue-600 to-blue-500
                           text-white opacity-70 cursor-not-allowed"
            >
                ✅ Ready to generate updated CMC PDF
            </button>

            <div className="mt-4 text-xs text-slate-500 text-center">
                💡 Generates an updated CMC PDF (result.pdf)
            </div>
        </div>
    );
}

/* ---------------- MAIN DASHBOARD ---------------- */

export default function Dashboard({ onBack, data = {} }) {
    const contentRef = useRef(null);

    const {
        comment,
        originalText,
        rewrite,
        guidelines,
        violatedRules,
        reasoning
    } = data;

    const hasViolations = Boolean(violatedRules && violatedRules.length);
    const statusLabel = hasViolations ? "Review required" : "All good";

    const handleDownloadCMC = async () => {
        const tryUrl = '/cmc/document/download-pdf';
        const backendDirectUrl = `${window.location.protocol}//${window.location.hostname}:8002/cmc/document/download-pdf`;

        const fetchAndRead = async (url) => {
            const r = await fetch(url);
            const contentType = r.headers.get('content-type') || '';
            const text = await r.text().catch(() => '');
            return { r, contentType, text };
        };

        try {
            let { r, contentType, text } = await fetchAndRead(tryUrl);

            const looksLikeHtml = contentType.includes('text/html') || (text && text.trim().startsWith('<!DOCTYPE'));
            if (looksLikeHtml) {
                ({ r, contentType, text } = await fetchAndRead(backendDirectUrl));
            }

            if (!r.ok) {
                let parsedErr = null;
                try { parsedErr = JSON.parse(text); } catch (_) { parsedErr = null; }
                const msg = (parsedErr && parsedErr.error) || text || 'CMC PDF not available';
                alert(msg);
                return;
            }

            // If response is HTML, give up
            if (contentType.includes('text/html') || (text && text.trim().startsWith('<!DOCTYPE'))) {
                alert('Unexpected HTML returned from server — check the backend is running on port 8002 and CORS is enabled.');
                return;
            }

            // Read blob properly from the successful response
            const blob = await (await fetch(r.url)).blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'cmc_original.pdf';
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Failed to download CMC PDF', err);
            alert('Download failed — make sure backend is running on port 8002 and CORS is enabled');
        }
    };

    // Download the result JSON and export it as a structured PDF
    const handleDownloadReport = async () => {
        const tryUrl = "/cmc/results/download";
        const backendDirectUrl = `${window.location.protocol}//${window.location.hostname}:5000/cmc/results/download`;

        const fetchAndReadText = async (url) => {
            try {
                const r = await fetch(url, { mode: 'cors', cache: 'no-cache', headers: { 'Accept': 'application/json' } });
                const contentType = r.headers.get('content-type') || '';
                const text = await r.text().catch(() => "");
                return { r, contentType, text };
            } catch (err) {
                console.warn('fetch failed for', url, err);
                return { r: null, contentType: '', text: '', error: err };
            }
        };

        try {
            let { r, contentType, text, error } = await fetchAndReadText(tryUrl);
            const looksLikeHtml = (r && contentType.includes('text/html')) || (text && text.trim().startsWith('<!DOCTYPE'));
            if (!r || looksLikeHtml) ({ r, contentType, text, error } = await fetchAndReadText(backendDirectUrl));

            // If fetch failed entirely, fall back to direct navigation (initiates download)
            if (!r) {
                console.warn('Fetch failed or blocked; opening backend URL to trigger download');
                const a = document.createElement('a');
                a.href = backendDirectUrl;
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
                document.body.appendChild(a);
                a.click();
                a.remove();
                return;
            }

            if (!r.ok) {
                let parsedErr = null;
                try { parsedErr = JSON.parse(text); } catch (_) { parsedErr = null; }
                const msg = (parsedErr && parsedErr.error) || text || 'No results available for download';
                alert(msg);
                return;
            }

            if (contentType.includes('text/html') || (text && text.trim().startsWith('<!DOCTYPE'))) {
                // final fallback: open direct backend URL to trigger download
                const a = document.createElement('a');
                a.href = backendDirectUrl;
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
                document.body.appendChild(a);
                a.click();
                a.remove();
                return;
            }

            // Parse JSON and normalize entries (support arrays, results arrays, or session-keyed objects)
            let parsed = null;
            try {
                parsed = JSON.parse(text);
            } catch (e) {
                alert('Result JSON invalid or empty');
                return;
            }

            // Flatten entries
            let entries = [];
            if (Array.isArray(parsed)) {
                entries = parsed;
            } else if (Array.isArray(parsed.results)) {
                entries = parsed.results;
            } else if (parsed && typeof parsed === 'object') {
                const vals = Object.values(parsed);
                if (vals.length && vals.every(v => Array.isArray(v))) entries = vals.flat();
                else entries = [parsed];
            }

            // Create a styled PDF report
            const doc = new jsPDF({ unit: "mm", format: "a4" });
            const pageW = doc.internal.pageSize.getWidth();
            const margin = 12;
            const maxWidth = pageW - margin * 2;
            const lineH = 6;

            const addHeader = (title) => {
                doc.setFillColor(24, 90, 219);
                doc.setDrawColor(24, 90, 219);
                doc.rect(0, 0, pageW, 18, 'F');
                doc.setFontSize(14);
                doc.setTextColor(255,255,255);
                doc.text(title, margin, 12);
                doc.setTextColor(0,0,0);
            };

            addHeader("Impact Analysis - Report");
            doc.setFontSize(12);
            let y = 30;
            doc.text(`Entries: ${entries.length}`, margin, y); y += lineH;
            doc.text(`Generated: ${new Date().toLocaleString()}`, margin, y); y += lineH * 1.5;

            const writeEntry = (entry, idx) => {
                doc.setFontSize(11);
                doc.setFont(undefined, 'bold');
                doc.text(`Entry ${idx + 1}${entry.entry_id ? ' — ' + entry.entry_id : ''}`, margin, y); y += lineH;
                doc.setFont(undefined, 'normal');

                if (entry.comment) {
                    const cLines = doc.splitTextToSize(`Comment: ${entry.comment}`, maxWidth);
                    cLines.forEach(ln => { if (y > doc.internal.pageSize.getHeight() - 20) { doc.addPage(); y = 20; } doc.text(ln, margin, y); y += lineH; });
                    y += 2;
                }

                if (entry.short_answer) {
                    doc.setFont(undefined, 'italic');
                    const sLines = doc.splitTextToSize(`Summary: ${entry.short_answer}`, maxWidth);
                    sLines.forEach(ln => { if (y > doc.internal.pageSize.getHeight() - 20) { doc.addPage(); y = 20; } doc.text(ln, margin, y); y += lineH; });
                    doc.setFont(undefined, 'normal');
                    y += 2;
                }

                if (entry.suggested_cmc_rewrite) {
                    doc.setFontSize(10);
                    doc.setFont(undefined, 'bold');
                    doc.text('Suggested Rewrite:', margin, y); y += lineH;
                    doc.setFont(undefined, 'normal');
                    const rLines = doc.splitTextToSize(entry.suggested_cmc_rewrite, maxWidth);
                    rLines.forEach(ln => { if (y > doc.internal.pageSize.getHeight() - 20) { doc.addPage(); y = 20; } doc.text(ln, margin, y); y += lineH; });
                    y += 4;
                    doc.setFontSize(11);
                }

                if (entry.diff_segments && entry.diff_segments.length > 0) {
                    doc.setFont(undefined, 'bold');
                    doc.text('Diff:', margin, y); y += lineH;
                    doc.setFont(undefined, 'normal');
                    entry.diff_segments.forEach(seg => {
                        if (seg.op === 'delete') {
                            doc.setTextColor(200, 40, 40);
                            const dLines = doc.splitTextToSize(`- ${seg.orig}`, maxWidth);
                            dLines.forEach(ln => { if (y > doc.internal.pageSize.getHeight() - 20) { doc.addPage(); y = 20; } doc.text(ln, margin + 4, y); y += lineH; });
                            doc.setTextColor(0,0,0);
                        } else if (seg.op === 'insert') {
                            doc.setTextColor(20, 120, 40);
                            const iLines = doc.splitTextToSize(`+ ${seg.suggested}`, maxWidth);
                            iLines.forEach(ln => { if (y > doc.internal.pageSize.getHeight() - 20) { doc.addPage(); y = 20; } doc.text(ln, margin + 4, y); y += lineH; });
                            doc.setTextColor(0,0,0);
                        } else if (seg.op === 'replace') {
                            doc.setTextColor(200, 40, 40);
                            const dLines = doc.splitTextToSize(`- ${seg.orig}`, maxWidth);
                            dLines.forEach(ln => { if (y > doc.internal.pageSize.getHeight() - 20) { doc.addPage(); y = 20; } doc.text(ln, margin + 4, y); y += lineH; });
                            doc.setTextColor(20, 120, 40);
                            const iLines = doc.splitTextToSize(`+ ${seg.suggested}`, maxWidth);
                            iLines.forEach(ln => { if (y > doc.internal.pageSize.getHeight() - 20) { doc.addPage(); y = 20; } doc.text(ln, margin + 4, y); y += lineH; });
                            doc.setTextColor(0,0,0);
                        } else {
                            const eLines = doc.splitTextToSize(seg.orig || seg.text || '', maxWidth);
                            eLines.forEach(ln => { if (y > doc.internal.pageSize.getHeight() - 20) { doc.addPage(); y = 20; } doc.text(ln, margin + 4, y); y += lineH; });
                        }
                    });
                    y += 6;
                }

                y += 4;
                doc.setDrawColor(200, 200, 200);
                doc.line(margin, y, pageW - margin, y);
                y += 8;
            };

            entries.forEach((ent, i) => writeEntry(ent, i));
            doc.save("result_formatted.pdf");
        } catch (err) {
            console.error("Failed to create PDF from result.json", err);
            alert("Download failed — make sure backend is running on port 5000 and CORS is enabled");
        }
    };

    return (
        <div className="flex flex-col h-full bg-blue-50 overflow-hidden">
            {/* HEADER */}
            <div className="flex items-center justify-between px-6 py-3 bg-white border-b border-blue-200 shadow-sm z-10">
                <h1 className="text-xl font-bold text-slate-900">
                    Impact Analysis Dashboard
                </h1>
                <div className="flex gap-3">
                    <button
                        onClick={onBack}
                        className="px-4 py-2 text-sm text-slate-700 hover:bg-blue-100 rounded-lg"
                    >
                        Close
                    </button>

                    <button
                        onClick={handleDownloadReport}
                        className="px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-blue-500 rounded-lg shadow-md hover:shadow-lg active:scale-95 transition-all"
                    >
                        Download Report (PDF)
                    </button>

                    <button
                        onClick={handleDownloadCMC}
                        className="px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-emerald-600 to-emerald-500 rounded-lg shadow-md hover:shadow-lg active:scale-95 transition-all"
                    >
                        Download CMC PDF
                    </button>
                </div>
            </div>

            {/* CONTENT */}
            <div className="flex-1 overflow-auto p-6" ref={contentRef}>
                <div className="max-w-5xl mx-auto space-y-6">

                    {/* HERO: simplified per request */}
                    <div className="rounded-3xl p-6 bg-gradient-to-r from-indigo-500 via-pink-500 to-yellow-400 text-white shadow-lg">
                        <h2 className="text-sm uppercase font-semibold">
                            Impact Summary
                        </h2>
                    </div>

                    {/* 🔥 SIMPLIFIED REPORT GENERATOR */}
                    <ReportGenerator onGenerate={handleDownloadReport} />

                    {/* MAIN GRID */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                        {/* LEFT */}
                        <div className="space-y-6">
                            <div className="bg-white p-6 rounded-2xl border border-blue-200 card-glow fade-in-up interactive-card">
                                <h3 className="text-sm font-bold uppercase mb-3">
                                    User Comment
                                </h3>
                                <p className="italic border-l-4 border-blue-400 pl-4">
                                    "{comment || "No comment provided"}"
                                </p>
                            </div>

                            <div className="bg-white p-6 rounded-2xl border border-blue-200 card-glow fade-in-up interactive-card">
                                <h3 className="text-sm font-bold uppercase mb-3">
                                    Original CMC Text
                                </h3>
                                <div className="font-mono text-sm bg-blue-50 p-3 rounded">
                                    {originalText
                                        ? originalText.length > 300
                                            ? originalText.slice(0, 300) + "…"
                                            : originalText
                                        : "No text context"}
                                </div>
                            </div>

                            <div className="bg-white p-6 rounded-2xl border border-blue-300 card-glow fade-in-up interactive-card">
                                <h3 className="text-sm font-bold uppercase mb-3">
                                    Suggested Rewrite
                                </h3>
                                {rewrite || "No rewrite generated"}
                            </div>
                        </div>

                        {/* RIGHT */}
                        <div className="space-y-6">
                            <div className="bg-white p-6 rounded-2xl border border-blue-200 card-glow fade-in-up interactive-card">
                                <h3 className="text-sm font-bold uppercase mb-3">
                                    {hasViolations
                                        ? "Detected Violations"
                                        : "Guideline Check Passed"}
                                </h3>
                                {hasViolations
                                    ? violatedRules
                                    : "All guidelines explicitly followed."}
                            </div>

                            
<div className="bg-gradient-to-br from-blue-50 to-white p-6 rounded-2xl border border-blue-200 card-glow fade-in-up interactive-card">

                                <h3 className="text-sm font-bold uppercase mb-3">

                                    🤖 AI Reasoning

                                </h3>

                                <div className="whitespace-pre-wrap">

                                    {reasoning || "No reasoning available."}

                                </div>

                            </div>
                        </div>
                    </div>

                    {/* GUIDELINES */}
                    <div className="bg-white p-6 rounded-2xl border border-blue-200">
                        <h3 className="text-sm font-bold uppercase mb-3">
                            Evaluated Guidelines
                        </h3>
                        <pre className="text-xs whitespace-pre-wrap max-h-32 overflow-y-auto">
                            {guidelines}
                        </pre>
                    </div>

                </div>
            </div>
        </div>
    );
}
