"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import {
  Database,
  Calculator,
  Globe2,
  ShieldAlert,
  FileText,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Stage = {
  id: string;
  name: string;
  icon: LucideIcon;
  description: string;
  highlight: { value: string; label: string };
};

const stages: Stage[] = [
  {
    id: "ingestion",
    name: "Ingestion Agent",
    icon: Database,
    description:
      "Resolves the ticker to a SEC CIK, pulls 5 years of financial data via SEC EDGAR, and builds a searchable vector store from 10-K, 8-K, and proxy filings.",
    highlight: { value: "5", label: "Years of filings" },
  },
  {
    id: "analysis",
    name: "Analysis Agent",
    icon: Calculator,
    description:
      "Computes 36 financial ratios, runs the Beneish M-Score and Altman Z-Score models, flags 15 anomaly patterns — 100% deterministic Python, zero LLM calls on any number.",
    highlight: { value: "36", label: "Ratios computed" },
  },
  {
    id: "market",
    name: "Market Intelligence Agent",
    icon: Globe2,
    description:
      "Identifies real named competitors, builds a full investment-banking-style trading comps table with implied valuation, and scores live news sentiment.",
    highlight: { value: "15", label: "Anomaly patterns" },
  },
  {
    id: "risk",
    name: "Risk Assessment Agent",
    icon: ShieldAlert,
    description:
      "Scores six independent risk dimensions — financial, market, operational, legal, management, ESG — and checks eight absolute deal-breaker conditions.",
    highlight: { value: "6", label: "Risk dimensions" },
  },
  {
    id: "memo",
    name: "Memo Generation Agent",
    icon: FileText,
    description:
      "Assembles a fully-cited investment memorandum. An anti-hallucination validator cross-checks every single number in the document against its verified source before delivery.",
    highlight: { value: "100%", label: "Numbers traced" },
  },
];

const proofStats = [
  { value: 36, suffix: "", label: "Financial Ratios Computed" },
  { value: 6, suffix: "", label: "Risk Dimensions Scored" },
  { value: 8, suffix: "", label: "Deal-Breaker Checks" },
  { value: 100, suffix: "%", label: "Numbers Traced to Source" },
];

function CountUp({
  to,
  suffix = "",
  start,
  duration = 1400,
}: {
  to: number;
  suffix?: string;
  start: boolean;
  duration?: number;
}) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!start) return;
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(Math.round(eased * to));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [start, to, duration]);
  return (
    <span className="font-mono tabular-nums">
      {n}
      {suffix}
    </span>
  );
}

