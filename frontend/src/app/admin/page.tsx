"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { API_URL } from "@/lib/auth";
import { useAuth } from "@/components/providers/auth-provider";
import { Users, FileStack, Activity, Loader2, ShieldAlert } from "lucide-react";

interface AdminStats {
  total_users: number;
  total_jobs: number;
  success_rate: number;
}

interface UserData {
  id: string;
  email: string;
  full_name: string;
  tier: string;
  credits: number;
  is_admin: boolean;
}

export default function AdminPage() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<UserData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!authLoading && (!user || !user.is_admin)) {
      router.push("/dashboard");
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    async function fetchAdminData() {
      if (!user?.is_admin) return;
      try {
        const [statsRes, usersRes] = await Promise.all([
          fetch(`${API_URL}/admin/stats`, { credentials: "include" }),
          fetch(`${API_URL}/admin/users`, { credentials: "include" })
        ]);

        if (!statsRes.ok || !usersRes.ok) throw new Error("Failed to fetch admin data");
        
        const statsData = await statsRes.json();
        const usersData = await usersRes.json();
        
        setStats(statsData);
        setUsers(usersData);
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

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-foreground p-6 md:p-12 relative overflow-hidden">
      {/* Background Glow */}
      <div className="absolute top-[20%] left-[30%] w-[40%] h-[40%] rounded-full bg-primary/5 blur-[150px] pointer-events-none" />
      
      <div className="max-w-6xl mx-auto relative z-10">
        <div className="flex items-center gap-3 mb-8">
          <ShieldAlert className="w-8 h-8 text-primary" />
          <h1 className="text-4xl font-bold">Admin <span className="text-gradient-neon">Panel</span></h1>
        </div>

        {error ? (
          <div className="p-4 bg-[#ff5c5c]/10 border border-[#ff5c5c]/30 text-[#ff5c5c] rounded-md mb-8">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
          </div>
        ) : (
          <>
            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className="glass rounded-xl p-6 border border-border border-t-primary/30 flex items-center gap-4"
              >
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                  <Users className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground font-medium">Total Users</p>
                  <p className="text-2xl font-bold font-mono">{stats?.total_users || 0}</p>
                </div>
              </motion.div>
              
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.1 }}
                className="glass rounded-xl p-6 border border-border border-t-primary/30 flex items-center gap-4"
              >
                <div className="w-12 h-12 rounded-full bg-blue-500/10 flex items-center justify-center shrink-0">
                  <FileStack className="w-6 h-6 text-blue-500" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground font-medium">Total Jobs</p>
                  <p className="text-2xl font-bold font-mono">{stats?.total_jobs || 0}</p>
                </div>
              </motion.div>
              
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.2 }}
                className="glass rounded-xl p-6 border border-border border-t-primary/30 flex items-center gap-4"
              >
                <div className="w-12 h-12 rounded-full bg-purple-500/10 flex items-center justify-center shrink-0">
                  <Activity className="w-6 h-6 text-purple-500" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground font-medium">Success Rate</p>
                  <p className="text-2xl font-bold font-mono">{stats?.success_rate ? `${stats.success_rate.toFixed(1)}%` : "0%"}</p>
                </div>
              </motion.div>
            </div>

            {/* Users Table */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="glass rounded-xl p-6 border border-border"
            >
              <h2 className="text-xl font-bold mb-6">User Management</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
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
                    {users.map((u) => (
                      <tr key={u.id} className="hover:bg-white/[0.02] transition-colors">
                        <td className="py-4 pl-2 font-mono text-xs text-muted-foreground">
                          {u.id.substring(0, 8)}...
                        </td>
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
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>
          </>
        )}
      </div>
    </div>
  );
}
