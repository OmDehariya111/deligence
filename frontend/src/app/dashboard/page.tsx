"use client";

import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { API_URL } from "@/lib/auth";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { Search, ArrowRight, Loader2, UploadCloud, Zap, FileText, Clock, TrendingUp, ArrowLeft, Settings } from "lucide-react";
import { Logo } from "@/components/site/Logo";

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  
  const [ticker, setTicker] = useState("");
  const [contextFile, setContextFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [recentJobs, setRecentJobs] = useState<any[]>([]);
  const [isLoadingJobs, setIsLoadingJobs] = useState(true);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    async function fetchJobs() {
      try {
        const res = await fetch(`${API_URL}/jobs`, {
          credentials: "include"
        });
        if (res.ok) {
          const data = await res.json();
          // Assuming the API returns a list or { jobs: [...] }
          setRecentJobs(Array.isArray(data) ? data.slice(0, 5) : data.jobs?.slice(0, 5) || []);
        }
      } catch (err) {
        console.error("Failed to fetch recent jobs", err);
      } finally {
        setIsLoadingJobs(false);
      }
    }
    fetchJobs();
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelection = (file: File) => {
    if (file.size > 10 * 1024 * 1024) {
      setError("File size must be under 10MB");
      return;
    }
    if (!file.name.endsWith(".pdf") && !file.name.endsWith(".txt")) {
      setError("Only PDF and TXT files are supported");
      return;
    }
    setError(null);
    setContextFile(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelection(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user || (user.credits ?? 0) < 1) {
      setError("Insufficient credits. Please upgrade your plan.");
      return;
    }
    
    if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(ticker)) {
      setError("Invalid ticker format");
      return;
    }
    
    setIsSubmitting(true);
    setError(null);
    
    try {
      const formData = new FormData();
      formData.append("ticker", ticker);
      formData.append("agents", "full");
      if (contextFile) {
        formData.append("context_file", contextFile);
      }
      
      const res = await fetch(`${API_URL}/jobs`, {
        method: "POST",
        credentials: "include",
        body: formData
      });
      
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to start job");
      }
      
      const data = await res.json();
      router.push(`/job/${data.id}`);
    } catch (err: any) {
      setError(err.message || "An error occurred");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-foreground relative overflow-hidden">
      <header className="sticky top-0 z-50 glass border-b border-white/5 py-4">
        <div className="container max-w-5xl mx-auto px-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-muted-foreground hover:text-white transition-colors">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div className="w-px h-6 bg-white/10" />
            <Link href="/" className="hover:opacity-80 transition-opacity">
              <Logo />
            </Link>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium text-muted-foreground hidden sm:inline-block">
              {user?.full_name || "User"}
            </span>
            <Link href="/settings" className="text-muted-foreground hover:text-primary transition-colors">
              <Settings className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </header>

      {/* Radial glow background */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/20 blur-[120px] rounded-full pointer-events-none" />
      
      <div className="container max-w-5xl mx-auto px-4 py-12 relative z-10 space-y-12">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-end justify-between gap-6"
        >
          <div>
            <h1 className="text-4xl md:text-5xl font-bold mb-2">
              Welcome back, <span className="text-gradient-neon">{user?.full_name || "User"}</span>
            </h1>
            <p className="text-muted-foreground">What company are we analyzing today?</p>
          </div>
          
          <div className="glass px-6 py-4 rounded-xl flex items-center gap-4 border border-primary/20">
            <div className="bg-primary/20 p-2 rounded-full">
              <Zap className="text-primary w-6 h-6" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground uppercase tracking-wider font-mono">Credits</p>
              <p className="text-2xl font-bold text-primary">{user?.credits || 0}</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <form onSubmit={handleSubmit} className="glass rounded-2xl border border-primary/30 p-8 space-y-8 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-primary/10 blur-[80px] rounded-full" />
            
            <div>
              <label className="block text-sm font-medium mb-3 text-primary font-mono uppercase tracking-widest">
                Target Ticker
              </label>
              <div className="relative">
                <Search className="absolute left-6 top-1/2 -translate-y-1/2 text-primary w-8 h-8" />
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  placeholder="AAPL"
                  className="w-full bg-black/50 border border-primary/20 rounded-xl py-6 pl-20 pr-6 text-3xl font-mono uppercase focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors text-white placeholder:text-gray-600"
                />
              </div>
            </div>

            <div 
              className="border-2 border-dashed border-primary/20 rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer hover:border-primary/50 transition-colors bg-black/30"
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                type="file"
                ref={fileInputRef}
                className="hidden"
                accept=".pdf,.txt"
                onChange={handleFileChange}
              />
              <UploadCloud className="w-12 h-12 text-primary/60 mb-4" />
              <p className="text-lg font-medium mb-1 text-white">Upload Context File (Optional)</p>
              <p className="text-sm text-muted-foreground mb-4">PDF or TXT up to 10MB. Drag & drop or click to browse.</p>
              {contextFile && (
                <div className="flex items-center gap-2 bg-primary/20 text-primary px-4 py-2 rounded-full text-sm font-medium">
                  <FileText className="w-4 h-4" />
                  {contextFile.name}
                </div>
              )}
            </div>

            {error && (
              <div className="bg-risk/20 border border-risk/50 text-risk px-4 py-3 rounded-lg flex items-center gap-2 text-sm">
                <Zap className="w-4 h-4" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting || (user?.credits || 0) < 1}
              className="w-full bg-primary text-[#0a0a0a] font-bold text-lg py-5 rounded-xl flex items-center justify-center gap-2 neon-glow disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {isSubmitting ? (
                <Loader2 className="w-6 h-6 animate-spin" />
              ) : (user?.credits || 0) < 1 ? (
                <>Out of Credits</>
              ) : (
                <>
                  Start Due Diligence (1 Credit)
                  <ArrowRight className="w-6 h-6" />
                </>
              )}
            </button>
          </form>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="space-y-6"
        >
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-primary" />
            <h2 className="text-xl font-bold font-mono tracking-tight">Recent Analyses</h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {isLoadingJobs ? (
              <div className="glass p-6 rounded-xl flex items-center justify-center">
                <Loader2 className="w-6 h-6 text-primary animate-spin" />
              </div>
            ) : recentJobs.length === 0 ? (
              <div className="glass p-6 rounded-xl border border-white/5 col-span-full">
                <p className="text-muted-foreground text-center">No recent jobs found. Start your first analysis above.</p>
              </div>
            ) : (
              recentJobs.map((job) => (
                <Link key={job.id} href={`/job/${job.id}`}>
                  <div className="glass p-5 rounded-xl border border-white/5 hover:border-primary/50 transition-colors group">
                    <div className="flex justify-between items-start mb-4">
                      <div className="flex items-center gap-2">
                        <TrendingUp className="w-5 h-5 text-primary" />
                        <span className="font-mono text-xl font-bold text-white">{job.ticker}</span>
                      </div>
                      <span className={`text-xs px-2 py-1 rounded-full font-mono font-medium ${
                        job.status === "COMPLETED" ? "bg-primary/20 text-primary" :
                        job.status === "FAILED" ? "bg-risk/20 text-risk" :
                        "bg-blue-500/20 text-blue-400"
                      }`}>
                        {job.status}
                      </span>
                    </div>
                    <div className="flex justify-between items-end">
                      <span className="text-xs text-muted-foreground">
                        {new Date(job.created_at).toLocaleDateString()}
                      </span>
                      <span className="text-sm text-primary font-medium flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                        View <ArrowRight className="w-4 h-4 ml-1" />
                      </span>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
