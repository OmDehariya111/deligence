"use client";

import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { Users, FileText, Activity, Loader2, Star } from "lucide-react";
import { API_URL } from "@/lib/auth";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";

interface AdminStats {
  total_users: number;
  total_jobs: number;
  success_rate: string;
  activity: ActivityPoint[];
}

interface AdminUser {
  id: number;
  email: string;
  full_name: string | null;
  is_admin: boolean;
  is_active: number;
  tier: "FREE" | "PRO" | "ENTERPRISE";
  credits: number;
  created_at: string;
}

interface AdminJob {
  id: string;
  ticker: string;
  user_id: number | null;
  status: string;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
}

interface ActivityPoint {
  label: string;
  date: string;
  jobs: number;
}

// Dynamically import Recharts to reduce initial JS payload and prevent SSR hydration errors
const RechartsWrapper = dynamic(
  () => import('recharts').then((mod) => {
    const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } = mod;
    return function Chart({ data }: { data: ActivityPoint[] }) {
      return (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
            <XAxis dataKey="label" stroke="#888" tickLine={false} axisLine={false} />
            <YAxis stroke="#888" tickLine={false} axisLine={false} allowDecimals={false} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#111', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
              itemStyle={{ color: '#10b981' }}
            />
            <Line type="monotone" dataKey="jobs" stroke="#10b981" strokeWidth={3} dot={{ r: 4, fill: "#10b981", strokeWidth: 2, stroke: "#000" }} activeDot={{ r: 6 }} />
            <Line type="monotone" dataKey="signups" stroke="#818cf8" strokeWidth={2} dot={false} activeDot={{ r: 5 }} />
          </LineChart>
        </ResponsiveContainer>
      );
    };
  }), 
  { ssr: false, loading: () => <div className="w-full h-full animate-pulse bg-white/5 rounded-xl"></div> }
);

