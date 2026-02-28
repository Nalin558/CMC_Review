import React from "react";
import DiffSideBySide from "./DiffSideBySide";

export default function DiffViewer({ result }) {
  if (!result) {
    return (
      <div className="p-4 text-gray-500">
        AI suggestion will appear here after submitting a comment.
      </div>
    );
  }

  return (
    <div className="p-4 overflow-y-auto">
      <h2 className="text-xl font-semibold mb-3">AI Suggested Correction</h2>

      <div className="mb-4">
        <h3 className="font-semibold">Short Answer</h3>
        <p className="text-gray-800 bg-gray-50 p-2 rounded">
          {result.short_answer}
        </p>
      </div>

      <div className="mb-4">
        <h3 className="font-semibold">Detailed Answer</h3>
        <p className="text-gray-800 bg-gray-50 p-2 rounded">
          {result.detailed_answer}
        </p>
      </div>

      <div className="mb-4">
        <h3 className="font-semibold">Suggested Rewrite</h3>
        <pre className="whitespace-pre-wrap bg-gray-50 p-2 rounded text-gray-900">
          {result.suggested_cmc_rewrite}
        </pre>
      </div>

      <div>
        <h3 className="font-semibold">Diff</h3>
        <div className="text-sm mt-2">
          {/* Prefer structured diff if present (word-level tokens). Otherwise fall back to legacy segments */}
          {result.structured_diff && result.structured_diff.blocks ? (
            <div>
              {/* Side-by-side structured diff */}
              <DiffSideBySide structured={result.structured_diff} />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2 bg-slate-800 p-3 rounded-lg">
              <div className="text-xs text-gray-300 font-semibold">Original</div>
              <div className="text-xs text-gray-300 font-semibold">Suggested</div>

              {result.diff_segments.map((diff, idx) => {
                if (diff.op === "delete") {
                  return (
                    <React.Fragment key={idx}>
                      <div className="bg-red-600 text-red-100 p-2 rounded text-sm font-semibold">{diff.orig}</div>
                      <div className="p-2 text-sm text-gray-400">&nbsp;</div>
                    </React.Fragment>
                  );
                }

                if (diff.op === "insert") {
                  return (
                    <React.Fragment key={idx}>
                      <div className="p-2 text-sm text-gray-400">&nbsp;</div>
                      <div className="bg-green-600 text-green-100 p-2 rounded text-sm font-semibold">{diff.suggested}</div>
                    </React.Fragment>
                  );
                }

                if (diff.op === "replace") {
                  return (
                    <React.Fragment key={idx}>
                      <div className="bg-red-600 text-red-100 p-2 rounded text-sm font-semibold">{diff.orig}</div>
                      <div className="bg-green-600 text-green-100 p-2 rounded text-sm font-semibold">{diff.suggested}</div>
                    </React.Fragment>
                  );
                }

                // equal
                return (
                  <React.Fragment key={idx}>
                    <div className="p-2 text-sm text-gray-300">{diff.orig}</div>
                    <div className="p-2 text-sm text-gray-300">{diff.orig}</div>
                  </React.Fragment>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
