"use client";

import { useEffect, useState } from "react";
import { Meteors } from "@/components/ui-effects/meteors";
import { API_URL } from "@/lib/auth";
import Link from "next/link";

interface Job {
  id: string;
  ticker: string;
  status: string;
  created_at: string;
}

export default function HistoryPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchJobs() {
      try {
        const res = await fetch(`${API_URL}/jobs`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            setJobs(data);
          } else {
            setJobs([]);
          }
        } else {
          setJobs([]);
        }
      } catch (err) {
        console.error("Failed to fetch jobs", err);
        setJobs([]);
      } finally {
        setLoading(false);
      }
    }
    fetchJobs();
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "FAILED":
        return "bg-red-500/10 text-red-400 border-red-500/20";
      case "RUNNING":
        return "bg-blue-500/10 text-blue-400 border-blue-500/20";
      default:
        return "bg-gray-500/10 text-gray-400 border-gray-500/20";
    }
  };

  return (
    <div className="min-h-screen bg-black relative flex flex-col items-center py-20 px-4">
      {/* Dynamic Backgrounds */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <Meteors number={15} />
      </div>

      <div className="z-10 w-full max-w-5xl space-y-8">
        <div className="text-center space-y-4">
          <h1 className="text-4xl md:text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-b from-neutral-50 to-neutral-400">
            Analysis History
          </h1>
          <p className="text-neutral-400 text-lg">
            View all your past AI investment memos and pipelines.
          </p>
        </div>

        <div className="bg-neutral-900/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-2xl">
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-16">
              <div className="text-6xl mb-4">📭</div>
              <h3 className="text-xl font-medium text-white mb-2">No History Found</h3>
              <p className="text-neutral-400 mb-6">You haven&apos;t run any analysis jobs yet.</p>
              <Link href="/" className="px-6 py-3 bg-white text-black font-semibold rounded-lg hover:bg-neutral-200 transition-colors">
                Run New Analysis
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/10 text-neutral-400 text-sm uppercase tracking-wider">
                    <th className="py-4 px-6 font-medium">Ticker</th>
                    <th className="py-4 px-6 font-medium">Job ID</th>
                    <th className="py-4 px-6 font-medium">Date</th>
                    <th className="py-4 px-6 font-medium">Status</th>
                    <th className="py-4 px-6 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {jobs.map((job) => (
                    <tr key={job.id} className="group hover:bg-white/[0.02] transition-colors">
                      <td className="py-4 px-6">
                        <div className="font-bold text-lg text-white">{job.ticker}</div>
                      </td>
                      <td className="py-4 px-6 text-sm text-neutral-500">
                        {job.id}
                      </td>
                      <td className="py-4 px-6 text-sm text-neutral-400">
                        {new Date(job.created_at).toLocaleString()}
                      </td>
                      <td className="py-4 px-6">
                        <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(job.status)}`}>
                          {job.status}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-right">
                        <Link
                          href={`/job/${job.id}`}
                          className="inline-flex items-center space-x-2 text-sm text-neutral-300 hover:text-emerald-400 transition-colors group-hover:underline"
                        >
                          <span>View Report</span>
                          <span>→</span>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
