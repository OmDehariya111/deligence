"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { API_URL } from "@/lib/auth";
import Link from "next/link";
import { FileText, Loader2, ArrowRight } from "lucide-react";

interface Job {
  id: string;
  ticker: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  created_at: string;
}

export default function HistoryPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchJobs() {
      try {
        const res = await fetch(`${API_URL}/jobs`, { credentials: "include" });
        if (!res.ok) throw new Error("Failed to fetch jobs");
        const data = await res.json();
        setJobs(data);
      } catch (err: any) {
        setError(err.message || "An error occurred");
      } finally {
        setLoading(false);
      }
    }
    fetchJobs();
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return "text-primary border-primary/50 bg-primary/10";
      case "FAILED":
        return "text-[#ff5c5c] border-[#ff5c5c]/50 bg-[#ff5c5c]/10";
      case "RUNNING":
        return "text-blue-400 border-blue-400/50 bg-blue-400/10";
      default:
        return "text-muted-foreground border-muted-foreground/50 bg-muted/10";
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-foreground p-6 md:p-12 relative overflow-hidden">
      {/* Background Glow */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-primary/10 blur-[120px] pointer-events-none" />
      
      <div className="max-w-5xl mx-auto relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-8"
        >
          <h1 className="text-4xl font-bold mb-2">Analysis <span className="text-gradient-neon">History</span></h1>
          <p className="text-muted-foreground">View your past due diligence reports and running tasks.</p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="glass rounded-xl p-6 border border-border"
        >
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20">
              <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
              <p className="text-muted-foreground font-mono">Loading history...</p>
            </div>
          ) : error ? (
            <div className="text-center py-10 text-[#ff5c5c]">{error}</div>
          ) : jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4 border border-primary/20">
                <FileText className="w-8 h-8 text-primary" />
              </div>
              <h3 className="text-xl font-bold mb-2">No analyses yet</h3>
              <p className="text-muted-foreground mb-6 max-w-md">You haven't run any due diligence reports. Start an analysis from the dashboard.</p>
              <Link href="/dashboard" className="px-6 py-2 rounded-md bg-primary text-primary-foreground font-medium neon-glow inline-flex items-center gap-2">
                Go to Dashboard <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-border/50 text-muted-foreground text-sm font-medium">
                    <th className="pb-4 pl-2">Ticker</th>
                    <th className="pb-4">Job ID</th>
                    <th className="pb-4">Date</th>
                    <th className="pb-4">Status</th>
                    <th className="pb-4 text-right pr-2">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {jobs.map((job) => (
                    <tr key={job.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-4 pl-2 font-bold">{job.ticker}</td>
                      <td className="py-4 font-mono text-sm text-muted-foreground">{job.id.substring(0, 8)}...</td>
                      <td className="py-4 text-sm text-muted-foreground">
                        {new Date(job.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusColor(job.status)}`}>
                          {job.status}
                        </span>
                      </td>
                      <td className="py-4 text-right pr-2">
                        {job.status === "COMPLETED" ? (
                          <Link href={`/report/${job.id}`} className="text-primary hover:text-primary/80 transition-colors inline-flex items-center gap-1 text-sm font-medium">
                            View Report <ArrowRight className="w-3 h-3" />
                          </Link>
                        ) : (
                          <span className="text-muted-foreground text-sm cursor-not-allowed">Pending...</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
