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
    label: "Time to complete",
    cells: [
      { text: "2–3 weeks", tone: "no" },
      { text: "Hours, but unreliable", tone: "meh" },
      { text: "Minutes", tone: "yes" },
    ],
  },
  {
    label: "Fraud detection models",
    cells: [
      { text: "Analyst-dependent", tone: "meh" },
      { text: "None", tone: "no" },
      { text: "Beneish + Altman built in", tone: "yes" },
    ],
  },
  {
    label: "Every number source-verified",
    cells: [
      { text: "Yes, but slow", tone: "meh" },
      { text: "No", tone: "no" },
      { text: "Yes, automatically", tone: "yes" },
    ],
  },
  {
    label: "Six-dimension risk scoring",
    cells: [
      { text: "Manual", tone: "meh" },
      { text: "No", tone: "no" },
      { text: "Automatic", tone: "yes" },
    ],
  },
  {
    label: "Cost",
    cells: [
      { text: "$15k+ per engagement", tone: "no" },
      { text: "Low, but unusable output", tone: "meh" },
      { text: "Free to start", tone: "yes" },
    ],
  },
];

function ToneIcon({ tone }: { tone?: Cell["tone"] }) {
  if (tone === "yes") return <Check className="h-3.5 w-3.5 shrink-0 text-primary" />;
  if (tone === "no") return <X className="h-3.5 w-3.5 shrink-0 text-risk/70" />;
  return <Minus className="h-3.5 w-3.5 shrink-0 text-muted-foreground/70" />;
}

export function Comparison() {
  const heads = ["Manual Due Diligence", "Generic AI Tools", "DeligenX"];

  return (
    <section id="compare" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-5 md:px-8">
        <motion.div {...reveal(0)} className="mx-auto max-w-2xl text-center">
          <h2 className="font-sans text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-foreground md:text-5xl">
            DeligenX vs.{" "}
            <span className="text-gradient-neon inline-block pr-2 italic">the old way.</span>
          </h2>
        </motion.div>

        <motion.div
          {...reveal(0.1)}
          className="glass mt-12 overflow-hidden rounded-2xl md:mt-16"
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
                  "px-5 py-4 text-sm font-medium",
                  i === 2
                    ? "border-l border-primary/30 bg-primary/[0.06] text-primary"
                    : "text-muted-foreground",
                  i === 0 && "hidden md:block",
                )}
              >
                {h}
              </div>
            ))}
          </div>

          {rows.map((row, ri) => (
            <motion.div
              key={row.label}
              {...reveal(0.12 + ri * 0.06)}
              className="grid grid-cols-2 border-b border-[rgba(255,255,255,0.05)] last:border-b-0 md:grid-cols-4"
            >
              <div className="col-span-2 px-5 pt-4 text-sm font-medium text-foreground md:col-span-1 md:py-5 md:pt-5">
                {row.label}
              </div>
              {row.cells.map((c, i) => (
                <div
                  key={i}
                  className={cn(
                    "flex items-start gap-2 px-5 py-4 text-sm md:py-5",
                    i === 2
                      ? "border-l border-primary/30 bg-primary/[0.06] font-medium text-foreground"
                      : "text-muted-foreground",
                  )}
                >
                  <span className="mt-0.5">
                    <ToneIcon tone={c.tone} />
                  </span>
                  <span>{c.text}</span>
                </div>
              ))}
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}