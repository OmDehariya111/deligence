"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { Menu, X, ArrowRight, LayoutDashboard, LogOut, Settings, History, User as UserIcon, ShieldAlert } from "lucide-react";
import { Logo } from "./Logo";
import { useAuth } from "@/components/providers/auth-provider";

const links = [
  { label: "Product", href: "/#product" },
  { label: "How It Works", href: "/#pipeline" },
  { label: "Pricing", href: "/#pricing" },
  { label: "About", href: "/#about" },
];

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const { user, isLoading, logout } = useAuth();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close user menu when clicking outside
  useEffect(() => {
    if (!userMenuOpen) return;
    const handleClick = () => setUserMenuOpen(false);
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, [userMenuOpen]);

  return (
    <>
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${
          scrolled
            ? "border-b border-[rgba(57,255,136,0.14)] bg-[rgba(10,10,10,0.72)] backdrop-blur-xl backdrop-saturate-150"
            : "border-b border-transparent bg-transparent"
        }`}
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 md:px-8">
          <Link href="/" className="flex items-center">
            <Logo />
          </Link>

          <nav className="hidden items-center gap-8 md:flex">
            {links.map((l) => (
              <a
                key={l.label}
                href={l.href}
                className="text-[13px] font-medium text-muted-foreground transition-colors duration-200 hover:text-foreground"
              >
                {l.label}
              </a>
            ))}
            <Link
              href="/demo"
              className="text-[13px] font-medium text-muted-foreground transition-colors duration-200 hover:text-foreground"
            >
              Live Demo
            </Link>
          </nav>

          <div className="hidden items-center gap-3 md:flex">
            {!isLoading && user ? (
              /* ── Logged-in: Dashboard + User Menu ── */
              <>
                {user.is_admin && (
                  <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className="group relative">
                    <div className="absolute inset-0 bg-gradient-to-r from-purple-500 to-[#ff5c5c] blur opacity-40 group-hover:opacity-100 transition-opacity duration-500 rounded-md"></div>
                    <Link
                      href="/admin"
                      className="relative flex items-center gap-1.5 rounded-md border border-purple-500/50 bg-[#0a0a0a] px-3.5 py-1.5 text-[13px] font-bold tracking-widest text-purple-200 transition-all duration-300 hover:text-white hover:border-purple-400"
                    >
                      <ShieldAlert className="h-3.5 w-3.5 text-purple-400" />
                      ADMIN
                    </Link>
                  </motion.div>
                )}

                <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
                  <Link
                    href="/dashboard"
                    className="inline-flex items-center gap-1.5 rounded-md border border-[rgba(57,255,136,0.25)] px-3.5 py-1.5 text-[13px] font-medium text-primary transition-all duration-200 hover:bg-primary/10"
                  >
                    <LayoutDashboard className="h-3.5 w-3.5" />
                    Dashboard
                  </Link>
                </motion.div>

                {/* User avatar / dropdown trigger */}
                <div className="relative">
                  <button
                    onClick={(e) => { e.stopPropagation(); setUserMenuOpen(!userMenuOpen); }}
                    className="flex h-8 w-8 items-center justify-center rounded-full border border-[rgba(57,255,136,0.3)] bg-primary/10 text-[13px] font-bold text-primary transition-all hover:bg-primary/20"
                    aria-label="User menu"
                  >
                    {(user.full_name || user.email)[0].toUpperCase()}
                  </button>

                  <AnimatePresence>
                    {userMenuOpen && (
                      <motion.div
                        initial={{ opacity: 0, y: 6, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 6, scale: 0.95 }}
                        transition={{ duration: 0.15 }}
                        className="absolute right-0 top-11 z-50 w-56 overflow-hidden rounded-lg border border-border bg-[rgba(12,12,12,0.95)] backdrop-blur-xl shadow-2xl"
                      >
                        {/* User info header */}
                        <div className="border-b border-border px-4 py-3">
                          <p className="text-sm font-medium text-foreground truncate">{user.full_name || "User"}</p>
                          <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                          <div className="mt-1.5 flex items-center gap-2">
                            <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-primary">
                              {user.tier || "FREE"}
                            </span>
                            <span className="text-[10px] text-muted-foreground">
                              {user.credits ?? 0} credits
                            </span>
                          </div>
                        </div>

                        {/* Menu items */}
                        <div className="py-1">
                          <Link
                            href="/dashboard"
                            onClick={() => setUserMenuOpen(false)}
                            className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground"
                          >
                            <LayoutDashboard className="h-4 w-4" /> Dashboard
                          </Link>
                          <Link
                            href="/history"
                            onClick={() => setUserMenuOpen(false)}
                            className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground"
                          >
                            <History className="h-4 w-4" /> History
                          </Link>
                          <Link
                            href="/settings"
                            onClick={() => setUserMenuOpen(false)}
                            className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground"
                          >
                            <Settings className="h-4 w-4" /> Settings
                          </Link>
                        </div>

                        {/* Logout */}
                        <div className="border-t border-border py-1">
                          <button
                            onClick={() => { setUserMenuOpen(false); void logout(); }}
                            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-risk transition-colors hover:bg-risk/10"
                          >
                            <LogOut className="h-4 w-4" /> Sign Out
                          </button>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </>
            ) : (
              /* ── Not logged in: Sign In + Try Free Demo ── */
              <>
                <motion.div whileTap={{ scale: 0.97 }}>
                  <Link
                    href="/login"
                    className="rounded-md border border-[rgba(255,255,255,0.10)] px-3.5 py-1.5 text-[13px] font-medium text-foreground/90 transition-all duration-200 hover:border-[rgba(57,255,136,0.35)] hover:text-foreground"
                  >
                    Sign In
                  </Link>
                </motion.div>
                <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
                  <Link
                    href="/demo"
                    className="group relative inline-flex items-center gap-1.5 rounded-md bg-primary px-3.5 py-1.5 text-[13px] font-semibold text-primary-foreground neon-glow transition-all duration-200 hover:brightness-110"
                  >
                    Try Free Demo
                    <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
                  </Link>
                </motion.div>
              </>
            )}
          </div>

          <button
            aria-label="Open menu"
            onClick={() => setOpen(true)}
            className="rounded-md border border-[rgba(255,255,255,0.10)] p-2 md:hidden"
          >
            <Menu className="h-4 w-4" />
          </button>
        </div>
      </motion.header>

      {/* ── Mobile Menu ── */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] flex flex-col bg-[rgba(10,10,10,0.85)] backdrop-blur-2xl md:hidden"
          >
            <div className="flex h-16 items-center justify-between px-5">
              <Logo />
              <button
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="rounded-md border border-[rgba(255,255,255,0.10)] p-2"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <nav className="flex flex-col gap-2 px-5 pt-6">
              {links.map((l, i) => (
                <motion.a
                  key={l.label}
                  href={l.href}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  onClick={() => setOpen(false)}
                  className="border-b border-[rgba(255,255,255,0.06)] py-4 text-xl font-medium text-foreground"
                >
                  {l.label}
                </motion.a>
              ))}
              <Link
                href="/demo"
                onClick={() => setOpen(false)}
                className="border-b border-[rgba(255,255,255,0.06)] py-4 text-xl font-medium text-foreground"
              >
                Live Demo
              </Link>

              {/* Auth-aware mobile buttons */}
              <div className="mt-8 flex flex-col gap-3">
                {!isLoading && user ? (
                  <>
                    <Link
                      href="/dashboard"
                      onClick={() => setOpen(false)}
                      className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground neon-glow"
                    >
                      <LayoutDashboard className="h-4 w-4" /> Dashboard
                    </Link>
                    <Link
                      href="/history"
                      onClick={() => setOpen(false)}
                      className="rounded-md border border-[rgba(255,255,255,0.10)] px-4 py-3 text-center text-sm font-medium"
                    >
                      History
                    </Link>
                    <Link
                      href="/settings"
                      onClick={() => setOpen(false)}
                      className="rounded-md border border-[rgba(255,255,255,0.10)] px-4 py-3 text-center text-sm font-medium"
                    >
                      Settings
                    </Link>
                    <button
                      onClick={() => { setOpen(false); void logout(); }}
                      className="rounded-md border border-risk/30 px-4 py-3 text-sm font-medium text-risk"
                    >
                      Sign Out
                    </button>
                  </>
                ) : (
                  <>
                    <Link
                      href="/login"
                      onClick={() => setOpen(false)}
                      className="rounded-md border border-[rgba(255,255,255,0.10)] px-4 py-3 text-center text-sm font-medium"
                    >
                      Sign In
                    </Link>
                    <Link
                      href="/demo"
                      onClick={() => setOpen(false)}
                      className="inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground neon-glow"
                    >
                      Try Free Demo <ArrowRight className="h-4 w-4" />
                    </Link>
                  </>
                )}
              </div>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}