// src/components/api.js
import axios from "axios";

const API_BASE = "http://127.0.0.1:8001";

export const fetchBackendContent = async () => {
    const res = await axios.get(`${API_BASE}/backend-content`);
    return res.data; // { guidelines, paragraph }
};

export const validateParagraph = async (guidelines, paragraph, sessionId, entryId) => {
    const res = await axios.post(`${API_BASE}/validate`, {
        guidelines,
        paragraph,
        session_id: sessionId,
        entry_id: entryId
    });
    return res.data; // { raw, violated, highlighted_html, saved_files }
};
