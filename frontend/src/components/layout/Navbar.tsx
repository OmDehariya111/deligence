"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/auth-provider";
import { LogOut, User, Settings, Star, Coins, Zap, Menu, X } from "lucide-react";

export default function Navbar() {
  const { user, logout, isLoading } = useAuth();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  const closeMobileMenu = () => setMobileOpen(false);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/10 bg-black/50 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-8">
            <Link href="/" className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
              DeligenX AI
            </Link>
            <div className="hidden md:flex space-x-4">
              <Link href="/" className="text-sm text-gray-300 hover:text-white transition-colors px-3 py-2 rounded-md hover:bg-white/5">
                New Analysis
              </Link>
              <Link href="/history" className="text-sm text-gray-300 hover:text-white transition-colors px-3 py-2 rounded-md hover:bg-white/5">
                History
              </Link>
            </div>
          </div>

          <div className="hidden md:flex items-center space-x-4">
            {!isLoading && (
              <>
                {user ? (
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-2 text-sm text-gray-300">
                      <User size={16} />
                      <span className="hidden sm:inline">{user.full_name || user.email}</span>
                    </div>
                    
                    <div className="flex items-center space-x-1 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm font-medium">
                      <Coins size={14} className="animate-pulse" />
                      <span>{user.credits ?? 0} Credits</span>
                    </div>

                    <Link href="/pricing" className="text-sm bg-gradient-to-r from-purple-500 to-indigo-600 text-white hover:opacity-90 transition-opacity px-3 py-1.5 rounded-full font-medium flex items-center space-x-1 shadow-lg shadow-purple-500/20">
                      <Zap size={14} />
                      <span className="hidden sm:inline">Upgrade</span>
                    </Link>
                    {user.is_admin && (
                      <Link href="/admin" className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors px-3 py-2 rounded-md hover:bg-emerald-500/10 flex items-center space-x-2 border border-emerald-500/20">
                        <Star size={16} />
                        <span className="hidden sm:inline">Admin</span>
                      </Link>
                    )}
                    <Link href="/settings" className="text-sm text-gray-300 hover:text-white transition-colors px-3 py-2 rounded-md hover:bg-white/5 flex items-center space-x-2">
                      <Settings size={16} />
                      <span className="hidden sm:inline">Settings</span>
                    </Link>
                    <button type="button"
                      onClick={logout}
                      className="text-sm text-gray-300 hover:text-red-400 transition-colors px-3 py-2 rounded-md hover:bg-white/5 flex items-center space-x-2"
                    >
                      <LogOut size={16} />
                      <span className="hidden sm:inline">Logout</span>
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center space-x-4">
                    <button type="button"
                      onClick={() => router.push("/login")}
                      className="text-sm text-gray-300 hover:text-white transition-colors px-3 py-2 rounded-md hover:bg-white/5 cursor-pointer"
                    >
                      Login
                    </button>
                    <button type="button"
                      onClick={() => router.push("/signup")}
                      className="text-sm bg-white text-black hover:bg-gray-200 transition-colors px-4 py-2 rounded-md font-medium cursor-pointer"
                    >
                      Sign Up
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
          <button
            type="button"
            onClick={() => setMobileOpen((open) => !open)}
            className="inline-flex size-10 items-center justify-center rounded-lg text-gray-200 hover:bg-white/10 md:hidden"
            aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
        {mobileOpen && (
          <div className="border-t border-white/10 py-3 md:hidden">
            <div className="flex flex-col gap-1">
              <Link onClick={closeMobileMenu} href="/" className="rounded-lg px-3 py-2 text-sm text-gray-200 hover:bg-white/10">New Analysis</Link>
              {user && <Link onClick={closeMobileMenu} href="/history" className="rounded-lg px-3 py-2 text-sm text-gray-200 hover:bg-white/10">History</Link>}
              {user ? (
                <>
                  <div className="mx-3 my-2 rounded-lg border border-blue-400/20 bg-blue-500/10 px-3 py-2 text-sm text-blue-200">{user.credits ?? 0} credits</div>
                  <Link onClick={closeMobileMenu} href="/pricing" className="rounded-lg px-3 py-2 text-sm text-indigo-200 hover:bg-white/10">Upgrade plan</Link>
                  <Link onClick={closeMobileMenu} href="/settings" className="rounded-lg px-3 py-2 text-sm text-gray-200 hover:bg-white/10">Settings</Link>
                  {user.is_admin && <Link onClick={closeMobileMenu} href="/admin" className="rounded-lg px-3 py-2 text-sm text-emerald-300 hover:bg-white/10">Admin</Link>}
                  <button type="button" onClick={logout} className="rounded-lg px-3 py-2 text-left text-sm text-red-300 hover:bg-white/10">Log out</button>
                </>
              ) : (
                <>
                  <Link onClick={closeMobileMenu} href="/login" className="rounded-lg px-3 py-2 text-sm text-gray-200 hover:bg-white/10">Log in</Link>
                  <Link onClick={closeMobileMenu} href="/signup" className="rounded-lg bg-white px-3 py-2 text-sm font-medium text-black">Create account</Link>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
