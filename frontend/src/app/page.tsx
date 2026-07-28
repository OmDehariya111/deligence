"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/auth-provider";
import { API_URL } from "@/lib/auth";
import { Search, UploadCloud, ArrowRight, Sparkles, Lock, Zap, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { motion } from "framer-motion";

// Custom UI Effects
import { SparklesText } from "@/components/ui-effects/sparkles";
import { BorderBeam } from "@/components/ui-effects/border-beam";

export default function Home() {
  const router = useRouter();
  const { user, isLoading: authLoading, refreshUser } = useAuth();
  const [ticker, setTicker] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectFile = (selectedFile: File | undefined) => {
    if (!selectedFile) return;
    const extension = selectedFile.name.split(".").pop()?.toLowerCase();
    if (!extension || !["pdf", "txt"].includes(extension)) {
      setError("Please upload a PDF or TXT context file.");
      return;
    }
    if (selectedFile.size > 10 * 1024 * 1024) {
      setError("Context files must be 10 MB or smaller.");
      return;
    }
    setError(null);
    setFile(selectedFile);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      selectFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!user) {
      router.push("/login");
      return;
    }

    const normalizedTicker = ticker.trim().toUpperCase();
    if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(normalizedTicker)) {
      setError("Enter a valid stock ticker, such as AAPL or BRK.B.");
      return;
    }
    
    if ((user.credits ?? 0) < 1) {
      setError("Insufficient credits. Please upgrade your plan to generate more reports.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("ticker", normalizedTicker);
      formData.append("agents", "full");
      if (file) formData.append("context_file", file);

      const response = await fetch(`${API_URL}/jobs`, {
        method: "POST",
        body: formData,
        credentials: "include"
      });
      
      const data = await response.json().catch(() => ({}));
      if (response.ok && data.id) {
        await refreshUser();
        router.push(`/job/${data.id}`);
      } else if (response.status === 403) {
        setError(data.detail || "Insufficient credits.");
        setLoading(false);
      } else {
        setError(data.detail || "Failed to start generation.");
        setLoading(false);
      }
    } catch (err) {
      console.error("Error:", err);
      setError("Network Error: Could not connect to the backend server. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-x-hidden bg-black selection:bg-indigo-500/30">
      
      {/* 1. Dot Pattern Background */}
      <div className="absolute inset-0 z-0 bg-[radial-gradient(#ffffff22_1px,transparent_1px)] [background-size:20px_20px] opacity-30" />

      {/* 2. Aurora / Mesh Gradient Background (Animated via Framer Motion) */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        <motion.div
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.6, 0.8, 0.6],
            rotate: [0, 90, 0],
          }}
          transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
          className="absolute -top-[10%] -left-[10%] w-[60vw] h-[60vw] rounded-full bg-blue-600/30 blur-[100px] mix-blend-screen"
        />
        <motion.div
          animate={{
            scale: [1, 1.5, 1],
            opacity: [0.5, 0.7, 0.5],
            rotate: [0, -90, 0],
          }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          className="absolute -bottom-[10%] -right-[10%] w-[50vw] h-[50vw] rounded-full bg-purple-600/30 blur-[100px] mix-blend-screen"
        />
        <motion.div
          animate={{
            scale: [1, 1.1, 1],
            opacity: [0.4, 0.6, 0.4],
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-[20%] left-[20%] w-[40vw] h-[40vw] rounded-full bg-indigo-500/30 blur-[120px] mix-blend-screen"
        />
      </div>

      <div className="relative z-10 w-full max-w-2xl px-4 flex flex-col items-center">
        
        {/* Animated Header */}
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="text-center mb-14"
        >
          <div className="inline-flex items-center justify-center space-x-2 mb-8 px-5 py-2 rounded-full bg-white/5 border border-white/10 text-sm text-indigo-300 font-semibold backdrop-blur-md shadow-[0_0_20px_rgba(79,70,229,0.15)]">
            <Sparkles className="w-4 h-4" />
            <span>DeligenX AI Platform v2.0</span>
          </div>
          <h1 className="text-5xl sm:text-6xl md:text-8xl font-extrabold tracking-tighter text-white mb-6 drop-shadow-2xl">
            Generate <SparklesText text="Alpha." />
          </h1>
          <p className="text-xl text-slate-300 max-w-xl mx-auto font-medium leading-relaxed drop-shadow-md">
            Multi-agent intelligence for deep fundamental analysis, SEC filings, and quality of earnings.
          </p>
        </motion.div>

        {/* Input Form with Border Beam */}
        <motion.form 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
          onSubmit={handleSubmit} 
          className="w-full relative group"
        >
          <Card className="relative overflow-hidden bg-black/40 border border-white/10 backdrop-blur-2xl p-6 rounded-3xl shadow-[0_0_50px_-12px_rgba(79,70,229,0.3)]">
            {/* The Magic UI Border Beam */}
            <BorderBeam size={300} duration={8} colorFrom="#818cf8" colorTo="#c084fc" />

            <div className="space-y-6 relative z-10">
              {/* Ticker Input */}
              <div className="relative">
                <div className="absolute inset-y-0 left-5 flex items-center pointer-events-none">
                  <Search className="h-6 w-6 text-slate-400" />
                </div>
                <Input
                  type="text"
                  placeholder="Company Ticker (e.g. AAPL)"
                  value={ticker}
                   onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  className="h-20 pl-16 pr-6 w-full bg-white/5 border-white/10 text-2xl font-bold text-white placeholder:text-slate-500 focus:bg-white/10 focus:border-indigo-500/50 rounded-2xl transition-all shadow-inner"
                  required
                />
              </div>

              {/* Drag & Drop Zone */}
              <div 
                className={`border-dashed border-2 rounded-2xl p-8 text-center transition-all cursor-pointer bg-white/5 backdrop-blur-sm ${
                  isDragging ? "border-indigo-500 bg-indigo-500/20" : "border-white/10 hover:border-indigo-400/50 hover:bg-white/10"
                }`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
                onDrop={handleDrop}
                onClick={() => document.getElementById("file-upload")?.click()}
                onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); document.getElementById("file-upload")?.click(); } }}
                role="button"
                tabIndex={0}
                aria-label="Upload optional PDF or TXT research context"
              >
                <input 
                  id="file-upload" type="file" className="hidden" accept=".pdf,.txt"
                   onChange={(e) => selectFile(e.target.files?.[0])}
                />
                <div className="flex flex-col items-center justify-center space-y-4">
                  <div className="p-4 bg-white/10 rounded-full shadow-inner">
                    <UploadCloud className={`w-8 h-8 ${file ? 'text-indigo-400' : 'text-slate-300'}`} />
                  </div>
                  <div>
                    {file ? (
                      <p className="text-base font-bold text-indigo-300">{file.name}</p>
                    ) : (
                      <>
                        <p className="text-base font-semibold text-slate-200 mb-1">
                          Upload Context Files (Optional)
                        </p>
                        <p className="text-sm text-slate-400">
                          Drag and drop PDFs or TXT files here
                        </p>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Error Message */}
               {error && (
                 <div role="alert" className="p-4 bg-red-500/10 border border-red-500/20 rounded-2xl flex items-center justify-between text-red-400 text-sm font-medium">
                  <span>{error}</span>
                  {user?.credits === 0 && (
                    <Button type="button" onClick={() => router.push("/pricing")} variant="outline" className="bg-red-500/20 border-red-500/50 hover:bg-red-500/30 text-white border ml-4">
                      Upgrade
                    </Button>
                  )}
                </div>
              )}

              {/* Submit Button */}
              {user?.credits === 0 ? (
                <Button 
                  type="button" 
                  onClick={() => router.push("/pricing")}
                  className="w-full h-16 bg-gradient-to-r from-purple-500 to-indigo-600 text-white hover:opacity-90 text-xl font-bold rounded-2xl shadow-[0_0_40px_-10px_rgba(168,85,247,0.4)] transition-all flex items-center justify-center gap-3 relative overflow-hidden group"
                >
                  <Lock className="w-5 h-5 relative z-10" />
                  <span className="relative z-10">Out of Credits - Upgrade Plan</span>
                  <Zap className="w-5 h-5 relative z-10" />
                </Button>
              ) : (
                <Button 
                  type="submit" 
                  disabled={loading || authLoading || (!!user && !ticker.trim())}
                  className="w-full relative group overflow-hidden rounded-2xl bg-gradient-to-r from-emerald-500 to-blue-500 hover:from-emerald-400 hover:to-blue-400 text-white font-bold text-lg py-6 transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:hover:scale-100 shadow-[0_0_40px_rgba(16,185,129,0.3)] hover:shadow-[0_0_60px_rgba(16,185,129,0.5)] border border-white/20"
                >
                  <div className="absolute inset-0 bg-white/20 group-hover:translate-x-full transition-transform duration-500 -skew-x-12 -ml-20 w-1/2" />
                  <span className="relative z-10 flex items-center gap-2">
                    {!user ? "Login to Generate" : loading ? <><Loader2 className="w-5 h-5 animate-spin" /> Initializing Agents...</> : `Start Due Diligence (1 Credit)`}
                  </span>
                  {!loading && user && <ArrowRight className="w-6 h-6 relative z-10 group-hover:translate-x-1 transition-transform" />}
                  <div className="absolute inset-0 h-full w-full bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 opacity-0 group-hover:opacity-30 transition-opacity duration-500" />
                </Button>
              )}
            </div>
          </Card>
        </motion.form>
      </div>
    </div>
  );
}
