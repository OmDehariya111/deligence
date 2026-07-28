"use client";

import React, { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/providers/auth-provider";
import { Check, Loader2, Sparkles, Zap, Shield, Crown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import { API_URL } from "@/lib/auth";

function PricingContent() {
  const router = useRouter();
  const { user, isLoading: authLoading, refreshUser } = useAuth();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState<string | null>(null);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const paymentMessage = searchParams.get("success") === "1"
    ? "Payment completed. Your credits and plan have been refreshed."
    : searchParams.get("canceled") === "1"
      ? "Checkout was canceled. No changes were made to your plan."
      : null;

  React.useEffect(() => {
    if (searchParams.get("success") === "1") {
      const timer = window.setTimeout(() => void refreshUser(), 0);
      return () => window.clearTimeout(timer);
    }
  }, [refreshUser, searchParams]);

  const handleCheckout = async (tier: string) => {
    if (!user) {
      router.push("/login?next=/pricing");
      return;
    }
    setLoading(tier);
    try {
      const res = await fetch(`${API_URL}/payments/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier }),
        credentials: "include"
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.url) {
        throw new Error(data.detail || "Unable to start checkout. Please try again.");
      }
      window.location.assign(data.url);
    } catch (err) {
      setCheckoutError(err instanceof Error ? err.message : "Unable to start checkout. Please try again.");
    } finally {
      setLoading(null);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center pt-16">
        <Loader2 className="animate-spin text-indigo-500" size={40} />
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 pb-20 px-4 flex flex-col items-center bg-black overflow-hidden relative selection:bg-indigo-500/30">
      
      {/* Background Gradients */}
      <div className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] bg-indigo-600/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] bg-purple-600/20 rounded-full blur-[120px] pointer-events-none" />

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center z-10 mb-16"
      >
        <div className="inline-flex items-center space-x-2 px-4 py-2 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 font-medium text-sm mb-6">
          <Sparkles size={16} />
          <span>Upgrade Your Intelligence</span>
        </div>
        <h1 className="text-5xl md:text-7xl font-extrabold text-white tracking-tight mb-6">
          Pricing that scales with you.
        </h1>
        <p className="text-lg text-gray-400 max-w-2xl mx-auto">
          Unleash the full power of autonomous due diligence. From occasional reports to enterprise-grade AI swarms.
        </p>
      </motion.div>

      {(checkoutError || paymentMessage) && (
        <div role="status" className="z-10 mb-8 max-w-2xl rounded-xl border border-indigo-400/30 bg-indigo-500/10 px-5 py-3 text-center text-sm text-indigo-100">
          {checkoutError || paymentMessage}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl w-full z-10 relative">
        
        {/* FREE TIER */}
        <motion.div 
          initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="bg-white/5 border border-white/10 rounded-3xl p-8 flex flex-col backdrop-blur-xl relative overflow-hidden group hover:border-white/20 transition-all"
        >
          <div className="mb-8">
            <h3 className="text-xl font-bold text-gray-300 mb-2">Explorer</h3>
            <div className="flex items-end space-x-1 mb-4">
              <span className="text-5xl font-extrabold text-white">$0</span>
              <span className="text-gray-500 mb-1">/ forever</span>
            </div>
            <p className="text-sm text-gray-400">Perfect to test the waters and generate your first reports.</p>
          </div>
          <div className="flex-1 space-y-4 mb-8">
            <div className="flex items-center space-x-3 text-sm text-gray-300"><Check size={18} className="text-emerald-400" /><span>5 Free Credits on Sign Up</span></div>
            <div className="flex items-center space-x-3 text-sm text-gray-300"><Check size={18} className="text-emerald-400" /><span>Basic SEC Filings Search</span></div>
            <div className="flex items-center space-x-3 text-sm text-gray-300"><Check size={18} className="text-emerald-400" /><span>Standard Processing Speed</span></div>
          </div>
          <Button 
            disabled
            className="w-full bg-white/10 text-gray-300 hover:bg-white/20 border border-white/10 rounded-xl h-12 font-medium"
          >
            {user?.tier === "FREE" ? "Current Plan" : "Included"}
          </Button>
        </motion.div>

        {/* PRO TIER */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2 }}
          className="bg-gradient-to-b from-indigo-900/40 to-purple-900/10 border-2 border-indigo-500/50 rounded-3xl p-8 flex flex-col backdrop-blur-xl relative overflow-hidden shadow-[0_0_50px_-15px_rgba(99,102,241,0.4)] transform hover:-translate-y-2 transition-transform duration-300"
        >
          <div className="absolute top-0 left-1/2 -translate-x-1/2 bg-indigo-500 text-white text-xs font-bold px-3 py-1 rounded-b-lg">MOST POPULAR</div>
          <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-500/30 blur-[50px] rounded-full pointer-events-none" />
          
          <div className="mb-8 relative z-10">
            <h3 className="text-xl font-bold text-indigo-400 mb-2 flex items-center space-x-2"><Zap size={20} /><span>Professional</span></h3>
            <div className="flex items-end space-x-1 mb-4">
              <span className="text-5xl font-extrabold text-white">$29</span>
              <span className="text-gray-400 mb-1">/ month</span>
            </div>
            <p className="text-sm text-indigo-200/70">For analysts needing deep dives and fast results.</p>
          </div>
          <div className="flex-1 space-y-4 mb-8 relative z-10">
            <div className="flex items-center space-x-3 text-sm text-white"><Check size={18} className="text-indigo-400" /><span>50 Credits per Month</span></div>
            <div className="flex items-center space-x-3 text-sm text-white"><Check size={18} className="text-indigo-400" /><span>Deep Fundamental Analysis</span></div>
            <div className="flex items-center space-x-3 text-sm text-white"><Check size={18} className="text-indigo-400" /><span>Priority GPU Processing</span></div>
            <div className="flex items-center space-x-3 text-sm text-white"><Check size={18} className="text-indigo-400" /><span>High-res PDF Exports</span></div>
          </div>
          <Button 
            onClick={() => handleCheckout("PRO")}
            disabled={loading === "PRO" || user?.tier === "PRO" || user?.tier === "ENTERPRISE"}
            className="w-full bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl h-12 font-bold shadow-lg shadow-indigo-500/25 transition-all relative z-10"
          >
            {loading === "PRO" ? <Loader2 className="animate-spin" /> : user?.tier === "PRO" ? "Current Plan" : "Upgrade to Pro"}
          </Button>
        </motion.div>

        {/* ENTERPRISE TIER */}
        <motion.div 
          initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="bg-white/5 border border-white/10 rounded-3xl p-8 flex flex-col backdrop-blur-xl relative overflow-hidden group hover:border-white/20 transition-all"
        >
          <div className="mb-8">
            <h3 className="text-xl font-bold text-purple-400 mb-2 flex items-center space-x-2"><Crown size={20} /><span>Enterprise</span></h3>
            <div className="flex items-end space-x-1 mb-4">
              <span className="text-5xl font-extrabold text-white">$99</span>
              <span className="text-gray-500 mb-1">/ month</span>
            </div>
            <p className="text-sm text-gray-400">Unlimited power for hedge funds and large teams.</p>
          </div>
          <div className="flex-1 space-y-4 mb-8">
            <div className="flex items-center space-x-3 text-sm text-gray-300"><Check size={18} className="text-purple-400" /><span>500 Credits per Month</span></div>
            <div className="flex items-center space-x-3 text-sm text-gray-300"><Check size={18} className="text-purple-400" /><span>Custom Agent Instructions</span></div>
            <div className="flex items-center space-x-3 text-sm text-gray-300"><Check size={18} className="text-purple-400" /><span>Dedicated Support Line</span></div>
            <div className="flex items-center space-x-3 text-sm text-gray-300"><Shield size={18} className="text-purple-400" /><span>Bank-grade Security</span></div>
          </div>
          <Button 
            onClick={() => handleCheckout("ENTERPRISE")}
            disabled={loading === "ENTERPRISE" || user?.tier === "ENTERPRISE"}
            className="w-full bg-white text-black hover:bg-gray-200 rounded-xl h-12 font-bold transition-all"
          >
            {loading === "ENTERPRISE" ? <Loader2 className="animate-spin" /> : user?.tier === "ENTERPRISE" ? "Current Plan" : "Upgrade to Enterprise"}
          </Button>
        </motion.div>

      </div>
    </div>
  );
}

export default function PricingPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-black" />}>
      <PricingContent />
    </Suspense>
  );
}
