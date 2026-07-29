"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Database, FileText, LineChart, Newspaper } from "lucide-react";
import { NeuralOrb } from "./NeuralOrb";

export function Hero() {
  const [ticker, setTicker] = useState("");
  const [focused, setFocused] = useState(false);

  return (
    <section className="relative isolate overflow-hidden pt-28 md:min-h-screen md:pt-24">
      {/* Corner mesh glows */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(60% 50% at 15% 20%, rgba(57,255,136,0.18), transparent 60%), radial-gradient(50% 45% at 100% 80%, rgba(77,255,160,0.14), transparent 65%), radial-gradient(40% 35% at 80% 0%, rgba(57,255,136,0.10), transparent 60%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent"
      />

      {/* 3D Orb — absolute on desktop, stacked below on mobile */}
      <div className="pointer-events-none absolute inset-0 -z-0 hidden md:block">
        <div className="pointer-events-auto absolute right-[-6%] top-1/2 h-[720px] w-[720px] -translate-y-1/2 opacity-90">
          <NeuralOrb />
        </div>
        <div className="absolute inset-y-0 left-0 w-2/3 bg-gradient-to-r from-background via-background/85 to-transparent" />
      </div>

      <div className="relative mx-auto grid max-w-7xl grid-cols-1 gap-10 px-5 pb-16 md:grid-cols-12 md:px-8">
        <div className="relative z-10 flex flex-col justify-center md:col-span-7 md:min-h-[calc(100vh-6rem)]">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="inline-flex w-fit items-center gap-2 rounded-full glass px-3 py-1.5 text-[11px] font-medium tracking-wide text-foreground/85"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inset-0 rounded-full bg-primary pulse-dot" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
            </span>
            Autonomous 5-Agent AI Pipeline
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.05 }}
            className="mt-6 max-w-2xl font-sans font-semibold tracking-[-0.035em] text-foreground"
            style={{
              fontSize: "clamp(2.6rem, 6.4vw, 6rem)",
              lineHeight: 1.02,
            }}
          >
            Investment memos
            <br />
            <span className="whitespace-nowrap">
              that{" "}
              <span className="text-gradient-neon italic inline-block pr-2">
                write
              </span>
            </span>{" "}
            <span className="text-gradient-neon italic inline-block pr-2">
              themselves.
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="mt-6 max-w-xl text-[15px] leading-relaxed text-muted-foreground md:text-base"
          >
            DeligenX ingests SEC filings, runs deterministic financial models, scores six
            dimensions of risk, and produces a fully-cited investment memorandum —
            autonomously, in minutes.
          </motion.p>

          {/* Terminal ticker input */}
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.25 }}
            className={`mt-8 flex w-full max-w-xl items-center gap-2 rounded-lg border bg-[rgba(8,8,8,0.72)] p-1.5 backdrop-blur-md transition-all ${
              focused
                ? "border-primary/60 shadow-[0_0_0_1px_rgba(57,255,136,0.35),0_0_40px_rgba(57,255,136,0.2)]"
                : "border-[rgba(255,255,255,0.08)]"
            }`}
          >
            <div className="relative flex flex-1 items-center gap-2 px-3 py-2 font-mono text-sm">
              <span className="text-primary/80">$</span>
              <div className="relative flex-1">
                <input
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase().slice(0, 6))}
                  onFocus={() => setFocused(true)}
                  onBlur={() => setFocused(false)}
                  className="w-full bg-transparent font-mono text-sm tracking-wider text-foreground focus:outline-none"
                  aria-label="Enter US stock ticker"
                />
                {!ticker && (
                  <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center font-mono text-sm text-muted-foreground/70">
                    AAPL<span className="caret-blink text-primary">_</span>
                  </span>
                )}
              </div>
            </div>
            <button className="group inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-shadow neon-glow hover:brightness-110">
              Analyze
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </button>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.7, delay: 0.4 }}
            className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground/80"
          >
            <span className="inline-flex items-center gap-1.5">
              <Database className="h-3 w-3 text-primary/80" /> SEC EDGAR
            </span>
            <span className="text-muted-foreground/40">·</span>
            <span className="inline-flex items-center gap-1.5">
              <LineChart className="h-3 w-3 text-primary/80" /> yfinance
            </span>
            <span className="text-muted-foreground/40">·</span>
            <span className="inline-flex items-center gap-1.5">
              <FileText className="h-3 w-3 text-primary/80" /> FRED
            </span>
            <span className="text-muted-foreground/40">·</span>
            <span className="inline-flex items-center gap-1.5">
              <Newspaper className="h-3 w-3 text-primary/80" /> NewsAPI
            </span>
          </motion.div>
        </div>

        <div className="relative md:col-span-5">
          {/* Mobile orb */}
          <div className="mx-auto h-[340px] w-full max-w-sm md:hidden">
            <NeuralOrb />
          </div>
        </div>
      </div>

      {/* Bottom fade to next section */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-b from-transparent to-background" />
    </section>
  );
}