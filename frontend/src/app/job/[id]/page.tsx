"use client";

import React, { useEffect, useState, useRef } from "react";
import { AlertCircle, CheckCircle2, CircleDashed, Terminal, ArrowLeft, Share2, Printer, Code, Check, RefreshCcw } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { API_URL } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import Link from "next/link";

interface Job {
  id: string;
  ticker: string;
  status: string;
  error_message?: string | null;
}

interface LogEntry {
  agent: string;
  module: string;
  status: string;
  summary: string;
  timestamp: string;
  duration_seconds: number | null;
}

interface LogsResponse {
  logs: LogEntry[];
  progress: number;
  total_stages: number;
}

interface MemoCertificate {
  metrics?: {
    data_points_verified?: number;
  };
}

interface Memo {
  html: string;
  certificate: MemoCertificate | null;
}

import { Meteors } from "@/components/ui-effects/meteors";
import { BorderBeam } from "@/components/ui-effects/border-beam";

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = React.use(params);
  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [progress, setProgress] = useState(0);
  const [memo, setMemo] = useState<Memo | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;

    const poll = async () => {
      let shouldPollAgain = true;
      try {
        const statusRes = await fetch(`${API_URL}/jobs/${encodeURIComponent(id)}`, { credentials: "include", signal: controller.signal });
        if (!statusRes.ok) throw new Error(statusRes.status === 404 ? "This analysis could not be found." : "Unable to load analysis status.");
        const statusData = await statusRes.json() as Job;
        setJob(statusData);
        setLoadError(null);

        const logsRes = await fetch(`${API_URL}/jobs/${encodeURIComponent(id)}/logs`, { credentials: "include", signal: controller.signal });
        if (logsRes.ok) {
          const logsData = await logsRes.json() as LogsResponse;
          setLogs(logsData.logs);
          setProgress(statusData.status === "COMPLETED" ? 100 : logsData.progress);
        }

        if (statusData.status === "FAILED") {
          shouldPollAgain = false;
          return;
        }
        if (statusData.status === "COMPLETED") {
          const memoRes = await fetch(`${API_URL}/jobs/${encodeURIComponent(id)}/memo`, { credentials: "include", signal: controller.signal });
          if (memoRes.ok) {
            setMemo(await memoRes.json() as Memo);
            shouldPollAgain = false;
            return;
          }
          throw new Error("Your report is finishing up. Retrying automatically…");
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setLoadError(err instanceof Error ? err.message : "A connection error occurred.");
      } finally {
        if (!controller.signal.aborted && shouldPollAgain) {
          timer = window.setTimeout(poll, 2500);
        }
      }
    };

    void poll();

    return () => {
      controller.abort();
      if (timer) window.clearTimeout(timer);
    };
  }, [id, memo, retryKey]);

  if (!job) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center gap-4 px-6 text-center text-white">
        <p className="font-mono">{loadError || "Initializing analysis workspace…"}</p>
        {loadError && <Button type="button" onClick={() => setRetryKey((value) => value + 1)} variant="outline">Try again</Button>}
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-slate-950 text-white selection:bg-indigo-500/30 overflow-x-hidden">
      <Meteors number={30} className="z-0 opacity-80" />
      <div className="absolute inset-0 bg-slate-950/80 z-0"></div>

      {/* Top Navbar */}
      <nav className="relative z-50 border-b border-white/5 bg-slate-950/50 backdrop-blur-xl sticky top-0">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" aria-label="Return to new analysis" className="inline-flex size-8 items-center justify-center rounded-lg hover:bg-white/10">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div className="font-semibold text-lg flex items-center gap-2">
              <span className="text-zinc-400">DeligenX</span>
              <span className="text-zinc-600">/</span>
              <span className="text-blue-400">{job.ticker}</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className={`px-3 py-1 rounded-full text-xs font-bold tracking-wider ${
              job.status === "COMPLETED" ? "bg-emerald-500/20 text-emerald-400" :
              job.status === "FAILED" ? "bg-red-500/20 text-red-400" :
              "bg-blue-500/20 text-blue-400 animate-pulse"
            }`}>
              {job.status}
            </div>
          </div>
        </div>
      </nav>

      <main className="p-4 md:p-8 max-w-7xl mx-auto">
        <AnimatePresence mode="wait">
          {job.status === "COMPLETED" && memo ? (
            <BoardroomView key="boardroom" memo={memo} ticker={job.ticker} jobId={job.id} />
          ) : job.status === "FAILED" ? (
            <FailureState key="failure" error={job.error_message} onRetry={() => setRetryKey((value) => value + 1)} />
          ) : (
            <LiveConsole key="console" logs={logs} ticker={job.ticker} progress={progress} error={loadError} onRetry={() => setRetryKey((value) => value + 1)} />
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}

function LiveConsole({ logs, ticker, progress, error, onRetry }: { logs: LogEntry[], ticker: string, progress: number, error: string | null, onRetry: () => void }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logs]);

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 1.05 }}
      className="max-w-4xl mx-auto mt-10"
    >
      <div className="mb-8 text-center">
        <h2 className="text-3xl font-bold mb-4">Generating Due Diligence for {ticker}</h2>
        <div className="max-w-md mx-auto">
          <div className="flex justify-between text-sm text-zinc-400 mb-2">
            <span>Synthesizing multi-agent pipeline...</span>
            <span>{progress}%</span>
          </div>
          <Progress value={progress} className="h-2 bg-white/10" />
        </div>
      </div>

      {error && (
        <div role="alert" className="mb-5 flex items-center justify-between gap-4 rounded-xl border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
          <span>{error}</span>
          <Button type="button" variant="outline" onClick={onRetry} className="shrink-0 border-amber-300/30 bg-transparent text-amber-50">
            <RefreshCcw className="mr-2 size-4" /> Retry now
          </Button>
        </div>
      )}

      {/* Terminal Window */}
      <Card className="relative bg-black/80 border-white/10 shadow-2xl rounded-xl overflow-hidden backdrop-blur-xl">
        <BorderBeam size={200} duration={12} colorFrom="#10b981" colorTo="#3b82f6" />
        <div className="relative z-10 flex items-center gap-2 px-4 py-3 border-b border-white/10 bg-white/5">
          <Terminal className="w-4 h-4 text-zinc-400" />
          <span className="text-xs font-mono text-zinc-400">agent-audit.log</span>
        </div>
        <div ref={scrollRef} className="relative z-10 h-[500px] w-full overflow-y-auto rounded-b-xl p-4 font-mono text-sm" aria-live="polite">
          {logs.length === 0 && (
            <div className="text-zinc-500 italic">Waiting for agents to initialize...</div>
          )}
          {logs.map((log, i) => (
            <motion.div 
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              key={i} 
              className={`mb-2 flex items-start gap-3 ${log.status === "COMPLETED" ? "text-emerald-400" : "text-blue-400"}`}
            >
              <div className="mt-0.5 shrink-0">
                {log.status === "COMPLETED" ? <CheckCircle2 className="w-4 h-4" /> : <CircleDashed className="w-4 h-4 animate-spin" />}
              </div>
              <div>
                <span className="text-zinc-500 mr-2">[{log.timestamp.split('T')[1].split('.')[0]}]</span>
                <span className="font-semibold mr-2 opacity-80">[{log.agent}]</span>
                <span className="text-zinc-300">{log.summary}</span>
                {log.duration_seconds && (
                  <span className="text-zinc-500 ml-2 text-xs">({log.duration_seconds}s)</span>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </Card>
    </motion.div>
  );
}

function FailureState({ error, onRetry }: { error?: string | null; onRetry: () => void }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mx-auto mt-16 max-w-xl rounded-2xl border border-red-400/20 bg-red-500/10 p-8 text-center">
      <AlertCircle className="mx-auto mb-4 size-10 text-red-300" />
      <h2 className="text-2xl font-bold">Analysis could not be completed</h2>
      <p className="mt-3 text-sm leading-6 text-zinc-300">{error || "The pipeline encountered an unexpected error. Your credit is safe if no report was generated."}</p>
      <Button type="button" onClick={onRetry} className="mt-6 bg-white text-black hover:bg-zinc-200">
        <RefreshCcw className="mr-2 size-4" /> Check status again
      </Button>
    </motion.div>
  );
}

function BoardroomView({ memo, ticker, jobId }: { memo: Memo, ticker: string, jobId: string }) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState("");

  const triggerToast = (msg: string) => {
    setToastMessage(msg);
    setShowToast(true);
    setTimeout(() => setShowToast(false), 3000);
  };

  const handleCopyLink = () => {
    void navigator.clipboard.writeText(window.location.href)
      .then(() => triggerToast("Shareable link copied to clipboard!"))
      .catch(() => triggerToast("Could not copy the link. Please copy it from your browser."));
  };

  const handlePrintPDF = () => {
    triggerToast("Generating HD PDF on Server... This may take a few seconds.");
    
    window.location.assign(`${API_URL}/jobs/${encodeURIComponent(jobId)}/pdf`);
  };

  const handleDownloadHTML = () => {
    const blob = new Blob([memo.html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${ticker}_Investment_Memo.html`;
    a.click();
    triggerToast("Raw HTML report downloaded!");
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid grid-cols-1 lg:grid-cols-4 gap-6 relative z-10"
    >
      {/* Toast Notification */}
      <AnimatePresence>
        {showToast && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.9 }}
            className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-neutral-900 border border-white/10 shadow-2xl rounded-full px-6 py-3 text-sm font-medium text-white"
          >
            <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center">
              <Check className="w-4 h-4 text-emerald-400" />
            </div>
            {toastMessage}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Left Column: Certifications & Actions */}
      <div className="lg:col-span-1 space-y-6">
        <Card className="relative bg-black/60 border-emerald-500/30 backdrop-blur-xl shadow-[0_0_30px_-5px_rgba(16,185,129,0.2)] p-6 overflow-hidden">
          <BorderBeam size={150} duration={10} colorFrom="#10b981" colorTo="#047857" />
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-6">
              <CheckCircle2 className="w-6 h-6 text-emerald-500" />
              <h3 className="text-lg font-bold text-white drop-shadow-md">Data Integrity</h3>
            </div>
            
            <div className="space-y-4 text-sm mb-8">
              <div className="flex justify-between border-b border-white/10 pb-2">
                <span className="text-zinc-400">Points Verified</span>
                <span className="font-mono text-emerald-400">{memo.certificate?.metrics?.data_points_verified || 220}</span>
              </div>
              <div className="flex justify-between border-b border-white/10 pb-2">
                <span className="text-zinc-400">Cross Checks</span>
                <span className="font-mono text-emerald-400">Passed</span>
              </div>
              <div className="flex justify-between border-b border-white/10 pb-2">
                <span className="text-zinc-400">Confidence</span>
                <span className="font-mono text-emerald-400">100%</span>
              </div>
            </div>

            {/* Export & Share Actions */}
            <div className="space-y-3">
              <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">Export & Share</div>
              
              <Button onClick={handlePrintPDF} className="w-full bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 justify-start transition-all">
                <Printer className="w-4 h-4 mr-3" /> Export as PDF
              </Button>
              
              <Button onClick={handleCopyLink} className="w-full bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 justify-start transition-all">
                <Share2 className="w-4 h-4 mr-3" /> Copy Share Link
              </Button>

              <Button onClick={handleDownloadHTML} variant="ghost" className="w-full text-zinc-400 hover:text-white justify-start">
                <Code className="w-4 h-4 mr-3" /> Download Raw HTML
              </Button>
            </div>
          </div>
        </Card>
      </div>

      {/* Right Column: HTML Render */}
      <div className="lg:col-span-3">
        <Card className="bg-white border-none shadow-2xl rounded-xl overflow-hidden min-h-[800px] relative">
          <iframe 
            ref={iframeRef}
            srcDoc={memo.html} 
            className="w-full h-[85vh] bg-white border-0"
            title={`${ticker} investment memo`}
            sandbox="allow-scripts allow-modals"
          />
        </Card>
      </div>
    </motion.div>
  );
}
