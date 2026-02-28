import React, { useState, useEffect } from "react";
import axios from "axios";

const API_BASE = "http://127.0.0.1:8001";

export default function ProcessLogs({ maxItems = 10 }) {
  const [open, setOpen] = useState(false);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/log/recent?limit=${maxItems}`);
      setLogs(res.data.logs || []);
    } catch (err) {
      console.error("Failed to fetch logs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // fetch once on mount
    fetchLogs();

    // poll every 5 seconds for real-time updates
    const interval = setInterval(fetchLogs, 5000);

    return () => clearInterval(interval);
  }, []);

  const toggle = () => {
    setOpen(!open);
  };

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between">
        <button onClick={toggle} className="text-xs font-semibold text-white px-2 py-1 rounded-lg bg-slate-600 hover:bg-slate-500">
          Process Logs {logs.length > 0 && <span className="ml-2 text-[11px] text-slate-300">({logs.length})</span>}
        </button>
        <button onClick={fetchLogs} disabled={loading} className="text-xs text-slate-300 hover:text-white underline">
          Refresh
        </button>
      </div>

      {open && (
        <div className="mt-2 p-2 rounded-lg max-h-48 overflow-auto text-xs" style={{ backgroundColor: '#192334', border: '1px solid #374151' }}>
          {loading && <div className="text-sm text-slate-300">Loading...</div>}
          {!loading && logs.length === 0 && <div className="text-slate-300">No recent important logs.</div>}
          <ul className="space-y-2">
            {logs.map((l, idx) => (
              <li key={idx} className="flex flex-col">
                <div className="flex items-center justify-between">
                  <div className="font-medium text-white">{l.event_type}</div>
                  <div className="text-[11px] text-slate-300">{new Date(l.timestamp).toLocaleString()}</div>
                </div>
                <pre className="mt-1 text-[12px] text-slate-200 rounded p-2 whitespace-pre-wrap" style={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}>{JSON.stringify(l.payload)}</pre>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}