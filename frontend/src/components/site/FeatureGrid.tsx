"use client";

import { motion } from "framer-motion";
import {
  ShieldAlert,
  Grid2x2Check,
  FileSearch,
  OctagonAlert,
  Table2,
  BadgeCheck,
  Bot,
  Activity,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Feature = {
  title: string;
  body: string;
  icon: LucideIcon;
  span: string;
};

const features: Feature[] = [
  {
    title: "Fraud & Distress Detection",
    body: "Beneish M-Score and Altman Z-Score run automatically across every fiscal year, flagging manipulation risk and bankruptcy probability with academically-validated models.",
    icon: ShieldAlert,
    span: "md:col-span-3 lg:col-span-4 lg:row-span-2",
  },
  {
    title: "Six-Dimension Risk Scorecard",
    body: "Financial, Market, Operational, Legal, Management & Governance, and ESG risk, each independently scored and weighted into one composite verdict.",
    icon: Grid2x2Check,
    span: "md:col-span-3 lg:col-span-4",
  },
  {
    title: "MD&A Credibility Cross-Check",
    body: "Compares what management promised last year against what actually happened this year. No other platform in this category does this.",
    icon: FileSearch,
    span: "md:col-span-3 lg:col-span-4",
  },
  {
    title: "Deal-Breaker Detection",
    body: "Eight absolute conditions — going concern, active fraud investigation, revenue restatement, and more — that override every other score.",
    icon: OctagonAlert,
    span: "md:col-span-3 lg:col-span-4",
  },
  {
    title: "Investment Banking Comps Table",
    body: "Full LTM trading multiples against real named competitors, with a peer-based implied valuation range.",
    icon: Table2,
    span: "md:col-span-3 lg:col-span-4",
  },
  {
    title: "Anti-Hallucination Validated",
    body: "Every number the AI writes is cross-checked against its verified source before the document is finalized. If it can't be traced, it doesn't appear.",
    icon: BadgeCheck,
    span: "md:col-span-6 lg:col-span-4 lg:row-span-2",
  },
  {
    title: "Fully Autonomous",
    body: "Ticker in, memo out. No prompts, no human review steps, no manual data entry.",
    icon: Bot,
    span: "md:col-span-3 lg:col-span-4",
  },
  {
    title: "Real-Time Market Context",
    body: "Live pricing, analyst consensus, news sentiment, and macro indicators layered onto historical filings.",
    icon: Activity,
    span: "md:col-span-3 lg:col-span-4",
  },
];

export function FeatureGrid() {
  return (
    <section id="features" className="relative isolate overflow-hidden py-24 md:py-32">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(45% 35% at 80% 10%, rgba(57,255,136,0.07), transparent 60%)",
        }}
      />
      <div className="mx-auto max-w-7xl px-5 md:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-15% 0px" }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="mx-auto max-w-3xl text-center"
        >
          <div className="inline-flex items-center gap-2 font-mono text-[11px] font-medium uppercase tracking-[0.25em] text-primary">
            <span className="h-px w-6 bg-primary/60" />
            Why DeligenX
            <span className="h-px w-6 bg-primary/60" />
          </div>
          <h2 className="mt-5 font-sans text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-foreground md:text-5xl lg:text-6xl">
            Built like a real risk desk,{" "}
            <span className="text-gradient-neon inline-block pr-2 italic">
              not a demo.
            </span>
          </h2>
        </motion.div>

        <div className="mt-14 grid grid-cols-1 gap-4 md:mt-16 md:grid-cols-6 lg:grid-cols-12">
          {features.map((f, i) => {
            const Icon = f.icon;
            return (
              <motion.article
                key={f.title}
                initial={{ opacity: 0, y: 22 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-10% 0px" }}
                transition={{ duration: 0.5, delay: i * 0.07, ease: "easeOut" }}
                className={cn(
                  "group glass relative flex flex-col rounded-xl p-6 transition-all duration-300",
                  "hover:-translate-y-1 hover:scale-[1.015] hover:border-primary/50",
                  "hover:shadow-[0_0_0_1px_rgba(57,255,136,0.35),0_18px_50px_-20px_rgba(57,255,136,0.35)]",
                  f.span,
                )}
              >
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-background/70 transition-all duration-300 group-hover:border-primary/70 group-hover:shadow-[0_0_22px_rgba(57,255,136,0.45)]">
                  <Icon className="h-5 w-5 text-primary/70 transition-all duration-300 group-hover:text-primary group-hover:drop-shadow-[0_0_8px_rgba(57,255,136,0.9)]" />
                </div>
                <h3 className="mt-4 font-sans text-base font-semibold text-foreground">
                  {f.title}
                </h3>
                <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
                  {f.body}
                </p>
              </motion.article>
            );
          })}
        </div>
      </div>
    </section>
  );
}