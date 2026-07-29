"use client";

import { motion } from "framer-motion";
import { Cpu } from "lucide-react";

const reveal = (delay: number) => ({
  initial: { opacity: 0, y: 18 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-10% 0px" },
  transition: { duration: 0.55, delay, ease: "easeOut" as const },
});

const stack = [
  "Python",
  "CrewAI",
  "SEC EDGAR",
  "ChromaDB",
  "Anthropic Claude",
  "FastMCP",
];

export function About() {
  return (
    <section id="about" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-4xl px-5 md:px-8">
        <motion.h2
          {...reveal(0)}
          className="font-sans text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-foreground md:text-5xl"
        >
          Built for{" "}
          <span className="text-gradient-neon inline-block pr-2 italic">IITISoC 2026.</span>
        </motion.h2>

        <motion.p {...reveal(0.08)} className="mt-6 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
          DeligenX is an autonomous five-agent CrewAI pipeline built end to end — from SEC
          EDGAR data ingestion and vector-indexed filings, through deterministic financial
          modelling, competitor comps and six-dimension risk scoring, all the way to a fully
          validated investment memorandum. Every number in the final document is traced back
          to its verified source by an anti-hallucination validator. No analyst in the loop,
          no manual intervention, no unverified claims.
        </motion.p>

        <motion.div {...reveal(0.14)} className="mt-9 flex flex-wrap gap-2">
          {stack.map((s) => (
            <span
              key={s}
              className="rounded-md border border-[rgba(255,255,255,0.09)] bg-[rgba(255,255,255,0.03)] px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground transition-colors hover:border-primary/35 hover:text-primary"
            >
              {s}
            </span>
          ))}
        </motion.div>

        <motion.div
          {...reveal(0.2)}
          className="glass mt-10 flex items-center gap-4 rounded-xl p-5"
        >
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-primary/30 bg-primary/10 text-primary">
            <Cpu className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-medium text-foreground">Team DeligenX</div>
            <div className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
              IIT Indore Summer of Code · 2026
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}