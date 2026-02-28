// src/components/PdfUploader.jsx
import React, { useState } from "react";

export default function PdfUploader({ onPdfUpload, loading }) {
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      const file = files[0];
      if (file.type === "application/pdf") {
        setUploadError(null); // clear error on valid file
        const blobUrl = URL.createObjectURL(file);
        onPdfUpload({ blobUrl });
        setUploadError(null); // hide error immediately
        uploadPdf(file); // still upload to backend if needed
      } else {
        setUploadError("Please upload a PDF file");
      }
    }
  };

  const handleFileInput = (e) => {
    const files = e.target.files;
    if (files && files[0]) {
      const file = files[0];
      if (file.type === "application/pdf") {
        const blobUrl = URL.createObjectURL(file);
        onPdfUpload({ blobUrl });
        uploadPdf(file); // still upload to backend if needed
      } else {
        setUploadError("Please upload a PDF file");
      }
    }
  };

  const uploadPdf = async (file) => {
    try {
      setUploadProgress(0);
      setUploadError(null);
      
      const formData = new FormData();
      formData.append("file", file);

      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          const percentComplete = (e.loaded / e.total) * 100;
          setUploadProgress(Math.round(percentComplete));
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status === 200) {
          const response = JSON.parse(xhr.responseText);
          setUploadProgress(null);
          onPdfUpload(response);
        } else {
          try {
            const errorData = JSON.parse(xhr.responseText);
            setUploadError(errorData.error || "Upload failed. Please try again.");
          } catch {
            setUploadError("Upload failed. Please try again.");
          }
          setUploadProgress(null);
        }
      });

      xhr.addEventListener("error", () => {
        setUploadError("Upload error. Please check your connection.");
        setUploadProgress(null);
      });

      xhr.open("POST", "http://127.0.0.1:8001/api/pdf/upload");
      xhr.send(formData);
    } catch (error) {
      console.error("Upload error:", error);
      setUploadError("Upload failed");
      setUploadProgress(null);
    }
  };

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-6 text-center transition ${
        dragActive
          ? "border-blue-500 bg-blue-50"
          : "border-slate-300 bg-slate-50"
      } ${loading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
    >
      {uploadProgress !== null ? (
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-700">
            Uploading... {uploadProgress}%
          </p>
          <div className="w-full bg-slate-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      ) : (
        <>
          <svg
            className="mx-auto h-10 w-10 text-slate-400 mb-2"
            stroke="currentColor"
            fill="none"
            viewBox="0 0 48 48"
          >
            <path
              d="M28 8H12a4 4 0 00-4 4v28a4 4 0 004 4h24a4 4 0 004-4V20m-14-8v16m0 0l4-4m-4 4l-4-4"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <p className="text-sm font-medium text-slate-700">
            Drop your PDF here or{" "}
            <label className="text-blue-600 hover:text-blue-700 cursor-pointer">
              click to browse
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileInput}
                className="hidden"
                disabled={loading}
              />
            </label>
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Maximum file size: 50MB
          </p>
        </>
      )}
      
      {uploadError && (
        <div className="mt-3 p-2 bg-red-100 border border-red-300 rounded text-red-700 text-xs">
          {uploadError}
        </div>
      )}
    </div>
  );
}