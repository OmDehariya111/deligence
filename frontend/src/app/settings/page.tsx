"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { User, Lock, Sliders, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { API_URL } from "@/lib/auth";

export default function SettingsPage() {
  const { user, setUser } = useAuth();
  const [activeTab, setActiveTab] = useState("profile");

  // Profile Form State
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileMessage, setProfileMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Security Form State
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [securityLoading, setSecurityLoading] = useState(false);
  const [securityMessage, setSecurityMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Initialize fields when user loads
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (user) {
        setFullName(user.full_name || "");
        setEmail(user.email || "");
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [user]);

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileLoading(true);
    setProfileMessage(null);

    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: fullName, email }),
        credentials: "include",
      });

      if (res.ok) {
        const updatedUser = await res.json();
        setUser(updatedUser); // Update globally
        setProfileMessage({ type: "success", text: "Profile updated successfully!" });
      } else {
        const errorData = await res.json();
        setProfileMessage({ type: "error", text: errorData.detail || "Failed to update profile." });
      }
    } catch {
      setProfileMessage({ type: "error", text: "Network error occurred." });
    } finally {
      setProfileLoading(false);
    }
  };

  const handleSecuritySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSecurityLoading(true);
    setSecurityMessage(null);

    try {
      const res = await fetch(`${API_URL}/auth/password`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
        credentials: "include",
      });

      if (res.ok) {
        setSecurityMessage({ type: "success", text: "Password changed successfully!" });
        setCurrentPassword("");
        setNewPassword("");
      } else {
        const errorData = await res.json();
        setSecurityMessage({ type: "error", text: errorData.detail || "Failed to change password." });
      }
    } catch {
      setSecurityMessage({ type: "error", text: "Network error occurred." });
    } finally {
      setSecurityLoading(false);
    }
  };

  return (
    <div className="min-h-screen pt-24 pb-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold mb-8 text-white">Settings</h1>
        
        <div className="flex flex-col md:flex-row gap-8">
          
          {/* Sidebar */}
          <aside className="w-full md:w-64 flex-shrink-0">
            <nav className="flex flex-col space-y-1">
              <button
                onClick={() => setActiveTab("profile")}
                className={`flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                  activeTab === "profile" 
                    ? "bg-white/10 text-white font-medium border border-white/20" 
                    : "text-gray-400 hover:bg-white/5 hover:text-white"
                }`}
              >
                <User size={18} />
                <span>Profile</span>
              </button>
              
              <button
                onClick={() => setActiveTab("security")}
                className={`flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                  activeTab === "security" 
                    ? "bg-white/10 text-white font-medium border border-white/20" 
                    : "text-gray-400 hover:bg-white/5 hover:text-white"
                }`}
              >
                <Lock size={18} />
                <span>Security</span>
              </button>

              <button
                onClick={() => setActiveTab("preferences")}
                className={`flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                  activeTab === "preferences" 
                    ? "bg-white/10 text-white font-medium border border-white/20" 
                    : "text-gray-400 hover:bg-white/5 hover:text-white"
                }`}
              >
                <Sliders size={18} />
                <span>Preferences</span>
              </button>
            </nav>
          </aside>

          {/* Main Content Area */}
          <main className="flex-1">
            <div className="bg-[#0a0a0a] border border-white/10 rounded-2xl p-8 relative overflow-hidden group">
              {/* Background Glow */}
              <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[150%] h-[150%] opacity-20 pointer-events-none radial-gradient-glow transition-opacity duration-700" />
              
              <div className="relative z-10">
                {activeTab === "profile" && (
                  <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <h2 className="text-xl font-semibold text-white mb-2">Public Profile</h2>
                    <p className="text-gray-400 text-sm mb-6">Manage how you appear to others on the platform.</p>
                    
                    {profileMessage && (
                      <div className={`p-4 rounded-xl mb-6 flex items-center space-x-3 ${profileMessage.type === "success" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"}`}>
                        {profileMessage.type === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                        <span className="text-sm font-medium">{profileMessage.text}</span>
                      </div>
                    )}

                    <form onSubmit={handleProfileSubmit} className="space-y-5">
                      <div>
                        <label htmlFor="settings-name" className="block text-sm font-medium text-gray-300 mb-2">Full Name</label>
                        <input 
                          id="settings-name"
                          type="text" 
                          value={fullName}
                          onChange={(e) => setFullName(e.target.value)}
                          className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
                          placeholder="Your full name"
                          required
                        />
                      </div>
                      <div>
                        <label htmlFor="settings-email" className="block text-sm font-medium text-gray-300 mb-2">Email Address</label>
                        <input 
                          id="settings-email"
                          type="email" 
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
                          placeholder="you@example.com"
                          required
                        />
                      </div>
                      
                      <div className="pt-4 flex justify-end">
                        <button 
                          type="submit" 
                          disabled={profileLoading}
                          className="px-6 py-3 bg-white text-black font-medium rounded-xl hover:bg-gray-200 transition-colors flex items-center space-x-2 disabled:opacity-50"
                        >
                          {profileLoading ? <Loader2 size={18} className="animate-spin" /> : null}
                          <span>Save Changes</span>
                        </button>
                      </div>
                    </form>
                  </div>
                )}

                {activeTab === "security" && (
                  <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <h2 className="text-xl font-semibold text-white mb-2">Security Settings</h2>
                    <p className="text-gray-400 text-sm mb-6">Update your password and secure your account.</p>
                    
                    {securityMessage && (
                      <div className={`p-4 rounded-xl mb-6 flex items-center space-x-3 ${securityMessage.type === "success" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"}`}>
                        {securityMessage.type === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                        <span className="text-sm font-medium">{securityMessage.text}</span>
                      </div>
                    )}

                    <form onSubmit={handleSecuritySubmit} className="space-y-5">
                      <div>
                        <label htmlFor="settings-current-password" className="block text-sm font-medium text-gray-300 mb-2">Current Password</label>
                        <input 
                          id="settings-current-password"
                          type="password" 
                          value={currentPassword}
                          onChange={(e) => setCurrentPassword(e.target.value)}
                          className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                          placeholder="Enter current password"
                          required
                        />
                      </div>
                      <div>
                        <label htmlFor="settings-new-password" className="block text-sm font-medium text-gray-300 mb-2">New Password</label>
                        <input 
                          id="settings-new-password"
                          type="password" 
                          value={newPassword}
                          onChange={(e) => setNewPassword(e.target.value)}
                          className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                          placeholder="Enter new password"
                          required
                          minLength={8}
                        />
                      </div>
                      
                      <div className="pt-4 flex justify-end">
                        <button 
                          type="submit" 
                          disabled={securityLoading}
                          className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl transition-colors flex items-center space-x-2 disabled:opacity-50"
                        >
                          {securityLoading ? <Loader2 size={18} className="animate-spin" /> : <Lock size={18} />}
                          <span>Update Password</span>
                        </button>
                      </div>
                    </form>
                  </div>
                )}

                {activeTab === "preferences" && (
                  <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <h2 className="text-xl font-semibold text-white mb-2">Preferences</h2>
                    <p className="text-gray-400 text-sm mb-6">Customize your platform experience.</p>
                    
                    <div className="space-y-6">
                      <div className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/10">
                        <div>
                          <h3 className="text-white font-medium">Email Notifications</h3>
                          <p className="text-gray-400 text-sm">Receive alerts when a memo is fully generated.</p>
                        </div>
                        <div className="w-12 h-6 bg-emerald-500 rounded-full relative cursor-pointer">
                          <div className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full"></div>
                        </div>
                      </div>

                      <div className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/10">
                        <div>
                          <h3 className="text-white font-medium">Dark Mode</h3>
                          <p className="text-gray-400 text-sm">You are currently using the default dark theme.</p>
                        </div>
                        <div className="w-12 h-6 bg-emerald-500 rounded-full relative cursor-pointer opacity-50 cursor-not-allowed">
                          <div className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full"></div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </main>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .radial-gradient-glow {
          background: radial-gradient(circle at 50% 0%, rgba(16, 185, 129, 0.15), transparent 70%);
        }
      `}} />
    </div>
  );
}
