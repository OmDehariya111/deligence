"use client";

import { motion } from "framer-motion";
import { Download, FileText, Quote } from "lucide-react";
import { riskStyles, type DemoReport } from "./demoData";

const reveal = (delay: number) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, delay, ease: "easeOut" as const },
});

export function ReportViewer({ report }: { report: DemoReport }) {
  return (
    <motion.div {...reveal(0)} className="glass overflow-hidden rounded-2xl">
      {/* Document chrome */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[rgba(255,255,255,0.07)] bg-[rgba(255,255,255,0.02)] px-5 py-3.5">
        <div className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
          <FileText className="h-3.5 w-3.5 text-primary" />
          {report.ticker}_investment_memo.docx
        </div>
        <div className="flex flex-wrap gap-2">
          {[".docx", ".pdf"].map((ext) => (
            <motion.button
              key={ext}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="inline-flex items-center gap-1.5 rounded-md border border-primary/40 bg-primary/10 px-3 py-1.5 font-mono text-[11px] font-medium text-primary transition-all duration-200 hover:bg-primary/20 hover:shadow-[0_0_20px_rgba(57,255,136,0.25)]"
            >
              <Download className="h-3.5 w-3.5" />
              Download Full Memo ({ext})
            </motion.button>
          ))}
        </div>
      </div>

      <div className="max-h-[640px] overflow-y-auto px-5 py-7 md:px-9 md:py-9">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[rgba(255,255,255,0.07)] pb-6">
          <div>
            <h2 className="font-sans text-2xl font-semibold tracking-[-0.02em] text-foreground md:text-3xl">
              {report.company}
            </h2>
            <div className="mt-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
              {report.ticker} · {report.sector}
            </div>
            <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/70">
              {report.generatedAt}
            </div>
          </div>
          <span className="rounded-md border border-warn/40 bg-warn/10 px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-warn">
            Investment stance: {report.stance}
          </span>
        </div>

        {/* Key metrics */}
        <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          {report.metrics.map((m, i) => (
            <motion.div
              key={m.label}
              {...reveal(0.05 * i)}
              className="rounded-lg border border-[rgba(255,255,255,0.07)] bg-[rgba(255,255,255,0.02)] p-3.5"
            >
              <div className="font-mono text-lg font-bold tabular-nums text-foreground">
                {m.value}
              </div>
              <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                {m.label}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Executive summary */}
        <section className="mt-9">
          <SectionTitle index="01" title="Executive Summary" />
          <div className="mt-4 space-y-4">
            {report.summary.map((p, i) => (
              <motion.p
                key={i}
                {...reveal(0.06 * i)}
                className="text-[14.5px] leading-[1.75] text-foreground/85"
              >
                {p}
              </motion.p>
            ))}
          </div>
          <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-primary/25 bg-primary/[0.05] p-3.5">
            <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
            <p className="font-mono text-[11px] leading-relaxed text-muted-foreground">
              Every figure above was cross-checked against its source filing by the
              anti-hallucination validator. Untraceable claims are removed before delivery.
            </p>
          </div>
        </section>

        {/* Risk scorecard */}
        <section className="mt-10">
          <SectionTitle index="02" title="Six-Dimension Risk Scorecard" />
          <div className="mt-4 space-y-2.5">
            {report.risks.map((r, i) => {
              const s = riskStyles[r.level];
              return (
                <motion.div
                  key={r.dimension}
                  {...reveal(0.05 * i)}
                  className="rounded-lg border border-[rgba(255,255,255,0.07)] bg-[rgba(255,255,255,0.02)] p-3.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-medium text-foreground">{r.dimension}</span>
                    <div className="flex items-center gap-3">
                      <span className={`font-mono text-sm font-bold tabular-nums ${s.text}`}>
                        {r.score.toFixed(1)}
                        <span className="text-muted-foreground/60"> / 10</span>
                      </span>
                      <span
                        className={`rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] ${s.chip}`}
                      >
                        {s.label}
                      </span>
                    </div>
                  </div>
                  <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-[rgba(255,255,255,0.06)]">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${r.score * 10}%` }}
                      transition={{ duration: 0.8, delay: 0.15 + i * 0.06, ease: "easeOut" }}
                      className={`h-full rounded-full ${s.bar}`}
                    />
                  </div>
                  <p className="mt-2 text-[12.5px] text-muted-foreground">{r.note}</p>
                </motion.div>
              );
            })}
          </div>
        </section>

        {/* Anomaly flags */}
        <section className="mt-10">
          <SectionTitle index="03" title="Anomaly Flags" />
          <ul className="mt-4 space-y-2.5">
            {report.anomalies.map((a, i) => {
              const s = riskStyles[a.severity];
              return (
                <motion.li
                  key={a.title}
                  {...reveal(0.05 * i)}
                  className="rounded-lg border border-[rgba(255,255,255,0.07)] bg-[rgba(255,255,255,0.02)] p-3.5"
                >
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span
                      className={`rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] ${s.chip}`}
                    >
                      {s.label}
                    </span>
                    <span className="text-sm font-medium text-foreground">{a.title}</span>
                  </div>
                  <p className="mt-2 text-[12.5px] leading-relaxed text-muted-foreground">
                    {a.detail}
                  </p>
                </motion.li>
              );
            })}
          </ul>
        </section>
      </div>
    </motion.div>
  );
}

function SectionTitle({ index, title }: { index: string; title: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-primary">
        {index}
      </span>
      <h3 className="font-sans text-lg font-semibold tracking-[-0.01em] text-foreground">
        {title}
      </h3>
      <span className="h-px flex-1 bg-[rgba(255,255,255,0.07)]" />
    </div>
  );
}