export function HowItWorks() {
  const [active, setActive] = useState<number>(0);
  const sectionRef = useRef<HTMLDivElement>(null);
  const inView = useInView(sectionRef, { once: true, margin: "-15% 0px" });

  return (
    <section
      ref={sectionRef}
      id="pipeline"
      className="relative isolate overflow-hidden py-24 md:py-32"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(50% 40% at 50% 0%, rgba(57,255,136,0.08), transparent 60%)",
        }}
      />

      <div className="mx-auto max-w-7xl px-5 md:px-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="mx-auto max-w-3xl text-center"
        >
          <div className="inline-flex items-center gap-2 font-mono text-[11px] font-medium uppercase tracking-[0.25em] text-primary">
            <span className="h-px w-6 bg-primary/60" />
            The Pipeline
            <span className="h-px w-6 bg-primary/60" />
          </div>
          <h2 className="mt-5 font-sans font-semibold tracking-[-0.03em] text-foreground text-4xl md:text-5xl lg:text-6xl leading-[1.05]">
            Five agents.{" "}
            <span className="text-gradient-neon italic inline-block pr-2">
              Zero human intervention.
            </span>
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-[15px] leading-relaxed text-muted-foreground md:text-base">
            Each agent completes its work fully before the next begins — a
            deterministic, auditable chain from raw filing to finished memo.
          </p>
        </motion.div>

        {/* Pipeline */}
        <div className="relative mt-16 md:mt-20">
          {/* Desktop connector line */}
          <div className="pointer-events-none absolute inset-x-0 top-[64px] hidden md:block">
            <div className="relative mx-auto h-px w-[92%] overflow-hidden">
              <div
                className="absolute inset-0"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(90deg, rgba(57,255,136,0.35) 0 6px, transparent 6px 14px)",
                }}
              />
              <motion.div
                initial={{ x: "-20%" }}
                animate={{ x: "120%" }}
                transition={{
                  duration: 4,
                  repeat: Infinity,
                  ease: "linear",
                }}
                className="absolute top-1/2 h-[3px] w-32 -translate-y-1/2 rounded-full"
                style={{
                  background:
                    "linear-gradient(90deg, transparent, #39ff88, transparent)",
                  boxShadow: "0 0 20px #39ff88, 0 0 40px rgba(57,255,136,0.6)",
                }}
              />
            </div>
          </div>

          {/* Mobile vertical connector */}
          <div className="pointer-events-none absolute left-[35px] top-0 bottom-0 w-px md:hidden">
            <div
              className="absolute inset-0"
              style={{
                backgroundImage:
                  "repeating-linear-gradient(180deg, rgba(57,255,136,0.35) 0 6px, transparent 6px 14px)",
              }}
            />
            <motion.div
              initial={{ y: "-10%" }}
              animate={{ y: "110%" }}
              transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
              className="absolute left-1/2 h-24 w-[3px] -translate-x-1/2 rounded-full"
              style={{
                background:
                  "linear-gradient(180deg, transparent, #39ff88, transparent)",
                boxShadow: "0 0 20px #39ff88, 0 0 40px rgba(57,255,136,0.6)",
              }}
            />
          </div>

          <ol className="relative grid grid-cols-1 gap-5 md:grid-cols-5 md:gap-4">
            {stages.map((stage, i) => {
              const Icon = stage.icon;
              const isActive = active === i;
              return (
                <motion.li
                  key={stage.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={inView ? { opacity: 1, y: 0 } : {}}
                  transition={{ duration: 0.5, delay: 0.15 + i * 0.1 }}
                  onMouseEnter={() => setActive(i)}
                  onFocus={() => setActive(i)}
                  onClick={() => setActive(i)}
                  className="relative"
                >
                  <div
                    className={cn(
                      "group relative h-full rounded-xl glass p-5 pl-16 md:pl-5 transition-all duration-300 cursor-pointer",
                      isActive
                        ? "border-primary/60 shadow-[0_0_0_1px_rgba(57,255,136,0.45),0_0_40px_rgba(57,255,136,0.18)]"
                        : "hover:border-primary/30",
                    )}
                  >
                    {/* Stage index node */}
                    <div
                      className={cn(
                        "absolute left-3 top-5 md:left-1/2 md:-top-2 md:-translate-x-1/2 md:top-0",
                        "flex h-10 w-10 items-center justify-center rounded-full border transition-all duration-300",
                        "bg-background/90 backdrop-blur",
                        isActive
                          ? "border-primary shadow-[0_0_20px_rgba(57,255,136,0.6)]"
                          : "border-primary/30",
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-4 w-4 transition-all",
                          isActive
                            ? "text-primary drop-shadow-[0_0_6px_rgba(57,255,136,0.9)]"
                            : "text-primary/70",
                        )}
                      />
                    </div>

                    <div className="md:mt-8">
                      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary/80">
                        Stage 0{i + 1}
                      </div>
                      <h3 className="mt-1.5 font-sans text-base font-semibold text-foreground">
                        {stage.name}
                      </h3>
                      <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
                        {stage.description}
                      </p>

                      <div className="mt-4 flex items-baseline gap-2 border-t border-[rgba(255,255,255,0.06)] pt-3">
                        <span
                          className={cn(
                            "font-mono text-xl font-bold tabular-nums",
                            isActive ? "text-primary" : "text-foreground/90",
                          )}
                        >
                          {stage.highlight.value}
                        </span>
                        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                          {stage.highlight.label}
                        </span>
                      </div>
                    </div>
                  </div>
                </motion.li>
              );
            })}
          </ol>
        </div>

        {/* Proof stats */}
        <div className="mt-16 grid grid-cols-2 gap-4 md:mt-20 md:grid-cols-4">
          {proofStats.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 16 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: 0.6 + i * 0.08 }}
              className="glass rounded-xl p-5 text-center transition-colors hover:border-primary/40"
            >
              <div className="font-mono text-4xl font-bold text-primary md:text-5xl">
                <CountUp to={s.value} suffix={s.suffix} start={inView} />
              </div>
              <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                {s.label}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}