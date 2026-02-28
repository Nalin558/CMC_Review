import React from "react";

// Renders a side-by-side diff similar to VS Code: left (Original / Deletions), right (Suggested / Insertions)
// Accepts either a structured diff (result.structured_diff.blocks) or legacy diff_segments array

function TokenSpan({ token }) {
  // token: { status: 'equal'|'delete'|'insert', html: '...' }
  if (!token) return null;
  const { status, html } = token;
  if (status === "equal") {
    return (
      <span className="px-1 text-gray-300" dangerouslySetInnerHTML={{ __html: html }} />
    );
  }
  if (status === "delete") {
    return (
      <span
        className="px-1 bg-red-600 text-red-100 line-through rounded font-semibold"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  }
  // insert
  return (
    <span
      className="px-1 bg-green-600 text-green-100 rounded font-semibold"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function LineCell({ tokens = [] }) {
  if (!tokens.length) {
    return <div className="min-h-[36px] p-2" />;
  }
  return (
    <div className="p-2 min-h-[36px] text-sm leading-5 whitespace-pre-wrap break-words">
      {tokens.map((t, i) => (
        <TokenSpan key={i} token={t} />
      ))}
    </div>
  );
}

export default function DiffSideBySide({ structured }) {
  // structured: { blocks: [ { type, old: [{status, html}], new: [...] } ] }
  if (!structured || !structured.blocks) return null;

  return (
    <div className="border rounded bg-slate-800 overflow-auto text-sm font-mono text-xs">
      <div className="grid grid-cols-2 border-b">
        <div className="p-2 font-semibold text-xs text-gray-300 border-r bg-slate-700">Original</div>
        <div className="p-2 font-semibold text-xs text-gray-300 bg-slate-700">Suggested</div>
      </div>

      <div>
        {structured.blocks.map((b, idx) => {
          const leftTokens = b.old || [];
          const rightTokens = b.new || [];

          // Determine row background based on type
          let leftBg = "";
          let rightBg = "";
          if (b.type === "delete") {
            leftBg = "bg-red-500 bg-opacity-30";
            rightBg = "bg-slate-800";
          } else if (b.type === "insert") {
            leftBg = "bg-slate-800";
            rightBg = "bg-green-500 bg-opacity-30";
          } else if (b.type === "replace") {
            leftBg = "bg-red-500 bg-opacity-30";
            rightBg = "bg-green-500 bg-opacity-30";
          } else {
            leftBg = "bg-slate-800";
            rightBg = "bg-slate-800";
          }

          return (
            <div key={idx} className="grid grid-cols-2 gap-0 border-b last:border-b-0">
              <div className={`${leftBg} border-r`}> 
                <LineCell tokens={leftTokens} />
              </div>
              <div className={`${rightBg}`}>
                <LineCell tokens={rightTokens} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
