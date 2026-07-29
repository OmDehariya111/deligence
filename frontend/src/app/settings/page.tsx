"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { API_URL } from "@/lib/auth";
import { useAuth } from "@/components/providers/auth-provider";
import { User, Shield, CheckCircle2, AlertCircle } from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<"profile" | "security">("profile");
  
  // Profile State
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [email, setEmail] = useState(user?.email || "");
  
  // Security State
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  
  // Feedback State
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error", text: string } | null>(null);

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ full_name: fullName, email }),
      });
      if (!res.ok) throw new Error("Failed to update profile");
      setMessage({ type: "success", text: "Profile updated successfully" });
    } catch (err: any) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_URL}/auth/password`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      if (!res.ok) throw new Error("Failed to update password");
      setMessage({ type: "success", text: "Password updated successfully" });
      setCurrentPassword("");
      setNewPassword("");
    } catch (err: any) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-foreground p-6 md:p-12 relative overflow-hidden">
      {/* Background Glow */}
      <div className="absolute top-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-primary/10 blur-[120px] pointer-events-none" />
      
      <div className="max-w-4xl mx-auto relative z-10 grid grid-cols-1 md:grid-cols-4 gap-8">
        
        <div className="md:col-span-1">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            className="flex flex-col gap-2"
          >
            <h1 className="text-3xl font-bold mb-4">Settings</h1>
            <button 
              onClick={() => { setActiveTab("profile"); setMessage(null); }}
              className={`flex items-center gap-3 p-3 rounded-lg text-left transition-all ${
                activeTab === "profile" 
                  ? "bg-primary/10 text-primary border border-primary/30" 
                  : "hover:bg-white/5 text-muted-foreground border border-transparent"
              }`}
            >
              <User className="w-5 h-5" />
              <span className="font-medium">Profile</span>
            </button>
            <button 
              onClick={() => { setActiveTab("security"); setMessage(null); }}
              className={`flex items-center gap-3 p-3 rounded-lg text-left transition-all ${
                activeTab === "security" 
                  ? "bg-primary/10 text-primary border border-primary/30" 
                  : "hover:bg-white/5 text-muted-foreground border border-transparent"
              }`}
            >
              <Shield className="w-5 h-5" />
              <span className="font-medium">Security</span>
            </button>
          </motion.div>
        </div>

        <div className="md:col-span-3">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="glass rounded-xl p-8 border border-border"
          >
            {message && (
              <motion.div 
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className={`p-4 rounded-md mb-6 flex items-start gap-3 border ${
                  message.type === "success" 
                    ? "bg-primary/10 border-primary/30 text-primary" 
                    : "bg-[#ff5c5c]/10 border-[#ff5c5c]/30 text-[#ff5c5c]"
                }`}
              >
                {message.type === "success" ? <CheckCircle2 className="w-5 h-5 shrink-0" /> : <AlertCircle className="w-5 h-5 shrink-0" />}
                <p className="text-sm font-medium">{message.text}</p>
              </motion.div>
            )}

            {activeTab === "profile" ? (
              <div>
                <h2 className="text-2xl font-bold mb-6">Profile Information</h2>
                <form onSubmit={handleProfileUpdate} className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-muted-foreground mb-2">Full Name</label>
                    <input 
                      type="text" 
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full bg-background/60 border border-border rounded-md px-4 py-2.5 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-muted-foreground mb-2">Email Address</label>
                    <input 
                      type="email" 
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full bg-background/60 border border-border rounded-md px-4 py-2.5 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                    />
                  </div>
                  <div className="p-4 rounded-md border border-border bg-black/20 flex justify-between items-center">
                    <div>
                      <p className="text-sm font-medium text-muted-foreground mb-1">Account Tier</p>
                      <p className="font-mono text-primary">{user?.tier || "FREE"}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium text-muted-foreground mb-1">Credits</p>
                      <p className="font-mono">{user?.credits ?? 0}</p>
                    </div>
                  </div>
                  <button 
                    type="submit" 
                    disabled={loading}
                    className="px-6 py-2.5 rounded-md bg-primary text-primary-foreground font-medium neon-glow disabled:opacity-50 disabled:shadow-none"
                  >
                    {loading ? "Saving..." : "Save Changes"}
                  </button>
                </form>
              </div>
            ) : (
              <div>
                <h2 className="text-2xl font-bold mb-6">Security Settings</h2>
                <form onSubmit={handlePasswordUpdate} className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-muted-foreground mb-2">Current Password</label>
                    <input 
                      type="password" 
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      className="w-full bg-background/60 border border-border rounded-md px-4 py-2.5 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-muted-foreground mb-2">New Password</label>
                    <input 
                      type="password" 
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="w-full bg-background/60 border border-border rounded-md px-4 py-2.5 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                      required
                    />
                  </div>
                  <button 
                    type="submit" 
                    disabled={loading}
                    className="px-6 py-2.5 rounded-md bg-primary text-primary-foreground font-medium neon-glow disabled:opacity-50 disabled:shadow-none"
                  >
                    {loading ? "Updating..." : "Update Password"}
                  </button>
                </form>
              </div>
            )}
          </motion.div>
        </div>

      </div>
    </div>
  );
}
