import React, { useState } from 'react';
import axios from 'axios';
import './PdfUploadComponent.css';


const API_BASE = "http://127.0.0.1:8001";

const PdfUploadComponent = ({ onUploadSuccess, onUploadError }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const uploadFile = async (file) => {
    // Validate file type
    if (file.type !== 'application/pdf') {
      const errorMsg = 'Please upload a PDF file';
      setError(errorMsg);
      onUploadError?.(errorMsg);
      return;
    }

    // Validate file size (100MB)
    if (file.size > 100 * 1024 * 1024) {
      const errorMsg = 'File is too large (max 100MB)';
      setError(errorMsg);
      onUploadError?.(errorMsg);
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post(`${API_BASE}/api/pdf/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        const successMsg = `PDF "${file.name}" uploaded successfully!`;
        setSuccess(successMsg);
        onUploadSuccess?.(response.data);
      } else {
        const errorMsg = response.data.error || 'Upload failed';
        setError(errorMsg);
        onUploadError?.(errorMsg);
      }
    } catch (err) {
      const errorMsg = err.response?.data?.error || err.message || 'Upload failed';
      setError(errorMsg);
      onUploadError?.(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  };

  const handleFileInput = (e) => {
    const files = e.target.files;
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  };

  return (
    <div className="pdf-upload-container">
      <div className="pdf-upload-wrapper">
        <div
          className={`pdf-upload-area ${isDragging ? 'dragging' : ''} ${isLoading ? 'loading' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <div className="upload-content">
            <div className="upload-icon-wrapper">
              <svg className="upload-icon-svg" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            
            <div className="upload-text-content">
              <h2 className="upload-title">Upload a PDF Document</h2>
              <p className="upload-description">
                Drag and drop your PDF here, or click to select a file
              </p>
            </div>
            
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileInput}
              disabled={isLoading}
              className="file-input"
              id="pdf-file-input"
            />
            <label htmlFor="pdf-file-input" className="browse-button">
              {isLoading ? (
                <>
                  <svg className="button-icon spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <svg className="button-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>Browse Files</span>
                </>
              )}
            </label>
            
            <p className="file-info">
              <svg className="info-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Maximum file size: 100MB | Format: PDF only
            </p>
          </div>
        </div>

        {error && (
          <div className="alert alert-error">
            <span className="alert-icon-emoji">❌</span>
            <div className="alert-content">
              <span className="alert-title">Upload Failed</span>
              <span className="alert-message">{error}</span>
            </div>
          </div>
        )}

        {success && (
          <div className="alert alert-success">
            <span className="alert-icon-emoji">✅</span>
            <div className="alert-content">
              <span className="alert-title">Success!</span>
              <span className="alert-message">{success}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PdfUploadComponent;
