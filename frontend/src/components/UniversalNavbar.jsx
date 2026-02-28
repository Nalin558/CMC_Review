import React, { useState, useEffect } from 'react';
import { Brain, Clock, Home, ArrowLeft } from 'lucide-react';

const UniversalNavbar = ({ 
  showHomeButton = false, 
  showBackButton = false, 
  backUrl = null,
  homeUrl = 'http://localhost:3000',
  currentPage = 'Home',
  activeModule = null, // 'home', 'create', 'update', 'review', 'back'
  showUploadButton = false,
  onUploadClick = null
}) => {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="sticky top-0 z-50 bg-slate-900/95 backdrop-blur-xl border-b border-slate-700/50 shadow-2xl">
      <div className="w-full px-5 py-2.5">
        <div className="flex items-center justify-between gap-3">
          {/* Logo and Title */}
          <div className="flex items-center gap-2.5 flex-shrink-0">
            <div className="relative">
              <div className="w-11 h-11 rounded-lg bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-purple-500/50 animate-pulse">
                <Brain className="w-6 h-6 text-white" strokeWidth={2.5} />
              </div>
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-400 rounded-full border-2 border-slate-900 animate-pulse" />
            </div>
            <div>
              <h1 className="text-xl font-black bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent tracking-tight">
                Intelli CMC Nexus
              </h1>
              <p className="text-xs text-slate-400 font-medium tracking-wide">
                {currentPage} • Enterprise Document Management Platform
              </p>
            </div>
          </div>

          {/* Center - All Buttons */}
          <div className="flex items-center gap-2.5 flex-1 justify-center">
            <a
              href="http://localhost:5173"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all duration-300 font-semibold whitespace-nowrap text-sm ${
                activeModule === 'create'
                  ? 'bg-gradient-to-r from-indigo-600 to-purple-600 border-2 border-indigo-400 text-white shadow-lg shadow-indigo-500/50'
                  : 'bg-gradient-to-r from-indigo-600/30 to-purple-600/30 hover:from-indigo-600/50 hover:to-purple-600/50 border border-indigo-500/40 hover:border-indigo-500/60 text-slate-200 hover:text-white'
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span>Create Document</span>
            </a>
            <a
              href="http://localhost:3002"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all duration-300 font-semibold whitespace-nowrap text-sm ${
                activeModule === 'update'
                  ? 'bg-gradient-to-r from-purple-600 to-pink-600 border-2 border-purple-400 text-white shadow-lg shadow-purple-500/50'
                  : 'bg-gradient-to-r from-purple-600/30 to-pink-600/30 hover:from-purple-600/50 hover:to-pink-600/50 border border-purple-500/40 hover:border-purple-500/60 text-slate-200 hover:text-white'
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Update & Refine</span>
            </a>
            <a
              href="http://localhost:3001"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all duration-300 font-semibold whitespace-nowrap text-sm ${
                activeModule === 'review'
                  ? 'bg-gradient-to-r from-green-600 to-teal-600 border-2 border-green-400 text-white shadow-lg shadow-green-500/50'
                  : 'bg-gradient-to-r from-green-600/30 to-teal-600/30 hover:from-green-600/50 hover:to-teal-600/50 border border-green-500/40 hover:border-green-500/60 text-slate-200 hover:text-white'
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Review & Approve</span>
            </a>
          </div>

          {/* Right Side - Navigation & Clock */}
          <div className="flex items-center gap-2.5 flex-shrink-0">
            {showHomeButton && (
              <button
                onClick={() => window.location.href = homeUrl}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all duration-300 font-semibold whitespace-nowrap text-sm ${
                  activeModule === 'home'
                    ? 'bg-gradient-to-r from-indigo-600 to-purple-600 border-2 border-indigo-400 text-white shadow-lg shadow-indigo-500/50'
                    : 'bg-gradient-to-r from-slate-700/50 to-slate-600/50 hover:from-slate-600/50 hover:to-slate-500/50 border border-slate-600/50 hover:border-slate-500/50 text-slate-300 hover:text-white'
                }`}
              >
                <Home className="w-4 h-4" />
                <span>Home</span>
              </button>
            )}
            
            {/* Clock */}
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-indigo-600/20 to-purple-600/20 border border-indigo-500/40 whitespace-nowrap font-semibold text-slate-200 text-sm">
              <Clock className="w-4 h-4 text-indigo-400" />
              <span>
                {time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default UniversalNavbar;
