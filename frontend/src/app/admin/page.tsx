"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { API_URL } from "@/lib/auth";
import { useAuth } from "@/components/providers/auth-provider";
import { Users, FileStack, Activity, Loader2, ShieldAlert, CheckCircle2, XCircle, Clock, CalendarDays } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";

interface AdminStats {
  total_users: number;
  total_jobs: number;
  success_rate: string;
  activity: { date: string; label: string; jobs: number; signups: number }[];
}

interface UserData {
  id: number;
  email: string;
  full_name: string;
  tier: string;
  credits: number;
  is_admin: boolean;
  created_at: string;
}

interface JobData {
  id: string;
  ticker: string;
  user_id: number;
  status: string;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export default function AdminPage() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<UserData[]>([]);
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  
  const [activeTab, setActiveTab] = useState<"users" | "jobs">("users");

  useEffect(() => {
    if (!authLoading && (!user || !user.is_admin)) {
      router.push("/dashboard");
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    async function fetchAdminData() {
      if (!user?.is_admin) return;
      try {
        const [statsRes, usersRes, jobsRes] = await Promise.all([
          fetch(`${API_URL}/admin/stats`, { credentials: "include" }),
          fetch(`${API_URL}/admin/users`, { credentials: "include" }),
          fetch(`${API_URL}/admin/jobs`, { credentials: "include" })
        ]);

        if (!statsRes.ok || !usersRes.ok || !jobsRes.ok) {
          throw new Error("Failed to fetch admin data");
        }
        
        const statsData = await statsRes.json();
        const usersData = await usersRes.json();
        const jobsData = await jobsRes.json();
        
        setStats(statsData);
        setUsers(usersData);
        setJobs(jobsData);
      } catch (err: any) {
        setError(err.message || "Admin fetch error");
      } finally {
        setLoading(false);
      }
    }
    
    if (!authLoading && user?.is_admin) {
      fetchAdminData();
    }
  }, [user, authLoading]);

  if (authLoading || (user && !user.is_admin)) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  // Helper for formatting dates
  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-foreground p-6 md:p-12 relative overflow-hidden">
      {/* Background Glow */}
      <div className="absolute top-[20%] left-[30%] w-[40%] h-[40%] rounded-full bg-primary/5 blur-[150px] pointer-events-none" />
      
      <div className="max-w-6xl mx-auto relative z-10">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-8 h-8 text-primary" />
            <h1 className="text-4xl font-bold">Admin <span className="text-gradient-neon">Panel</span></h1>
          </div>
        </div>

        {error ? (
          <div className="p-4 bg-[#ff5c5c]/10 border border-[#ff5c5c]/30 text-[#ff5c5c] rounded-md mb-8">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="flex flex-col items-center justify-center py-32">
            <Loader2 className="w-10 h-10 animate-spin text-primary mb-4" />
            <p className="text-muted-foreground font-mono text-sm uppercase tracking-widest">Loading Dashboard</p>
          </div>
        ) : (
          <>
            {/* Stats Cards (Clickable Tabs) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
              <motion.div
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setActiveTab("users")}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className={cn(
                  "cursor-pointer rounded-xl p-6 border flex items-center gap-4 transition-colors duration-300",
                  activeTab === "users" 
                    ? "bg-primary/5 border-primary shadow-[0_0_30px_rgba(57,255,136,0.15)]" 
                    : "glass border-border border-t-primary/30 hover:bg-white/[0.02]"
                )}
              >
                <div className={cn("w-12 h-12 rounded-full flex items-center justify-center shrink-0 transition-colors", activeTab === "users" ? "bg-primary/20 text-primary" : "bg-primary/10 text-primary")}>
                  <Users className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground font-medium">Total Users</p>
                  <p className="text-3xl font-bold font-mono">{stats?.total_users || 0}</p>
                </div>
              </motion.div>
              
              <motion.div
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setActiveTab("jobs")}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.1 }}
                className={cn(
                  "cursor-pointer rounded-xl p-6 border flex items-center gap-4 transition-colors duration-300",
                  activeTab === "jobs" 
                    ? "bg-blue-500/5 border-blue-500 shadow-[0_0_30px_rgba(59,130,246,0.15)]" 
                    : "glass border-border border-t-blue-500/30 hover:bg-white/[0.02]"
                )}
              >
                <div className={cn("w-12 h-12 rounded-full flex items-center justify-center shrink-0 transition-colors", activeTab === "jobs" ? "bg-blue-500/20 text-blue-500" : "bg-blue-500/10 text-blue-500")}>
                  <FileStack className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground font-medium">Total Jobs</p>
                  <p className="text-3xl font-bold font-mono">{stats?.total_jobs || 0}</p>
                </div>
              </motion.div>
              
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.2 }}
                className="glass rounded-xl p-6 border border-border border-t-purple-500/30 flex items-center gap-4"
              >
                <div className="w-12 h-12 rounded-full bg-purple-500/10 flex items-center justify-center shrink-0">
                  <Activity className="w-6 h-6 text-purple-500" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground font-medium">Platform Success Rate</p>
                  <p className="text-3xl font-bold font-mono">{stats?.success_rate || "0%"}</p>
                </div>
              </motion.div>
            </div>

            {/* Activity Graph */}
            {stats?.activity && stats.activity.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.3 }}
                className="glass rounded-xl p-6 border border-border mb-10"
              >
                <div className="flex items-center gap-2 mb-6">
                  <CalendarDays className="w-5 h-5 text-muted-foreground" />
                  <h2 className="text-xl font-bold">7-Day Activity</h2>
                </div>
                <div className="h-[300px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={stats.activity} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorJobs" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorSignups" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#39ff88" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#39ff88" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                      <XAxis 
                        dataKey="label" 
                        stroke="rgba(255,255,255,0.3)" 
                        fontSize={12} 
                        tickLine={false}
                        axisLine={false}
                        dy={10}
                      />
                      <YAxis 
                        stroke="rgba(255,255,255,0.3)" 
                        fontSize={12} 
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip 
                        contentStyle={{ 
                          backgroundColor: 'rgba(10, 10, 10, 0.9)', 
                          border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: '8px',
                          color: '#fff'
                        }} 
                      />
                      <Area type="monotone" dataKey="jobs" name="Jobs Run" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorJobs)" />
                      <Area type="monotone" dataKey="signups" name="New Users" stroke="#39ff88" strokeWidth={2} fillOpacity={1} fill="url(#colorSignups)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* Main Content Area (Tabs) */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.4 }}
              className="glass rounded-xl border border-border overflow-hidden min-h-[400px]"
            >
              {/* Tab Headers */}
              <div className="flex items-center border-b border-border/50 bg-white/[0.01]">
                <button
                  onClick={() => setActiveTab("users")}
                  className={cn(
                    "px-6 py-4 font-semibold text-sm transition-colors border-b-2",
                    activeTab === "users" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-white"
                  )}
                >
                  User Management
                </button>
                <button
                  onClick={() => setActiveTab("jobs")}
                  className={cn(
                    "px-6 py-4 font-semibold text-sm transition-colors border-b-2",
                    activeTab === "jobs" ? "border-blue-500 text-blue-500" : "border-transparent text-muted-foreground hover:text-white"
                  )}
                >
                  Job History
                </button>
              </div>

              <div className="p-6 overflow-x-auto">
                <AnimatePresence mode="wait">
                  {activeTab === "users" && (
                    <motion.div
                      key="users"
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 10 }}
                      transition={{ duration: 0.2 }}
                    >
                      <table className="w-full text-left border-collapse min-w-[600px]">
                        <thead>
                          <tr className="border-b border-border/50 text-muted-foreground text-sm font-medium">
                            <th className="pb-4 pl-2">ID</th>
                            <th className="pb-4">Name</th>
                            <th className="pb-4">Email</th>
                            <th className="pb-4">Tier</th>
                            <th className="pb-4 text-right pr-2">Credits</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/30">
                          {users.length === 0 ? (
                            <tr><td colSpan={5} className="py-8 text-center text-muted-foreground">No users found.</td></tr>
                          ) : (
                            users.map((u) => (
                              <tr key={u.id} className="hover:bg-white/[0.02] transition-colors">
                                <td className="py-4 pl-2 font-mono text-xs text-muted-foreground">#{u.id}</td>
                                <td className="py-4 font-medium flex items-center gap-2">
                                  {u.full_name}
                                  {u.is_admin && (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-bold bg-primary/20 text-primary border border-primary/30">
                                      Admin
                                    </span>
                                  )}
                                </td>
                                <td className="py-4 text-sm text-muted-foreground">{u.email}</td>
                                <td className="py-4 text-sm">
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-white/5 border border-border">
                                    {u.tier}
                                  </span>
                                </td>
                                <td className="py-4 text-right pr-2 font-mono">{u.credits}</td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </motion.div>
                  )}

                  {activeTab === "jobs" && (
                    <motion.div
                      key="jobs"
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 10 }}
                      transition={{ duration: 0.2 }}
                    >
                      <table className="w-full text-left border-collapse min-w-[700px]">
                        <thead>
                          <tr className="border-b border-border/50 text-muted-foreground text-sm font-medium">
                            <th className="pb-4 pl-2">Job ID</th>
                            <th className="pb-4">Ticker</th>
                            <th className="pb-4">User ID</th>
                            <th className="pb-4">Status</th>
                            <th className="pb-4 text-right pr-2">Created</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/30">
                          {jobs.length === 0 ? (
                            <tr><td colSpan={5} className="py-8 text-center text-muted-foreground">No jobs run yet.</td></tr>
                          ) : (
                            jobs.map((j) => (
                              <tr key={j.id} className="hover:bg-white/[0.02] transition-colors">
                                <td className="py-4 pl-2 font-mono text-xs text-muted-foreground">
                                  {j.id.substring(0, 8)}...
                                </td>
                                <td className="py-4 font-bold tracking-wider">{j.ticker}</td>
                                <td className="py-4 text-sm text-muted-foreground font-mono">#{j.user_id}</td>
                                <td className="py-4">
                                  <div className="flex items-center gap-1.5">
                                    {j.status === "COMPLETED" && <CheckCircle2 className="w-4 h-4 text-primary" />}
                                    {j.status === "FAILED" && <XCircle className="w-4 h-4 text-risk" />}
                                    {j.status === "RUNNING" && <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />}
                                    {(j.status === "PENDING" || j.status === "QUEUED") && <Clock className="w-4 h-4 text-yellow-400" />}
                                    
                                    <span className={cn(
                                      "text-xs font-semibold uppercase tracking-wider",
                                      j.status === "COMPLETED" && "text-primary",
                                      j.status === "FAILED" && "text-risk",
                                      j.status === "RUNNING" && "text-blue-400",
                                      (j.status === "PENDING" || j.status === "QUEUED") && "text-yellow-400"
                                    )}>
                                      {j.status}
                                    </span>
                                  </div>
                                </td>
                                <td className="py-4 text-right pr-2 text-xs text-muted-foreground">
                                  {formatDate(j.created_at)}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          </>
        )}
      </div>
    </div>
  );
}