export default function AdminDashboard() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedModal, setSelectedModal] = useState<'users' | 'jobs' | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const chartData = stats?.activity ?? [];

  useEffect(() => {
    if (authLoading) return;
    
    if (!user || !user.is_admin) {
      router.push("/");
      return;
    }

    const fetchAdminData = async () => {
      try {
        const [statsRes, usersRes, jobsRes] = await Promise.all([
          fetch(`${API_URL}/admin/stats`, { credentials: "include" }),
          fetch(`${API_URL}/admin/users`, { credentials: "include" }),
          fetch(`${API_URL}/admin/jobs`, { credentials: "include" }),
        ]);

        if (statsRes.ok) setStats(await statsRes.json() as AdminStats);
        if (usersRes.ok) setUsers(await usersRes.json() as AdminUser[]);
        if (jobsRes.ok) setJobs(await jobsRes.json() as AdminJob[]);
      } catch (err) {
        console.error("Failed to fetch admin data", err);
      } finally {
        setLoading(false);
      }
    };

    fetchAdminData();
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!selectedModal) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedModal(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    window.setTimeout(() => dialogRef.current?.querySelector<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")?.focus(), 0);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [selectedModal]);

  const trapDialogFocus = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])"));
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center pt-16">
        <Loader2 className="animate-spin text-emerald-500" size={40} />
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 pb-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center space-x-3 mb-8">
          <Activity className="text-emerald-500" size={32} />
          <h1 className="text-3xl font-bold text-white">Admin Command Center</h1>
        </div>
        
        {/* Metric Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div 
            onClick={() => setSelectedModal('users')}
            onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedModal('users'); }}
            role="button"
            tabIndex={0}
            aria-label="View recent registered users"
            className="bg-white/5 border border-white/10 rounded-2xl p-6 relative overflow-hidden group hover:bg-white/10 transition-colors cursor-pointer hover:scale-105 duration-300"
          >
            <div className="absolute -right-4 -top-4 w-24 h-24 bg-blue-500/20 rounded-full blur-2xl group-hover:bg-blue-500/30 transition-all" />
            <div className="flex items-center justify-between mb-4 relative z-10">
              <h3 className="text-gray-400 font-medium">Total Users</h3>
              <Users className="text-blue-400" size={20} />
            </div>
            <p className="text-4xl font-bold text-white relative z-10">{stats?.total_users || 0}</p>
          </div>

          <div 
            onClick={() => setSelectedModal('jobs')}
            onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedModal('jobs'); }}
            role="button"
            tabIndex={0}
            aria-label="View recent platform jobs"
            className="bg-white/5 border border-white/10 rounded-2xl p-6 relative overflow-hidden group hover:bg-white/10 transition-colors cursor-pointer hover:scale-105 duration-300"
          >
            <div className="absolute -right-4 -top-4 w-24 h-24 bg-emerald-500/20 rounded-full blur-2xl group-hover:bg-emerald-500/30 transition-all" />
            <div className="flex items-center justify-between mb-4 relative z-10">
              <h3 className="text-gray-400 font-medium">Total Jobs Generated</h3>
              <FileText className="text-emerald-400" size={20} />
            </div>
            <p className="text-4xl font-bold text-white relative z-10">{stats?.total_jobs || 0}</p>
          </div>

          <div className="bg-white/5 border border-white/10 rounded-2xl p-6 relative overflow-hidden group hover:bg-white/10 transition-colors">
            <div className="absolute -right-4 -top-4 w-24 h-24 bg-purple-500/20 rounded-full blur-2xl group-hover:bg-purple-500/30 transition-all" />
            <div className="flex items-center justify-between mb-4 relative z-10">
              <h3 className="text-gray-400 font-medium">Success Rate</h3>
              <Activity className="text-purple-400" size={20} />
            </div>
            <p className="text-4xl font-bold text-white relative z-10">{stats?.success_rate || "0%"}</p>
          </div>
        </div>

        {/* Charts & Data */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Chart Section */}
          <div className="lg:col-span-2 bg-[#0a0a0a] border border-white/10 rounded-2xl p-6">
            <div className="mb-6 flex items-center justify-between gap-4">
              <h2 className="text-xl font-semibold text-white">7-Day Platform Activity</h2>
              <div className="flex gap-3 text-xs text-gray-400"><span><i className="mr-1 inline-block size-2 rounded-full bg-emerald-400" />Jobs</span><span><i className="mr-1 inline-block size-2 rounded-full bg-indigo-400" />Sign-ups</span></div>
            </div>
            <div className="h-72 w-full">
              <RechartsWrapper data={chartData} />
            </div>
          </div>

          {/* Recent Users List */}
          <div className="bg-[#0a0a0a] border border-white/10 rounded-2xl p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Recent Users</h2>
            <div className="space-y-4 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
              {users.map((u) => (
                <div key={u.id} className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/5">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white">
                      {(u.full_name || u.email).substring(0, 1).toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{u.full_name || "Unknown"}</p>
                      <p className="text-xs text-gray-500">{u.email}</p>
                    </div>
                  </div>
                  {u.is_admin && <Star size={14} className="text-emerald-500" />}
                </div>
              ))}
              {users.length === 0 && <p className="text-sm text-gray-500">No users found.</p>}
            </div>
          </div>
        </div>

        {/* Global Jobs Table */}
        <div className="mt-8 bg-[#0a0a0a] border border-white/10 rounded-2xl overflow-hidden">
          <div className="p-6 border-b border-white/10">
            <h2 className="text-xl font-semibold text-white">Recent Platform Jobs</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-400">
              <thead className="text-xs text-gray-500 uppercase bg-white/5">
                <tr>
                  <th className="px-6 py-4 font-medium">Job ID</th>
                  <th className="px-6 py-4 font-medium">Ticker</th>
                  <th className="px-6 py-4 font-medium">User ID</th>
                  <th className="px-6 py-4 font-medium">Status</th>
                  <th className="px-6 py-4 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                    <td className="px-6 py-4 font-mono text-xs">{job.id.substring(0, 20)}...</td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-1 bg-white/10 rounded-md font-medium text-white">{job.ticker}</span>
                    </td>
                    <td className="px-6 py-4">User #{job.user_id}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 rounded-md text-xs font-medium ${
                        job.status === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-400' :
                        job.status === 'FAILED' ? 'bg-red-500/20 text-red-400' :
                        'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {job.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {new Date(job.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
                {jobs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-gray-500">No jobs generated yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Modals */}
        {selectedModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div 
              className="absolute inset-0 bg-black/60 backdrop-blur-sm" 
              onClick={() => setSelectedModal(null)} 
            />
            <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="admin-modal-title" onKeyDown={trapDialogFocus} className="relative z-10 w-full max-w-6xl bg-[#0a0a0a] border border-white/10 rounded-2xl shadow-2xl flex flex-col max-h-[85vh] animate-in fade-in zoom-in-95 duration-200">
              <div className="flex items-center justify-between p-6 border-b border-white/10">
                <h2 id="admin-modal-title" className="text-2xl font-bold text-white">
                  {selectedModal === 'users' ? 'Recent Registered Users' : 'Recent Platform Jobs'}
                </h2>
                <button 
                  type="button"
                  onClick={() => setSelectedModal(null)}
                  className="p-2 text-gray-400 hover:text-white hover:bg-white/5 rounded-full transition-colors flex items-center justify-center"
                  aria-label="Close dialog"
                >
                  <span className="text-2xl leading-none">&times;</span>
                </button>
              </div>
              
              <div className="p-6 overflow-y-auto custom-scrollbar flex-1">
                {selectedModal === 'users' ? (
                  <table className="w-full text-left text-sm text-gray-400">
                    <thead className="text-xs text-gray-500 uppercase bg-white/5">
                      <tr>
                        <th className="px-6 py-4 font-medium">ID</th>
                        <th className="px-6 py-4 font-medium">Full Name</th>
                        <th className="px-6 py-4 font-medium">Email</th>
                        <th className="px-6 py-4 font-medium">Role</th>
                        <th className="px-6 py-4 font-medium">Tier</th>
                        <th className="px-6 py-4 font-medium">Credits</th>
                        <th className="px-6 py-4 font-medium">Status</th>
                        <th className="px-6 py-4 font-medium">Joined Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((u) => (
                        <tr key={u.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                          <td className="px-6 py-4">#{u.id}</td>
                          <td className="px-6 py-4 font-medium text-white">{u.full_name || "N/A"}</td>
                          <td className="px-6 py-4">{u.email}</td>
                          <td className="px-6 py-4">
                            {u.is_admin ? <span className="text-emerald-400 flex items-center space-x-1"><Star size={12}/> <span>Admin</span></span> : "User"}
                          </td>
                          <td className="px-6 py-4 font-medium">
                            {u.tier === 'PRO' ? <span className="text-blue-400">PRO</span> : u.tier === 'ENTERPRISE' ? <span className="text-purple-400">ENTERPRISE</span> : <span className="text-gray-400">FREE</span>}
                          </td>
                          <td className="px-6 py-4 font-mono">{u.credits}</td>
                          <td className="px-6 py-4">
                            {u.is_active !== 0 ? <span className="text-emerald-400">Active</span> : <span className="text-red-400">Inactive</span>}
                          </td>
                          <td className="px-6 py-4">{new Date(u.created_at).toLocaleString()}</td>
                        </tr>
                      ))}
                      {users.length === 0 && (
                        <tr><td colSpan={8} className="text-center py-8 text-gray-500">No users found</td></tr>
                      )}
                    </tbody>
                  </table>
                ) : (
                  <table className="w-full text-left text-sm text-gray-400">
                    <thead className="text-xs text-gray-500 uppercase bg-white/5">
                      <tr>
                        <th className="px-6 py-4 font-medium">Job ID</th>
                        <th className="px-6 py-4 font-medium">User ID</th>
                        <th className="px-6 py-4 font-medium">Ticker</th>
                        <th className="px-6 py-4 font-medium">Status</th>
                        <th className="px-6 py-4 font-medium">Started At</th>
                        <th className="px-6 py-4 font-medium">Completed At</th>
                        <th className="px-6 py-4 font-medium">Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {jobs.map((job) => (
                        <tr key={job.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                          <td className="px-6 py-4 font-mono text-xs" title={job.id}>{job.id.substring(0, 16)}...</td>
                          <td className="px-6 py-4">User #{job.user_id}</td>
                          <td className="px-6 py-4">
                            <span className="px-2 py-1 bg-white/10 rounded-md font-medium text-white">{job.ticker}</span>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`px-2 py-1 rounded-md text-xs font-medium ${
                              job.status === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-400' :
                              job.status === 'FAILED' ? 'bg-red-500/20 text-red-400' :
                              'bg-yellow-500/20 text-yellow-400'
                            }`}>
                              {job.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-xs">{new Date(job.created_at).toLocaleString()}</td>
                          <td className="px-6 py-4 text-xs">{job.completed_at ? new Date(job.completed_at).toLocaleString() : '-'}</td>
                          <td className="px-6 py-4 text-xs max-w-[150px] truncate text-red-400" title={job.error_message ?? undefined}>{job.error_message || '-'}</td>
                        </tr>
                      ))}
                      {jobs.length === 0 && (
                        <tr><td colSpan={7} className="text-center py-8 text-gray-500">No jobs found</td></tr>
                      )}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
