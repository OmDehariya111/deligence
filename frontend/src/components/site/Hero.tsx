"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Database, FileText, LineChart, Newspaper } from "lucide-react";
import Link from "next/link";
import { NeuralOrb } from "./NeuralOrb";

export function Hero() {
  const [ticker, setTicker] = useState("");
  const [focused, setFocused] = useState(false);

  return (
    <section className="relative isolate pt-28 md:min-h-screen md:pt-24">
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
        <div className="pointer-events-auto absolute right-[2%] top-1/2 h-[780px] w-[780px] -translate-y-1/2 opacity-90">
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
            Automating
            <br />
            the art of
            <br />
            <span className="text-gradient-neon italic inline-block pr-4 pb-1">
              Financial
            </span>
            <br />
            <span className="text-gradient-neon italic inline-block pr-2">
              Research.
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="mt-6 max-w-xl text-[15px] leading-relaxed text-muted-foreground md:text-base"
          >
            Experience the future of financial research. DeligenX orchestrates a sophisticated 5-agent AI architecture to autonomously ingest real-time data, execute deterministic risk models, and generate institutional-grade investment memorandums—compressing weeks of due diligence into minutes.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.25 }}
            className="mt-10 flex items-center gap-4"
          >
            <Link
              href="/dashboard"
              className="group relative inline-flex items-center gap-2 overflow-hidden rounded-full bg-primary px-8 py-3.5 text-sm font-bold text-primary-foreground shadow-[0_0_40px_rgba(57,255,136,0.3)] transition-all hover:scale-[1.02] hover:shadow-[0_0_60px_rgba(57,255,136,0.5)] active:scale-[0.98]"
            >
              <span className="relative z-10 flex items-center gap-2">
                Launch Platform
                <ArrowRight className="h-4.5 w-4.5 transition-transform group-hover:translate-x-1" />
              </span>
            </Link>
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