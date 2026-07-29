"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { API_URL } from "@/lib/auth";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { 
  ArrowLeft, Terminal, CheckCircle2, CircleDashed, AlertCircle, 
  RefreshCcw, Share2, Printer, Code, Check, Loader2 
} from "lucide-react";
import { Logo } from "@/components/site/Logo";
import { useParams } from "next/navigation";

interface Job {
  id: string;
  ticker: string;
  status: string;
  error_message?: string;
  created_at: string;
}

interface LogEntry {
  agent: string;
  module: string;
  status: string;
  summary: string;
  timestamp: string;
  duration_seconds: number;
}

interface LogsResponse {
  logs: LogEntry[];
  progress: number;
  total_stages: number;
}

interface Memo {
  html: string;
  certificate?: string;
}

export default function JobPage() {
  const params = useParams();
  const id = params.id as string;
  
  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [progress, setProgress] = useState(0);
  const [memo, setMemo] = useState<Memo | null>(null);
  
  const [isCopied, setIsCopied] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const fetchJobData = useCallback(async () => {
    try {
      const jobRes = await fetch(`${API_URL}/jobs/${id}`, { credentials: "include" });
      if (jobRes.ok) {
        const jobData = await jobRes.json();
        setJob(jobData);
        
        if (jobData.status !== "FAILED") {
          const logsRes = await fetch(`${API_URL}/jobs/${id}/logs`, { credentials: "include" });
          if (logsRes.ok) {
            const logsData: LogsResponse = await logsRes.json();
            setLogs(logsData.logs || []);
            setProgress(logsData.progress || 0);
          }
        }
        
        if (jobData.status === "COMPLETED" && !memo) {
          const memoRes = await fetch(`${API_URL}/jobs/${id}/memo`, { credentials: "include" });
          if (memoRes.ok) {
            const memoData = await memoRes.json();
            setMemo(memoData);
          }
        }
      }
    } catch (err) {
      console.error("Failed to fetch job data", err);
    }
  }, [id, memo]);

  useEffect(() => {
    fetchJobData();
    
    let interval: NodeJS.Timeout;
    if (job?.status !== "COMPLETED" && job?.status !== "FAILED") {
      interval = setInterval(fetchJobData, 2500);
    }
    
    return () => clearInterval(interval);
  }, [job?.status, fetchJobData]);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleDownloadHtml = () => {
    if (!memo?.html) return;
    const blob = new Blob([memo.html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${job?.ticker || "memo"}-diligence.html`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadPdf = () => {
    window.location.assign(`${API_URL}/jobs/${id}/pdf`);
  };

  if (!job) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <Loader2 className="w-12 h-12 text-primary animate-spin" />
      </div>
    );
  }

  const isCompleted = job.status === "COMPLETED" && memo;
  const isFailed = job.status === "FAILED";

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-foreground flex flex-col">
      {/* Top Nav */}
      <header className="glass border-b border-white/5 sticky top-0 z-50">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-muted-foreground hover:text-white transition-colors">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div className="w-px h-6 bg-white/10" />
            <div className="scale-75 origin-left">
              <Logo />
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <span className="font-mono text-xl font-bold text-white tracking-widest">{job.ticker}</span>
            <div className={`px-3 py-1 rounded-full border text-xs font-mono font-medium flex items-center gap-2 ${
              isCompleted ? "bg-primary/10 border-primary/30 text-primary" : 
              isFailed ? "bg-risk/10 border-risk/30 text-risk" : 
              "bg-blue-500/10 border-blue-500/30 text-blue-400"
            }`}>
              {isCompleted && <CheckCircle2 className="w-3 h-3" />}
              {isFailed && <AlertCircle className="w-3 h-3" />}
              {!isCompleted && !isFailed && <CircleDashed className="w-3 h-3 animate-spin" />}
              {job.status}
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 flex overflow-hidden">
        {isFailed ? (
          <div className="container mx-auto px-4 py-20 flex flex-col items-center justify-center text-center">
            <div className="w-24 h-24 bg-risk/10 text-risk rounded-full flex items-center justify-center mb-6">
              <AlertCircle className="w-12 h-12" />
            </div>
            <h2 className="text-3xl font-bold mb-4">Analysis Failed</h2>
            <p className="text-muted-foreground max-w-md mb-8">
              {job.error_message || "An unexpected error occurred during the analysis process."}
            </p>
            <Link 
              href="/dashboard"
              className="bg-primary text-[#0a0a0a] px-8 py-3 rounded-xl font-bold flex items-center gap-2 neon-glow"
            >
              <RefreshCcw className="w-5 h-5" />
              Try Again
            </Link>
          </div>
        ) : isCompleted ? (
          <div className="flex-1 flex flex-col md:flex-row h-full overflow-hidden">
            {/* Boardroom Left Sidebar */}
            <div className="w-full md:w-80 glass border-r border-white/5 p-6 flex flex-col shrink-0 overflow-y-auto">
              <h3 className="text-lg font-bold font-mono tracking-tight mb-6 text-white flex items-center gap-2">
                <Terminal className="w-5 h-5 text-primary" />
                Boardroom Output
              </h3>
              
              <div className="space-y-4 mb-8 flex-1">
                <div className="glass p-4 rounded-xl border border-primary/20 bg-primary/5">
                  <div className="text-xs text-muted-foreground font-mono uppercase mb-1">Status</div>
                  <div className="text-primary font-bold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" /> Finalized
                  </div>
                </div>
                
                <div className="glass p-4 rounded-xl border border-white/5">
                  <div className="text-xs text-muted-foreground font-mono uppercase mb-1">Target</div>
                  <div className="text-white font-bold">{job.ticker}</div>
                </div>
                
                {memo.certificate && (
                  <div className="glass p-4 rounded-xl border border-white/5">
                    <div className="text-xs text-muted-foreground font-mono uppercase mb-1">Integrity Hash</div>
                    <div className="text-white font-mono text-xs truncate" title={memo.certificate}>
                      {memo.certificate}
                    </div>
                  </div>
                )}
              </div>
              
              <div className="space-y-3">
                <button 
                  onClick={handleDownloadPdf}
                  className="w-full glass border border-primary/30 hover:border-primary text-primary px-4 py-3 rounded-lg flex items-center justify-center gap-2 transition-colors font-medium text-sm"
                >
                  <Printer className="w-4 h-4" /> Download PDF
                </button>
                <button 
                  onClick={handleDownloadHtml}
                  className="w-full glass border border-white/10 hover:border-white/30 text-white px-4 py-3 rounded-lg flex items-center justify-center gap-2 transition-colors font-medium text-sm"
                >
                  <Code className="w-4 h-4" /> Export HTML
                </button>
                <button 
                  onClick={handleShare}
                  className="w-full glass border border-white/10 hover:border-white/30 text-white px-4 py-3 rounded-lg flex items-center justify-center gap-2 transition-colors font-medium text-sm"
                >
                  {isCopied ? <Check className="w-4 h-4 text-primary" /> : <Share2 className="w-4 h-4" />}
                  {isCopied ? "Copied!" : "Share Link"}
                </button>
              </div>
            </div>
            
            {/* Right Iframe */}
            <div className="flex-1 bg-white relative overflow-hidden">
              <iframe 
                srcDoc={memo.html} 
                className="w-full h-full border-none absolute inset-0"
                title="Diligence Memo"
              />
            </div>
          </div>
        ) : (
          <div className="container mx-auto px-4 py-8 flex flex-col h-full max-w-5xl">
            {/* Live Console */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-mono text-muted-foreground">Analysis Progress</span>
                <span className="text-sm font-mono text-primary">{Math.round(progress)}%</span>
              </div>
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <motion.div 
                  className="h-full bg-primary"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.5 }}
                />
              </div>
            </div>
            
            <div className="flex-1 glass border border-primary/20 rounded-xl overflow-hidden flex flex-col relative shadow-[0_0_30px_rgba(57,255,136,0.1)]">
              <div className="bg-black/50 border-b border-white/5 px-4 py-3 flex items-center gap-2">
                <Terminal className="w-4 h-4 text-primary" />
                <span className="font-mono text-xs text-white">live-console.sh</span>
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse ml-2" />
              </div>
              
              <div className="flex-1 overflow-y-auto p-4 font-mono text-xs sm:text-sm space-y-2">
                <AnimatePresence initial={false}>
                  {logs.map((log, i) => (
                    <motion.div 
                      key={i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex items-start gap-3 border-l-2 pl-3 py-1"
                      style={{ 
                        borderColor: log.status === "COMPLETED" ? "#39ff88" : 
                                    log.status === "RUNNING" ? "#3b82f6" : "#4b5563"
                      }}
                    >
                      <span className="text-muted-foreground shrink-0 w-20">
                        {new Date(log.timestamp).toLocaleTimeString([], { hour12: false })}
                      </span>
                      <span className="text-purple-400 shrink-0 w-24">[{log.agent}]</span>
                      <span className="text-gray-300 flex-1">{log.summary}</span>
                      {log.duration_seconds > 0 && (
                        <span className="text-muted-foreground shrink-0 text-right">
                          {log.duration_seconds.toFixed(1)}s
                        </span>
                      )}
                    </motion.div>
                  ))}
                </AnimatePresence>
                <div ref={logsEndRef} className="h-4" />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
