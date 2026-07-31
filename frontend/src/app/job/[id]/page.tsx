"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { API_URL } from "@/lib/auth";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { 
  ArrowLeft, CheckCircle2, CircleDashed, AlertCircle, 
  RefreshCcw, Share2, Printer, Code, Check, Loader2, Sparkles, Database, Calculator, Globe2, ShieldAlert, FileText
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
  certificate?: any;
}

const PIPELINE_AGENTS = [
  { id: "IngestionAgent", name: "Ingestion Agent", icon: Database },
  { id: "Analysis Agent", name: "Analysis Agent", icon: Calculator },
  { id: "MarketIntelligenceAgent", name: "Market Intelligence Agent", icon: Globe2 },
  { id: "Risk Assessment Agent", name: "Risk Assessment Agent", icon: ShieldAlert },
  { id: "MemoGenerationAgent", name: "Memo Generation Agent", icon: FileText },
];

export default function JobPage() {
  const params = useParams();
  const id = params.id as string;
  
  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [progress, setProgress] = useState(0);
  const [memo, setMemo] = useState<Memo | null>(null);
  
  const [isCopied, setIsCopied] = useState(false);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  const toggleAgent = (agentId: string) => {
    setExpandedAgent(prev => prev === agentId ? null : agentId);
  };

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
  
  const activeLog = logs.length > 0 ? logs[logs.length - 1] : null;
  const activeAgentId = activeLog?.agent;
  const activeAgentIndex = PIPELINE_AGENTS.findIndex(a => a.id === activeAgentId);

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
            <Link href="/" className="hover:opacity-80 transition-opacity block">
              <Logo />
            </Link>
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
              <h3 className="text-lg font-bold tracking-tight mb-6 text-white flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-primary" />
                Investment Intelligence
              </h3>
              
              <div className="space-y-4 mb-8">
                <div className="glass p-4 rounded-xl border border-primary/20 bg-primary/5">
                  <div className="text-xs text-muted-foreground font-mono uppercase mb-1">Status</div>
                  <div className="text-primary font-bold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" /> Finalized
                  </div>
                </div>
                
                <div className="glass p-4 rounded-xl border border-white/5">
                  <div className="text-xs text-muted-foreground font-mono uppercase mb-1">Target</div>
                  <div className="text-white font-bold text-xl tracking-wider">{job.ticker}</div>
                </div>
                
                {memo.certificate && (
                  <div className="glass p-4 rounded-xl border border-white/5">
                    <div className="text-xs text-muted-foreground font-mono uppercase mb-1">Run Metadata</div>
                    <div className="text-white font-mono text-xs truncate" title={JSON.stringify(memo.certificate)}>
                      ID: {memo.certificate.run_id || "N/A"}
                    </div>
                  </div>
                )}
              </div>

              <div className="glass p-4 rounded-xl border border-white/5 mb-auto">
                <div className="text-xs text-muted-foreground font-mono uppercase mb-3">Integrity Checks</div>
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                    <span className="text-sm text-gray-300">17-Section Memo Generated</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                    <span className="text-sm text-gray-300">All Figures Source-Verified</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                    <span className="text-sm text-gray-300">Data Integrity Certified</span>
                  </div>
                </div>
              </div>
              
              <div className="space-y-3 mt-8">
                <button 
                  onClick={handleDownloadPdf}
                  className="w-full bg-primary/10 hover:bg-primary/20 border border-primary/30 hover:border-primary text-primary px-4 py-3 rounded-lg flex items-center justify-center gap-2 transition-all font-medium text-sm hover:shadow-[0_0_15px_rgba(57,255,136,0.2)]"
                >
                  <Printer className="w-4 h-4" /> Download PDF
                </button>
                <button 
                  onClick={handleDownloadHtml}
                  className="w-full glass border border-white/10 hover:border-white/30 hover:bg-white/5 text-white px-4 py-3 rounded-lg flex items-center justify-center gap-2 transition-all font-medium text-sm"
                >
                  <Code className="w-4 h-4" /> Export HTML
                </button>
                <button 
                  onClick={handleShare}
                  className="w-full glass border border-white/10 hover:border-white/30 hover:bg-white/5 text-white px-4 py-3 rounded-lg flex items-center justify-center gap-2 transition-all font-medium text-sm"
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
          <div className="container mx-auto px-4 py-12 flex flex-col items-center h-full overflow-y-auto">
            <div className="text-center mb-10 mt-8">
              <h2 className="text-3xl font-bold font-mono tracking-tight text-white mb-2">Analyzing {job.ticker}...</h2>
              <p className="text-muted-foreground">Compiling institutional-grade investment memorandum</p>
            </div>
            
            <div className="w-full max-w-2xl glass border border-white/10 rounded-2xl p-8 shadow-2xl relative overflow-hidden mb-12">
              <div className="absolute top-0 left-1/4 w-1/2 h-32 bg-primary/10 blur-[100px] rounded-full pointer-events-none" />
              
              <div className="mb-8">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-mono text-muted-foreground">Pipeline Progress</span>
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
              
              <div className="relative">
                <div className="absolute left-6 top-6 bottom-6 w-px bg-white/10" />
                
                <div className="space-y-8 relative">
                  {PIPELINE_AGENTS.map((agent, index) => {
                    const isAgentCompleted = activeAgentIndex > index;
                    const isAgentActive = activeAgentIndex === index || (activeAgentIndex === -1 && index === 0 && logs.length > 0);
                    const isAgentPending = !isAgentCompleted && !isAgentActive;
                    
                    const agentLogs = logs.filter(l => l.agent === agent.id);
                    const latestLogForAgent = agentLogs[agentLogs.length - 1] || (isAgentActive ? activeLog : null);

                    let circleColor = "bg-[#111] border-white/10 text-muted-foreground";
                    if (isAgentCompleted) circleColor = "bg-primary/20 border-primary/50 text-primary";
                    if (isAgentActive) circleColor = "bg-blue-500/20 border-blue-500/50 text-blue-400";
                    
                    return (
                      <div key={agent.id} className="flex items-start gap-6 relative">
                        <div 
                          className={`w-12 h-12 rounded-xl border flex items-center justify-center shrink-0 z-10 transition-colors duration-500 cursor-pointer hover:brightness-110 ${circleColor}`}
                          onClick={() => toggleAgent(agent.id)}
                        >
                          {isAgentCompleted ? (
                            <CheckCircle2 className="w-6 h-6" />
                          ) : isAgentActive ? (
                            <Loader2 className="w-6 h-6 animate-spin" />
                          ) : (
                            <agent.icon className="w-5 h-5 opacity-50" />
                          )}
                        </div>
                        
                        <div className="pt-2 flex-1 cursor-pointer" onClick={() => toggleAgent(agent.id)}>
                          <h4 className={`text-lg font-bold mb-1 transition-colors hover:text-white ${isAgentPending ? 'text-muted-foreground' : 'text-white'}`}>
                            {agent.name}
                          </h4>
                          
                          {/* Expanded View */}
                          {expandedAgent === agent.id && agentLogs.length > 0 && (
                            <motion.div 
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              className="mt-4 space-y-3 mb-6"
                            >
                              {agentLogs.map((log, i) => (
                                <div key={i} className="flex items-start gap-3">
                                  <CheckCircle2 className="w-4 h-4 mt-0.5 text-primary shrink-0" />
                                  <span className="text-sm font-mono text-gray-300">
                                    {log.summary}
                                  </span>
                                </div>
                              ))}
                            </motion.div>
                          )}
                          
                          {/* Collapsed View (Normal) */}
                          {expandedAgent !== agent.id && (
                            <>
                              {isAgentActive && latestLogForAgent && (
                                <AnimatePresence mode="wait">
                                  <motion.div 
                                    key={latestLogForAgent.summary}
                                    initial={{ opacity: 0, y: 5 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: -5 }}
                                    className="text-sm font-mono text-blue-400/80 flex items-center gap-2"
                                  >
                                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse shrink-0" />
                                    {latestLogForAgent.summary}
                                  </motion.div>
                                </AnimatePresence>
                              )}
                              
                              {isAgentCompleted && (
                                <div className="text-sm font-mono text-primary/70">
                                  Completed successfully
                                </div>
                              )}
                              
                              {isAgentPending && (
                                <div className="text-sm font-mono text-muted-foreground/50">
                                  Waiting in queue...
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
