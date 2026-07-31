"use client";

import { motion } from "framer-motion";
import { Check, X, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

const reveal = (delay: number) => ({
  initial: { opacity: 0, y: 18 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-10% 0px" },
  transition: { duration: 0.55, delay, ease: "easeOut" as const },
});

type Cell = { text: string; tone?: "yes" | "no" | "meh" };

const rows: { label: string; cells: [Cell, Cell, Cell] }[] = [
  {
    label: "Analysis time",
    cells: [
      { text: "2–3 weeks per company", tone: "no" },
      { text: "Hours, but unreliable outputs", tone: "meh" },
      { text: "Under 20 minutes, fully autonomous", tone: "yes" },
    ],
  },
  {
    label: "Mathematical integrity",
    cells: [
      { text: "Analyst-dependent, error-prone", tone: "no" },
      { text: "LLMs hallucinate financial figures", tone: "no" },
      { text: "LLMs never touch numbers — deterministic Python computes all 36 ratios, M-Score & Z-Score", tone: "yes" },
    ],
  },
  {
    label: "Peer & competitor identification",
    cells: [
      { text: "Manual research, subjective", tone: "no" },
      { text: "Basic keyword matching", tone: "meh" },
      { text: "AI-first: web search + RAG + SEC validation loop with hallucination guards", tone: "yes" },
    ],
  },
  {
    label: "Risk coverage",
    cells: [
      { text: "Financial risks only", tone: "meh" },
      { text: "Generic, vague risk summaries", tone: "no" },
      { text: "6-dimension scoring with 8 automated deal-breaker conditions", tone: "yes" },
    ],
  },
  {
    label: "Data provenance & trust",
    cells: [
      { text: "Trust the analyst", tone: "meh" },
      { text: "No audit trail", tone: "no" },
      { text: "Full XBRL provenance chain + arithmetic cross-checks + Data Verification Report", tone: "yes" },
    ],
  },
  {
    label: "Output quality",
    cells: [
      { text: "10–20 page Word doc", tone: "meh" },
      { text: "Unformatted text dump", tone: "no" },
      { text: "17-section boardroom-ready HTML memo with 40+ interactive data visualizations", tone: "yes" },
    ],
  },
  {
    label: "Handling missing data",
    cells: [
      { text: "Analysis gaps, missed entirely", tone: "no" },
      { text: "Hallucinate placeholder values", tone: "no" },
      { text: "Graceful degradation — sections adapt, never fabricate", tone: "yes" },
    ],
  },
  {
    label: "Cost",
    cells: [
      { text: "$15k–25k per engagement", tone: "no" },
      { text: "Low, but output is unusable", tone: "meh" },
      { text: "Democratized — institutional-grade for a fraction of the cost", tone: "yes" },
    ],
  },
];

function ToneIcon({ tone }: { tone?: Cell["tone"] }) {
  if (tone === "yes") return <Check className="h-4 w-4 shrink-0 text-emerald-500 drop-shadow-[0_0_8px_rgba(16,185,129,0.8)]" />;
  if (tone === "no") return <X className="h-4 w-4 shrink-0 text-risk/70" />;
  return <Minus className="h-4 w-4 shrink-0 text-muted-foreground/70" />;
}

export function Comparison() {
  const heads = ["Manual Due Diligence", "Generic AI Tools", "DeligenX"];

  return (
    <section id="compare" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-7xl px-5 md:px-8">
        <motion.div {...reveal(0)} className="mx-auto max-w-3xl text-center">
          <h2 className="font-sans text-4xl font-bold leading-[1.05] tracking-[-0.03em] text-foreground md:text-5xl lg:text-6xl drop-shadow-sm">
            DeligenX vs.{" "}
            <span className="text-gradient-neon inline-block pr-2 italic">the old way.</span>
          </h2>
        </motion.div>

        <motion.div
          {...reveal(0.1)}
          className="glass mt-12 overflow-hidden rounded-2xl md:mt-16 border border-white/10"
        >
          {/* Header */}
          <div className="grid grid-cols-2 border-b border-[rgba(255,255,255,0.07)] md:grid-cols-4">
            <div className="hidden px-5 py-4 font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground md:block">
              Capability
            </div>
            {heads.map((h, i) => (
              <div
                key={h}
                className={cn(
                  "px-5 py-5 text-sm font-semibold tracking-wide",
                  i === 2
                    ? "border-l border-r border-emerald-500/50 bg-emerald-500/[0.08] text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.15)] relative z-10"
                    : "text-muted-foreground",
                  i === 0 && "hidden md:block",
                )}
              >
                {h}
              </div>
            ))}
          </div>

          {rows.map((row, ri) => {
            const isLast = ri === rows.length - 1;
            return (
              <motion.div
                key={row.label}
                {...reveal(0.12 + ri * 0.04)}
                className={cn(
                  "grid grid-cols-2 border-[rgba(255,255,255,0.05)] md:grid-cols-4 relative",
                  !isLast && "border-b"
                )}
              >
                <div className="col-span-2 px-5 pt-4 text-sm font-medium text-foreground/90 md:col-span-1 md:py-5 md:pt-5">
                  {row.label}
                </div>
                {row.cells.map((c, i) => (
                  <div
                    key={i}
                    className={cn(
                      "items-start gap-3 px-5 py-4 text-sm md:py-5 leading-relaxed",
                      i === 0 ? "hidden md:flex" : "flex",
                      i === 2
                        ? "border-l border-r border-emerald-500/50 bg-emerald-500/[0.08] font-medium text-foreground shadow-[inset_0_0_20px_rgba(16,185,129,0.05)] relative z-10"
                        : "text-muted-foreground",
                      isLast && i === 2 && "border-b shadow-[0_10px_30px_rgba(16,185,129,0.15)]"
                    )}
                  >
                    <span className="mt-0.5">
                      <ToneIcon tone={c.tone} />
                    </span>
                    <span>{c.text}</span>
                  </div>
                ))}
              </motion.div>
            );
          })}
        </motion.div>

        <motion.div {...reveal(0.6)} className="mt-10 text-center">
          <p className="text-muted-foreground/80 font-mono text-sm tracking-wide">
            Built for analysts who demand <span className="text-foreground/90 font-medium">mathematical certainty</span>, not AI guesswork.
          </p>
        </motion.div>
      </div>
    </section>
  );
}