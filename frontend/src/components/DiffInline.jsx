// src/components/DiffInline.jsx
import React, { useState, useEffect } from "react";
import { logEvent } from "../log";

/**
 * DiffInline
 * Renders inline red/green diffs with Accept / Reject per change.
 *
 * Expects diffSegments like:
 *  {
 *    op: "equal" | "delete" | "replace" | "insert",
 *    orig: string,
 *    suggested: string
 *  }
 */
export default function DiffInline({ diffSegments = [], onTextChange }) {
  // state stores accepted/rejected/pending for each diff segment
  const [states, setStates] = useState([]);

  // Reset states whenever new diffSegments arrive (new LLM answer)
  useEffect(() => {
    setStates(
      diffSegments.map((seg) =>
        seg.op === "equal" ? "accepted" : "pending"
      )
    );
  }, [diffSegments]);

  // Build the current "final text" based on states and send upwards
  useEffect(() => {
    if (!onTextChange || !diffSegments.length) return;

    let finalText = "";

    diffSegments.forEach((seg, idx) => {
      const st = states[idx];

      switch (seg.op) {
        case "equal":
          finalText += seg.orig || "";
          break;

        case "delete":
          // accepted => delete (skip text)
          // rejected or pending => keep original
          if (st === "rejected" || st === "pending") {
            finalText += seg.orig || "";
          }
          break;

        case "replace":
          // accepted => use suggested
          // rejected or pending => keep original
          if (st === "accepted") {
            finalText += seg.suggested || "";
          } else {
            finalText += seg.orig || "";
          }
          break;

        case "insert":
          // accepted => add suggested
          // rejected/pending => nothing
          if (st === "accepted") {
            finalText += seg.suggested || "";
          }
          break;

        default:
          // safety: if unknown op, just keep original
          finalText += seg.orig || "";
      }
    });

    onTextChange(finalText);
  }, [states, diffSegments, onTextChange]);

  const updateState = (idx, newState, seg, actionType) => {
    // optional: log accept / reject per segment
    if (actionType === "accept") {
      logEvent("diff_accept", {
        op: seg.op,
        original: seg.orig,
        suggested: seg.suggested,
        index: idx,
      });
    } else if (actionType === "reject") {
      logEvent("diff_reject", {
        op: seg.op,
        original: seg.orig,
        suggested: seg.suggested,
        index: idx,
      });
    }

    setStates((prev) => {
      const next = [...prev];
      next[idx] = newState;
      return next;
    });
  };

  return (
    <span>
      {diffSegments.map((seg, idx) => {
        const st = states[idx];

        // EQUAL → plain text
        if (seg.op === "equal") {
          return (
            <span key={idx} className="text-slate-800">
              {seg.orig}
            </span>
          );
        }

        // DELETE
        if (seg.op === "delete") {
          if (st === "accepted") {
            // deletion applied => nothing shown
            return null;
          }
          if (st === "rejected") {
            // show as normal text
            return (
              <span key={idx} className="text-slate-800">
                {seg.orig}
              </span>
            );
          }
          // pending => show red strikethrough with controls
          return (
            <span
              key={idx}
              className="inline-flex items-center gap-1 bg-red-100 text-red-700 line-through rounded px-0.5"
            >
              <span>{seg.orig}</span>
              <button
                type="button"
                onClick={() =>
                  updateState(idx, "accepted", seg, "accept")
                }
                className="text-xs hover:text-green-700"
                title="Accept delete"
              >
                ✓
              </button>
              <button
                type="button"
                onClick={() =>
                  updateState(idx, "rejected", seg, "reject")
                }
                className="text-xs hover:text-slate-700"
                title="Reject delete"
              >
                ✕
              </button>
            </span>
          );
        }

        // REPLACE
        if (seg.op === "replace") {
          if (st === "accepted") {
            // show new text as normal
            return (
              <span key={idx} className="text-slate-800">
                {seg.suggested}
              </span>
            );
          }
          if (st === "rejected") {
            // show original as normal
            return (
              <span key={idx} className="text-slate-800">
                {seg.orig}
              </span>
            );
          }
          // pending => show orig red, new green, with controls
          return (
            <span key={idx} className="inline-flex items-center gap-1">
              <span className="bg-red-100 text-red-700 line-through rounded px-0.5">
                {seg.orig}
              </span>
              <span className="bg-green-100 text-green-700 rounded px-0.5">
                {seg.suggested}
              </span>
              <button
                type="button"
                onClick={() =>
                  updateState(idx, "accepted", seg, "accept")
                }
                className="text-xs text-green-700 hover:text-green-900"
                title="Apply change"
              >
                ✓
              </button>
              <button
                type="button"
                onClick={() =>
                  updateState(idx, "rejected", seg, "reject")
                }
                className="text-xs text-slate-700 hover:text-slate-900"
                title="Reject change"
              >
                ✕
              </button>
            </span>
          );
        }

        // INSERT (text exists only in suggested)
        if (seg.op === "insert") {
          if (st === "accepted") {
            return (
              <span key={idx} className="text-slate-800">
                {seg.suggested}
              </span>
            );
          }
          if (st === "rejected") {
            // rejected insert → show nothing
            return null;
          }
          // pending => show green inserted text with controls
          return (
            <span
              key={idx}
              className="inline-flex items-center gap-1 bg-green-100 text-green-700 rounded px-0.5"
            >
              <span>{seg.suggested}</span>
              <button
                type="button"
                onClick={() =>
                  updateState(idx, "accepted", seg, "accept")
                }
                className="text-xs hover:text-green-900"
                title="Accept insert"
              >
                ✓
              </button>
              <button
                type="button"
                onClick={() =>
                  updateState(idx, "rejected", seg, "reject")
                }
                className="text-xs hover:text-slate-900"
                title="Reject insert"
              >
                ✕
              </button>
            </span>
          );
        }

        // fallback: unknown op → render original
        return (
          <span key={idx} className="text-slate-800">
            {seg.orig}
          </span>
        );
      })}
    </span>
  );
}
