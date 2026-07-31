"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Quote } from "lucide-react";
import { cn } from "@/lib/utils";

const scorecard = [
  { dim: "Financial", score: "72 / 100", level: "low" },
  { dim: "Market", score: "58 / 100", level: "med" },
  { dim: "Operational", score: "66 / 100", level: "low" },
  { dim: "Legal", score: "41 / 100", level: "high" },
  { dim: "Management", score: "55 / 100", level: "med" },
  { dim: "ESG", score: "69 / 100", level: "low" },
] as const;

const levelStyles: Record<string, string> = {
  low: "text-primary border-primary/40 bg-primary/10",
  med: "text-warn border-warn/40 bg-warn/10",
  high: "text-risk border-risk/40 bg-risk/10",
};

const reveal = (delay: number) => ({
  initial: { opacity: 0, y: 18 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-10% 0px" },
  transition: { duration: 0.55, delay, ease: "easeOut" as const },
});

export function SampleReport() {
  return (
    <section id="sample" className="relative isolate overflow-hidden py-24 md:py-32">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(45% 40% at 50% 20%, rgba(57,255,136,0.08), transparent 65%)",
        }}
      />
      <div className="mx-auto max-w-6xl px-5 md:px-8">
        <motion.div {...reveal(0)} className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 font-mono text-[11px] font-medium uppercase tracking-[0.25em] text-primary">
            <span className="h-px w-6 bg-primary/60" />
            See it in action
            <span className="h-px w-6 bg-primary/60" />
          </div>
          <h2 className="mt-5 font-sans text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-foreground md:text-5xl lg:text-6xl">
            One ticker.{" "}
            <span className="text-gradient-neon inline-block pr-2 italic">
              A complete investment memo.
            </span>
          </h2>
        </motion.div>

        <div className="relative mt-14 md:mt-20">
          {/* Document window */}
          <motion.div
            {...reveal(0.1)}
            className="glass relative overflow-hidden rounded-2xl shadow-[0_40px_120px_-40px_rgba(57,255,136,0.35)]"
          >
            {/* Chrome */}
            <div className="flex items-center gap-3 border-b border-[rgba(255,255,255,0.07)] bg-[rgba(255,255,255,0.03)] px-4 py-3">
              <div className="flex shrink-0 gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-risk/70" />
                <span className="h-2.5 w-2.5 rounded-full bg-warn/70" />
                <span className="h-2.5 w-2.5 rounded-full bg-primary/70" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="mx-auto max-w-sm truncate rounded-md border border-[rgba(255,255,255,0.07)] bg-background/60 px-3 py-1 text-center font-mono text-[10px] text-muted-foreground">
                  deligenx.ai/memo/NKLA-2026Q2
                </div>
              </div>
            </div>

            {/* Memo body */}
            <div className="p-5 md:p-8">
              <header className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-4">
                <div className="min-w-0">
                  <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary/80">
                    Investment Memorandum
                  </div>
                  <h3 className="mt-1 truncate font-sans text-xl font-semibold text-foreground md:text-2xl">
                    Nikola Corporation
                  </h3>
                  <div className="mt-1 font-mono text-xs text-muted-foreground">
                    NASDAQ: NKLA · Generated in 4m 12s
                  </div>
                </div>
                <span className="shrink-0 rounded-full border border-warn/50 bg-warn/10 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.15em] text-warn">
                  Stance: Caution
                </span>
              </header>

              <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
                {/* Scorecard */}
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    Risk Scorecard
                  </div>
                  <div className="mt-3 overflow-hidden rounded-lg border border-[rgba(255,255,255,0.07)]">
                    {scorecard.map((r, i) => (
                      <motion.div
                        key={r.dim}
                        {...reveal(0.25 + i * 0.06)}
                        className={cn(
                          "flex items-center justify-between gap-3 border-b border-[rgba(255,255,255,0.05)] px-3 py-2.5 last:border-b-0",
                          r.level === "high"
                            ? "bg-risk/5"
                            : r.level === "med"
                              ? "bg-warn/5"
                              : "bg-primary/5",
                        )}
                      >
                        <span className="min-w-0 truncate text-[13px] text-foreground/90">
                          {r.dim}
                        </span>
                        <span
                          className={cn(
                            "shrink-0 rounded-md border px-2 py-0.5 font-mono text-[11px] font-semibold tabular-nums",
                            levelStyles[r.level],
                          )}
                        >
                          {r.score}
                        </span>
                      </motion.div>
                    ))}
                  </div>
                </div>

                {/* Narrative */}
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    Excerpt — Financial Analysis
                  </div>
                  <div className="mt-3 rounded-lg border border-[rgba(255,255,255,0.07)] bg-background/40 p-4">
                    <Quote className="h-4 w-4 text-primary/60" />
                    <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
                      Gross margin contracted{" "}
                      <span className="font-mono font-semibold text-foreground">
                        410bps
                      </span>{" "}
                      year-over-year to{" "}
                      <span className="font-mono font-semibold text-foreground">
                        18.2%
                      </span>
                      , while days sales outstanding expanded to{" "}
                      <span className="font-mono font-semibold text-foreground">
                        74 days
                      </span>
                      . The Beneish M-Score of{" "}
                      <span className="font-mono font-semibold text-warn">-1.94</span>{" "}
                      places the issuer above the manipulation threshold
                      <sup className="ml-0.5 rounded bg-primary/15 px-1 font-mono text-[9px] text-primary">
                        [10-K p.62]
                      </sup>
                      .
                    </p>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    {[
                      { k: "Deal-breakers", v: "1 / 8" },
                      { k: "Citations", v: "247" },
                    ].map((s) => (
                      <div
                        key={s.k}
                        className="rounded-lg border border-[rgba(255,255,255,0.07)] bg-background/40 p-3"
                      >
                        <div className="font-mono text-lg font-bold tabular-nums text-primary">
                          {s.v}
                        </div>
                        <div className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
                          {s.k}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Floating annotations (desktop) */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-10% 0px" }}
            transition={{ duration: 0.5, delay: 0.55, ease: "easeOut" }}
            className="pointer-events-none absolute -left-6 top-[58%] hidden xl:block"
          >
            <Annotation label="Color-coded 6-dimension scorecard" side="left" />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-10% 0px" }}
            transition={{ duration: 0.5, delay: 0.7, ease: "easeOut" }}
            className="pointer-events-none absolute -right-8 top-[62%] hidden xl:block"
          >
            <Annotation label="Every claim cited to source" side="right" />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: -14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-10% 0px" }}
            transition={{ duration: 0.5, delay: 0.85, ease: "easeOut" }}
            className="pointer-events-none absolute -right-10 top-16 hidden xl:block"
          >
            <Annotation label="Composite verdict in one badge" side="right" />
          </motion.div>
        </div>

        {/* Mobile annotations */}
        <div className="mt-6 flex flex-wrap justify-center gap-2 xl:hidden">
          {[
            "Every claim cited to source",
            "Color-coded 6-dimension scorecard",
          ].map((l, i) => (
            <motion.span key={l} {...reveal(0.5 + i * 0.1)}>
              <Annotation label={l} side="left" />
            </motion.span>
          ))}
        </div>

        <motion.div {...reveal(0.6)} className="mt-12 flex justify-center">
          <Link
            href="/demo"
            className="group inline-flex items-center gap-2 rounded-full bg-primary px-7 py-3.5 font-sans text-sm font-semibold text-primary-foreground shadow-[0_0_40px_rgba(57,255,136,0.45)] transition-all duration-300 hover:shadow-[0_0_60px_rgba(57,255,136,0.7)] active:scale-[0.98]"
          >
            View Interactive Demo
            <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
          </Link>
        </motion.div>
      </div>
    </section>
  );
}

function Annotation({ label, side }: { label: string; side: "left" | "right" }) {
  return (
    <span className="glass inline-flex items-center gap-2 rounded-full border-primary/30 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-primary shadow-[0_0_24px_rgba(57,255,136,0.2)]">
      {side === "right" && <span className="h-px w-5 bg-primary/50" />}
      {label}
      {side === "left" && <span className="h-px w-5 bg-primary/50" />}
    </span>
  );
}